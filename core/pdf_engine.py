"""
PDF 统一引擎
基于 PyMuPDF 实现页面渲染、删除、文本提取、空白页检测
"""
from __future__ import annotations

import logging
import os
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger("pdf_scanner")


def parse_pages_to_check(pages_str: str, total_pages: int) -> list[int]:
    """
    解析页面范围字符串，返回要检查的页码列表
    支持格式: "2", "2:5", "2,-1", "2:5,7:10,-3:-1"
    """
    pages_to_check = set()
    ranges = pages_str.split(",")

    for range_str in ranges:
        range_str = range_str.strip()
        if not range_str:
            continue

        if ":" in range_str:
            parts = range_str.split(":")
            if len(parts) != 2:
                logger.warning(f"无效的页面范围格式: {range_str}")
                continue

            start_str, end_str = parts

            if start_str.startswith("-"):
                start = total_pages + int(start_str) + 1
            else:
                start = int(start_str)

            if end_str.startswith("-"):
                end = total_pages + int(end_str) + 1
            else:
                end = int(end_str)

            if start < 1 or start > total_pages:
                logger.warning(f"起始页 {start} 超出范围 (1-{total_pages})")
                continue
            if end < 1 or end > total_pages:
                logger.warning(f"结束页 {end} 超出范围 (1-{total_pages})")
                continue

            if start <= end:
                pages_to_check.update(range(start, end + 1))
            else:
                pages_to_check.update(range(end, start + 1))
        else:
            if range_str.startswith("-"):
                page = total_pages + int(range_str) + 1
            else:
                page = int(range_str)

            if page < 1 or page > total_pages:
                logger.warning(f"页码 {page} 超出范围 (1-{total_pages})")
                continue

            pages_to_check.add(page)

    return sorted(list(pages_to_check))


class PDFEngine:
    """基于 PyMuPDF 的 PDF 操作引擎"""

    def get_page_count(self, pdf_path: Path) -> int:
        """获取 PDF 总页数"""
        import fitz
        with fitz.open(str(pdf_path)) as doc:
            return len(doc)

    def render_pages(
        self, pdf_path: Path, page_nums: list[int], dpi: int = 150
    ) -> list[tuple[int, Image.Image]]:
        """
        将指定页面渲染为 PIL Image
        返回 [(页码, Image), ...]
        """
        import fitz
        from PIL import Image

        result = []
        with fitz.open(str(pdf_path)) as doc:
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)

            for page_num in page_nums:
                if page_num < 1 or page_num > len(doc):
                    continue
                page = doc[page_num - 1]
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                result.append((page_num, img))

        return result

    def delete_pages(
        self,
        pdf_path: Path,
        page_nums: list[int],
        output_path: Path | None = None,
        backup: bool = True,
    ) -> bool:
        """
        删除指定页面
        page_nums: 1-based 页码列表
        output_path: 如果指定，输出到新路径；否则覆盖原文件
        backup: 覆盖原文件时是否创建 .bak 备份
        """
        import fitz
        import tempfile

        save_path = output_path or pdf_path

        # 备份原文件
        if backup and save_path == pdf_path:
            backup_path = pdf_path.with_suffix(".pdf.bak")
            try:
                shutil.copy2(str(pdf_path), str(backup_path))
                logger.info(f"已创建备份: {backup_path.name}")
            except Exception as e:
                logger.warning(f"创建备份失败: {e}")

        try:
            with fitz.open(str(pdf_path)) as doc:
                # 转换为 0-based 并去重排序（从大到小删除避免索引偏移）
                indices = sorted({p - 1 for p in page_nums if 1 <= p <= len(doc)}, reverse=True)
                if not indices:
                    return False

                for idx in indices:
                    doc.delete_page(idx)

                save_path.parent.mkdir(parents=True, exist_ok=True)

                # Windows 上直接保存到同一文件可能因句柄占用失败，先写临时文件再替换
                if save_path == pdf_path:
                    fd, tmp_path = tempfile.mkstemp(suffix=".pdf", dir=str(pdf_path.parent))
                    os.close(fd)
                    doc.save(tmp_path, garbage=4, deflate=True)
                    shutil.move(tmp_path, str(save_path))
                else:
                    doc.save(str(save_path), garbage=4, deflate=True)

            return True
        except Exception as e:
            logger.error(f"删除页面失败: {e}")
            return False

    def _page_has_visual_content(self, page) -> bool:
        """检查页面是否包含图像或矢量图（用于扫描页保护）"""
        return bool(page.get_images()) or bool(page.get_drawings())

    def find_blank_pages(self, pdf_path: Path, min_text_length: int = 10) -> list[int]:
        """
        查找所有空白页的页码（1-based）
        对扫描版/图片型 PDF 有保护机制：若页面含图像/矢量图但文本极少，将保守保留
        """
        import fitz

        blank_pages = []
        # 支持阿拉伯数字、罗马数字、字母页码（如 5, iv, A-1, B）
        page_number_pattern = re.compile(
            r"^[\s\-–—]*(?:\d+|[ivxlcdmIVXLCDM]+|[a-zA-Z](?:[-–—]?\d*)?)[\s\-–—]*$"
        )

        with fitz.open(str(pdf_path)) as doc:
            for i in range(len(doc)):
                page = doc[i]
                text = page.get_text()

                if not text:
                    if self._page_has_visual_content(page):
                        logger.debug(f"第{i + 1}页无文本但含图像/矢量图，视为扫描页保留")
                        continue
                    blank_pages.append(i + 1)
                    continue

                text_stripped = text.strip()
                if not text_stripped:
                    if self._page_has_visual_content(page):
                        logger.debug(f"第{i + 1}页文本为空但含图像/矢量图，视为扫描页保留")
                        continue
                    blank_pages.append(i + 1)
                    continue

                if len(text_stripped) < min_text_length:
                    if self._page_has_visual_content(page):
                        logger.debug(f"第{i + 1}页文本短但含图像/矢量图，保守保留")
                        continue
                    blank_pages.append(i + 1)
                    continue

                if page_number_pattern.match(text_stripped):
                    blank_pages.append(i + 1)
                    continue

        return blank_pages

    @staticmethod
    def _has_encrypt_entry(pdf_path: Path) -> bool:
        """
        扫描 PDF 文件尾部检查是否存在 /Encrypt 字典。
        PyMuPDF 的 doc.is_encrypted 在打开仅设所有者密码的 PDF 时
        可能返回 False（因自动空密码认证），需要原始文件级兜底检测。
        """
        try:
            file_size = pdf_path.stat().st_size
            # trailer 通常在文件末尾 4KB 内
            read_size = min(file_size, 4096)
            with open(pdf_path, "rb") as f:
                f.seek(file_size - read_size)
                tail = f.read()
            return b"/Encrypt" in tail
        except Exception:
            return False

    def is_encrypted(self, pdf_path: Path) -> bool:
        """检查 PDF 是否有密码保护"""
        import fitz
        with fitz.open(str(pdf_path)) as doc:
            if doc.is_encrypted:
                return True
        # 兜底：PyMuPDF 自动认证后 is_encrypted 可能为 False，
        # 但文件仍含 /Encrypt 字典（如仅设权限密码的 PDF）
        return self._has_encrypt_entry(pdf_path)

    def remove_password(
        self,
        pdf_path: Path,
        password: str = "",
        output_path: Path | None = None,
        backup: bool = True,
    ) -> tuple[bool, str]:
        """
        清除 PDF 密码保护
        password: 用户密码（空字符串适用于仅需所有者密码的文件）
        output_path: 输出路径，默认覆盖原文件
        backup: 覆盖时是否创建 .bak 备份
        返回 (是否成功, 消息)
        """
        import fitz
        import tempfile

        save_path = output_path or pdf_path

        try:
            with fitz.open(str(pdf_path)) as doc:
                has_encrypt = self._has_encrypt_entry(pdf_path)

                if not has_encrypt and not doc.is_encrypted:
                    return False, "文件未加密"

                if doc.is_encrypted:
                    if not doc.authenticate(password):
                        return False, "密码错误，无法解密"
                else:
                    # 文件有 /Encrypt 但 PyMuPDF 已自动认证，
                    # 仍需调用 authenticate 确保 save 时移除加密
                    doc.authenticate(password)

                # 备份原文件
                if backup and save_path == pdf_path:
                    backup_path = pdf_path.with_suffix(".pdf.bak")
                    try:
                        shutil.copy2(str(pdf_path), str(backup_path))
                        logger.info(f"已创建备份: {backup_path.name}")
                    except Exception as e:
                        logger.warning(f"创建备份失败: {e}")

                save_path.parent.mkdir(parents=True, exist_ok=True)

                if save_path == pdf_path:
                    fd, tmp_path = tempfile.mkstemp(suffix=".pdf", dir=str(pdf_path.parent))
                    os.close(fd)
                    doc.save(tmp_path, garbage=4, deflate=True)
                    shutil.move(tmp_path, str(save_path))
                else:
                    doc.save(str(save_path), garbage=4, deflate=True)

            return True, "密码已清除"
        except Exception as e:
            logger.error(f"清除密码失败: {e}")
            return False, str(e)

    # 签名相关正则
    _SIG_FIELD_RE = re.compile(r"/FT\s*/Sig\b")
    _SIG_VALUE_RE = re.compile(r"/Type\s*/Sig\b")

    def _find_signature_xrefs(self, doc) -> tuple[list[int], list[int]]:
        """
        查找所有签名相关的 xref
        返回 (签名字段 xref 列表, 签名值字典 xref 列表)
        """
        field_xrefs = []
        value_xrefs = []
        for xref in range(1, doc.xref_length()):
            try:
                obj_str = doc.xref_object(xref)
                if self._SIG_FIELD_RE.search(obj_str):
                    field_xrefs.append(xref)
                elif self._SIG_VALUE_RE.search(obj_str):
                    value_xrefs.append(xref)
            except Exception:
                continue
        return field_xrefs, value_xrefs

    def _clean_acroform_fields(self, doc, sig_field_xrefs: list[int]) -> None:
        """从 AcroForm 的 /Fields 数组中移除签名字段引用"""
        try:
            catalog_xref = doc.pdf_catalog()
            catalog_str = doc.xref_object(catalog_xref)
            # 查找 AcroForm 引用
            acroform_match = re.search(r"/AcroForm\s+(\d+)\s+(\d+)\s+R", catalog_str)
            if not acroform_match:
                return
            acroform_xref = int(acroform_match.group(1))
            acroform_str = doc.xref_object(acroform_xref)

            # 查找 Fields 数组引用
            fields_match = re.search(r"/Fields\s+(\d+)\s+(\d+)\s+R", acroform_str)
            if not fields_match:
                return
            fields_xref = int(fields_match.group(1))

            # 读取 Fields 数组内容
            fields_str = doc.xref_object(fields_xref)
            # 提取所有 xref 引用
            refs = re.findall(r"(\d+)\s+(\d+)\s+R", fields_str)
            remaining_refs = [
                f"{xref_num} {gen_num} R"
                for xref_num, gen_num in refs
                if int(xref_num) not in sig_field_xrefs
            ]

            # 用 xref_set_object 替换整个 Fields 数组
            new_array = f"[{' '.join(remaining_refs)}]"
            doc.xref_set_object(fields_xref, new_array)
        except Exception as e:
            logger.warning(f"清理 AcroForm Fields 时出错: {e}")

    def has_signatures(self, pdf_path: Path) -> bool:
        """检查 PDF 是否包含数字签名"""
        import fitz
        with fitz.open(str(pdf_path)) as doc:
            field_xrefs, value_xrefs = self._find_signature_xrefs(doc)
            return bool(field_xrefs) or bool(value_xrefs)

    def remove_signatures(
        self,
        pdf_path: Path,
        output_path: Path | None = None,
        backup: bool = True,
    ) -> tuple[bool, str]:
        """
        清除 PDF 数字签名
        通过重建全新 PDF（仅复制页面内容）彻底丢弃原文件中的签名结构。
        output_path: 输出路径，默认覆盖原文件
        backup: 覆盖时是否创建 .bak 备份
        返回 (是否成功, 消息)
        """
        import fitz
        import tempfile

        save_path = output_path or pdf_path

        try:
            with fitz.open(str(pdf_path)) as src_doc:
                # 检测签名
                sig_field_xrefs, sig_value_xrefs = self._find_signature_xrefs(src_doc)
                all_sig_xrefs = set(sig_field_xrefs + sig_value_xrefs)
                if not all_sig_xrefs:
                    return False, "文件无数字签名"

                sig_count = len(sig_field_xrefs) or len(sig_value_xrefs)

                # 备份原文件
                if backup and save_path == pdf_path:
                    backup_path = pdf_path.with_suffix(".pdf.bak")
                    try:
                        shutil.copy2(str(pdf_path), str(backup_path))
                        logger.info(f"已创建备份: {backup_path.name}")
                    except Exception as e:
                        logger.warning(f"创建备份失败: {e}")

                save_path.parent.mkdir(parents=True, exist_ok=True)

                # 重建全新 PDF：只复制页面，丢弃所有表单、签名、元数据
                new_doc = fitz.open()
                new_doc.insert_pdf(
                    src_doc,
                    from_page=0,
                    to_page=src_doc.page_count - 1,
                    start_at=-1,
                )

                # 复制基本元数据（不含签名相关）
                meta = src_doc.metadata
                if meta:
                    clean_meta = {k: v for k, v in meta.items() if v and k != "encryption"}
                    if clean_meta:
                        new_doc.set_metadata(clean_meta)

                # 清理新文档中残留的签名字段和 widget
                for page in new_doc:
                    widgets_to_delete = []
                    widget = page.first_widget
                    while widget:
                        widgets_to_delete.append(widget)
                        widget = widget.next
                    for w in widgets_to_delete:
                        try:
                            page.delete_widget(w)
                        except Exception:
                            pass

                # 清除文档目录中的 AcroForm、Perms、DSS 等
                try:
                    catalog_xref = new_doc.pdf_catalog()
                    new_doc.xref_set_key(catalog_xref, "AcroForm", "null")
                    new_doc.xref_set_key(catalog_xref, "Perms", "null")
                    new_doc.xref_set_key(catalog_xref, "DSS", "null")
                    new_doc.xref_set_key(catalog_xref, "DocTimeStamp", "null")
                except Exception:
                    pass

                fd, tmp_path = tempfile.mkstemp(suffix=".pdf", dir=str(pdf_path.parent))
                os.close(fd)
                new_doc.save(tmp_path, garbage=4, deflate=True)
                new_doc.close()

            if save_path == pdf_path:
                shutil.move(tmp_path, str(save_path))
            else:
                shutil.copy2(tmp_path, str(save_path))
                os.remove(tmp_path)

            return True, f"已清除 {sig_count} 个签名"
        except Exception as e:
            logger.error(f"清除签名失败: {e}")
            return False, str(e)

    def remove_blank_pages(
        self,
        pdf_path: Path,
        output_path: Path | None = None,
        min_text_length: int = 10,
        backup: bool = True,
    ) -> tuple[bool, list[int]]:
        """
        删除所有空白页
        返回 (是否成功, 删除的页码列表)
        """
        blank_pages = self.find_blank_pages(pdf_path, min_text_length)
        if not blank_pages:
            return False, []

        success = self.delete_pages(pdf_path, blank_pages, output_path, backup=backup)
        return success, blank_pages

    def analyze_annotation_watermarks(self, pdf_path: Path) -> list[dict]:
        """
        检测注释型水印
        返回 [{'page': int, 'type': str, 'rect': tuple}, ...]
        """
        import fitz

        results = []
        with fitz.open(str(pdf_path)) as doc:
            for i in range(len(doc)):
                page = doc[i]
                for annot in page.annots():
                    if annot is None:
                        continue
                    subtype = annot.type[1]
                    if subtype in ("Watermark", "Stamp"):
                        results.append(
                            {
                                "page": i + 1,
                                "type": subtype,
                                "rect": tuple(annot.rect),
                            }
                        )
        return results

    def remove_annotation_watermarks(
        self,
        pdf_path: Path,
        output_path: Path | None = None,
        backup: bool = True,
    ) -> tuple[bool, int, list[int], str]:
        """
        删除注释型水印并保存
        返回 (是否修改, 删除数量, 影响的页码列表, 消息)
        """
        import fitz
        import tempfile

        save_path = output_path or pdf_path

        try:
            with fitz.open(str(pdf_path)) as doc:
                removed_count = 0
                affected_pages: set[int] = set()

                for i in range(len(doc)):
                    page = doc[i]
                    annots_to_delete = []
                    for annot in page.annots():
                        if annot is None:
                            continue
                        subtype = annot.type[1]
                        if subtype in ("Watermark", "Stamp"):
                            annots_to_delete.append(annot)

                    for annot in annots_to_delete:
                        page.delete_annot(annot)
                        removed_count += 1
                        affected_pages.add(i + 1)

                if removed_count == 0:
                    return False, 0, [], "未发现水印注释"

                # 备份原文件
                if backup and save_path == pdf_path:
                    backup_path = pdf_path.with_suffix(".pdf.bak")
                    try:
                        shutil.copy2(str(pdf_path), str(backup_path))
                        logger.info(f"已创建备份: {backup_path.name}")
                    except Exception as e:
                        logger.warning(f"创建备份失败: {e}")

                save_path.parent.mkdir(parents=True, exist_ok=True)

                # Windows 上直接保存到同一文件可能因句柄占用失败，先写临时文件再替换
                if save_path == pdf_path:
                    fd, tmp_path = tempfile.mkstemp(suffix=".pdf", dir=str(pdf_path.parent))
                    os.close(fd)
                    doc.save(tmp_path, garbage=4, deflate=True)
                    shutil.move(tmp_path, str(save_path))
                else:
                    doc.save(str(save_path), garbage=4, deflate=True)

            return True, removed_count, sorted(affected_pages), f"已删除 {removed_count} 个水印注释"
        except Exception as e:
            logger.error(f"去除水印失败: {e}")
            return False, 0, [], str(e)

    @staticmethod
    def _parse_size_str(size_str: str) -> int:
        """解析大小字符串，支持 K/k(KB) 和 M/m(MB) 后缀"""
        size_str = size_str.strip().upper()
        if size_str.endswith("K"):
            return int(float(size_str[:-1]) * 1024)
        elif size_str.endswith("M"):
            return int(float(size_str[:-1]) * 1024 * 1024)
        else:
            return int(size_str)

    @staticmethod
    def _generate_transparent_png() -> bytes:
        """生成 1x1 透明 PNG 字节流"""
        import io

        from PIL import Image

        img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    @staticmethod
    def _image_matches(img: ImageInfo, criteria: ImageMatchCriteria) -> bool:
        """
        判断单张图片是否满足匹配条件
        同类条件 OR，不同类条件 AND
        """
        conditions: list[bool] = []

        # MD5 维度（列表内 OR）— 匹配流 MD5 或像素 MD5
        if criteria.md5s:
            conditions.append(img.md5 in criteria.md5s)
        if criteria.pixel_md5s:
            conditions.append(img.pixel_md5 in criteria.pixel_md5s)

        # 尺寸维度（范围 AND）
        dim_ok = True
        if criteria.min_width is not None and img.width < criteria.min_width:
            dim_ok = False
        if criteria.max_width is not None and img.width > criteria.max_width:
            dim_ok = False
        if criteria.min_height is not None and img.height < criteria.min_height:
            dim_ok = False
        if criteria.max_height is not None and img.height > criteria.max_height:
            dim_ok = False
        if criteria.min_width is not None or criteria.max_width is not None or criteria.min_height is not None or criteria.max_height is not None:
            conditions.append(dim_ok)

        # 大小维度（范围 AND）
        size_ok = True
        if criteria.min_size is not None and img.size < criteria.min_size:
            size_ok = False
        if criteria.max_size is not None and img.size > criteria.max_size:
            size_ok = False
        if criteria.min_size is not None or criteria.max_size is not None:
            conditions.append(size_ok)

        # 格式维度（列表内 OR）
        if criteria.formats:
            conditions.append(img.format in criteria.formats)

        # 覆盖率维度（范围 AND）
        cov_ok = True
        if criteria.min_coverage is not None:
            if img.coverage is None or img.coverage < criteria.min_coverage:
                cov_ok = False
        if criteria.max_coverage is not None:
            if img.coverage is None or img.coverage > criteria.max_coverage:
                cov_ok = False
        if criteria.min_coverage is not None or criteria.max_coverage is not None:
            conditions.append(cov_ok)

        # Alpha 维度
        if criteria.has_alpha is not None:
            conditions.append(img.has_alpha == criteria.has_alpha)

        if not conditions:
            return False
        return all(conditions)

    def analyze_images(self, pdf_path: Path) -> list[ImageInfo]:
        """分析 PDF 中的所有嵌入图片，返回图片信息列表"""
        import hashlib
        import io

        import fitz
        from PIL import Image

        results: list[ImageInfo] = []
        seen_xrefs: set[int] = set()

        with fitz.open(str(pdf_path)) as doc:
            for page_num in range(1, len(doc) + 1):
                if page_num < 1 or page_num > len(doc):
                    continue
                page = doc[page_num - 1]
                page_area = page.rect.width * page.rect.height

                for img_info in page.get_images(full=True):
                    xref = img_info[0]
                    if xref in seen_xrefs:
                        continue
                    seen_xrefs.add(xref)

                    try:
                        extracted = doc.extract_image(xref)
                        if not extracted:
                            continue

                        img_bytes = extracted["image"]
                        ext = extracted.get("ext", "").lower()
                        width = extracted.get("width", 0)
                        height = extracted.get("height", 0)
                        size = len(img_bytes)
                        md5 = hashlib.md5(img_bytes).hexdigest().lower()

                        # 覆盖率
                        coverage: float | None = None
                        rects = page.get_image_rects(xref)
                        if rects and page_area > 0:
                            total_rect_area = sum(r.width * r.height for r in rects)
                            coverage = total_rect_area / page_area

                        # Alpha 通道：检查 SMask（PyMuPDF 将 alpha 存为独立 SMask 对象）
                        # 或检查 PNG 解码后的模式
                        has_alpha = False
                        try:
                            xref_obj = doc.xref_object(xref)
                            if "/SMask" in xref_obj:
                                has_alpha = True
                            elif ext == "png":
                                try:
                                    pil_img = Image.open(io.BytesIO(img_bytes))
                                    if "A" in pil_img.mode:
                                        has_alpha = True
                                except Exception:
                                    pass
                        except Exception:
                            pass

                        # 像素级 MD5（用于 --image 匹配，不受重编码影响）
                        # 统一用 RGB 模式计算，因为 PyMuPDF 提取时会将 alpha 存为 SMask
                        pixel_md5 = ""
                        try:
                            pil_img = Image.open(io.BytesIO(img_bytes))
                            pil_img = pil_img.convert("RGB")
                            pixel_md5 = hashlib.md5(pil_img.tobytes()).hexdigest().lower()
                        except Exception:
                            pass

                        results.append(
                            ImageInfo(
                                xref=xref,
                                page=page_num,
                                md5=md5,
                                pixel_md5=pixel_md5,
                                width=width,
                                height=height,
                                size=size,
                                format=ext,
                                coverage=coverage,
                                has_alpha=has_alpha,
                            )
                        )
                    except Exception as e:
                        logger.warning(f"提取图片 xref={xref} 失败: {e}")

        return results

    def remove_images_by_criteria(
        self,
        pdf_path: Path,
        criteria: ImageMatchCriteria,
        output_path: Path | None = None,
        backup: bool = True,
    ) -> tuple[bool, int, list[ImageInfo], str]:
        """
        按条件匹配并删除图片（替换为透明像素）
        返回 (是否修改, 删除实例数, 匹配到的图片列表, 消息)
        """
        import fitz
        import tempfile

        # 分析并匹配
        all_images = self.analyze_images(pdf_path)
        matched = [img for img in all_images if self._image_matches(img, criteria)]
        if not matched:
            return False, 0, [], "未匹配到目标图片"

        xrefs_to_replace = {img.xref for img in matched}
        save_path = output_path or pdf_path

        try:
            with fitz.open(str(pdf_path)) as doc:
                # 统计实际影响的页面实例数
                instance_count = 0
                for page_num in range(1, len(doc) + 1):
                    if page_num < 1 or page_num > len(doc):
                        continue
                    page = doc[page_num - 1]
                    for img_info in page.get_images(full=True):
                        if img_info[0] in xrefs_to_replace:
                            instance_count += 1

                # 替换数据流并修正 XObject 字典
                transparent_png = self._generate_transparent_png()
                for xref in xrefs_to_replace:
                    try:
                        doc.update_stream(xref, transparent_png)
                        doc.xref_set_key(xref, "Width", "1")
                        doc.xref_set_key(xref, "Height", "1")
                        doc.xref_set_key(xref, "ColorSpace", "/DeviceRGB")
                        doc.xref_set_key(xref, "BitsPerComponent", "8")
                        for key in ("Mask", "SMask", "Decode", "DecodeParms"):
                            try:
                                doc.xref_set_key(xref, key, "null")
                            except Exception:
                                pass
                    except Exception as e:
                        logger.warning(f"替换 xref={xref} 失败: {e}")

                # 备份
                if backup and save_path == pdf_path:
                    backup_path = pdf_path.with_suffix(".pdf.bak")
                    try:
                        shutil.copy2(str(pdf_path), str(backup_path))
                        logger.info(f"已创建备份: {backup_path.name}")
                    except Exception as e:
                        logger.warning(f"创建备份失败: {e}")

                save_path.parent.mkdir(parents=True, exist_ok=True)

                if save_path == pdf_path:
                    fd, tmp_path = tempfile.mkstemp(suffix=".pdf", dir=str(pdf_path.parent))
                    os.close(fd)
                    doc.save(tmp_path, garbage=4, deflate=True)
                    shutil.move(tmp_path, str(save_path))
                else:
                    doc.save(str(save_path), garbage=4, deflate=True)

            msg = f"已删除 {instance_count} 个图片实例（涉及 {len(xrefs_to_replace)} 个唯一图像）"
            return True, instance_count, matched, msg
        except Exception as e:
            logger.error(f"删除图片失败: {e}")
            return False, 0, [], str(e)

    # ---- 内置字体名映射表 ----
    _BUILTIN_FONTS = frozenset({"china-s", "china-t", "japan", "korea", "helv", "tiro", "cour", "symb", "zadb"})

    _CJK_FONT_MAP: list[tuple[str, str]] = [
        # (关键字, 内置字体名) — 按优先级排列
        ("MingLiu", "china-t"),
        ("Ming", "china-t"),
        ("宋", "china-s"),
        ("SimSun", "china-s"),
        ("Song", "china-s"),
        ("NSimSun", "china-s"),
        ("黑", "china-s"),
        ("YaHei", "china-s"),
        ("Hei", "china-s"),
        ("SimHei", "china-s"),
        ("楷", "china-s"),
        ("Kai", "china-s"),
        ("FangSong", "china-s"),
        ("仿宋", "china-s"),
    ]

    @staticmethod
    def _map_to_builtin_font(fontname: str) -> str:
        """将原始字体名映射为 PyMuPDF 内置字体名"""
        if not fontname:
            return "helv"
        # 已经是内置字体名
        if fontname in PDFEngine._BUILTIN_FONTS:
            return fontname
        # CJK 字体名映射
        name_lower = fontname
        for keyword, builtin in PDFEngine._CJK_FONT_MAP:
            if keyword in name_lower:
                return builtin
        # 日文
        if "Gothic" in name_lower or "Mincho" in name_lower:
            return "japan"
        # 韩文
        if "Batang" in name_lower or "Gulim" in name_lower or "Malgun" in name_lower:
            return "korea"
        # 默认使用 Helvetica
        return "helv"

    def find_text(self, pdf_path: Path, criteria: ReplaceCriteria) -> list[TextMatchInfo]:
        """
        按条件查找 PDF 中的文本
        返回所有匹配结果的列表
        """
        import fitz

        results: list[TextMatchInfo] = []

        with fitz.open(str(pdf_path)) as doc:
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                page_num = page_idx + 1

                # 精确匹配 + 大小写敏感：使用 search_for（最可靠）
                if not criteria.regex and criteria.case_sensitive:
                    rects_list = page.search_for(criteria.find)
                    if rects_list:
                        results.append(TextMatchInfo(
                            page=page_num,
                            rects=[tuple(r) for r in rects_list],
                            matched_text=criteria.find,
                        ))
                    continue

                # 其他模式：使用 rawdict 字符级定位
                text_dict = page.get_text("rawdict")
                for block in text_dict.get("blocks", []):
                    if block.get("type") != 0:  # 仅处理文本块
                        continue
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            span_text = span.get("text", "")
                            chars = span.get("chars", [])

                            # 某些 PDF 的 span.text 为空但 chars 有内容（如 insert_text 创建的）
                            if not span_text and chars:
                                span_text = "".join(c.get("c", "") for c in chars)

                            if not span_text:
                                continue

                            fontname = span.get("font", "")
                            fontsize = span.get("size", 0.0)
                            color = span.get("color", 0)

                            if criteria.regex:
                                # 正则匹配
                                flags = 0 if criteria.case_sensitive else re.IGNORECASE
                                try:
                                    pattern = re.compile(criteria.find, flags)
                                except re.error as e:
                                    logger.warning(f"正则表达式无效: {e}")
                                    return results

                                for m in pattern.finditer(span_text):
                                    start_idx, end_idx = m.start(), m.end()
                                    matched_rects = self._calc_chars_rect(chars, start_idx, end_idx)
                                    if matched_rects:
                                        results.append(TextMatchInfo(
                                            page=page_num,
                                            rects=matched_rects,
                                            matched_text=m.group(),
                                            fontname=fontname,
                                            fontsize=fontsize,
                                            color=color,
                                        ))
                            else:
                                # 精确匹配 + 大小写不敏感
                                find_text = criteria.find
                                span_search = span_text if criteria.case_sensitive else span_text.lower()
                                find_search = find_text if criteria.case_sensitive else find_text.lower()

                                start = 0
                                while True:
                                    idx = span_search.find(find_search, start)
                                    if idx == -1:
                                        break
                                    matched_rects = self._calc_chars_rect(chars, idx, idx + len(find_text))
                                    if matched_rects:
                                        results.append(TextMatchInfo(
                                            page=page_num,
                                            rects=matched_rects,
                                            matched_text=span_text[idx:idx + len(find_text)],
                                            fontname=fontname,
                                            fontsize=fontsize,
                                            color=color,
                                        ))
                                    start = idx + 1

        return results

    @staticmethod
    def _calc_chars_rect(chars: list, start_idx: int, end_idx: int) -> list[tuple]:
        """根据字符列表计算指定范围的 bbox，rect 四周内缩 0.5pt"""
        if not chars or start_idx >= len(chars) or end_idx > len(chars) or start_idx >= end_idx:
            return []

        # 收集所有字符 bbox
        char_rects = []
        for ci in range(start_idx, end_idx):
            c = chars[ci]
            bbox = c.get("bbox")
            if bbox and len(bbox) == 4:
                char_rects.append(bbox)

        if not char_rects:
            return []

        # 合并所有字符 bbox
        x0 = min(r[0] for r in char_rects)
        y0 = min(r[1] for r in char_rects)
        x1 = max(r[2] for r in char_rects)
        y1 = max(r[3] for r in char_rects)

        # 四周内缩 0.5pt
        inset = 0.5
        x0 += inset
        y0 += inset
        x1 -= inset
        y1 -= inset

        if x0 >= x1 or y0 >= y1:
            # 内缩后无有效区域，退回原始 rect
            x0 = min(r[0] for r in char_rects)
            y0 = min(r[1] for r in char_rects)
            x1 = max(r[2] for r in char_rects)
            y1 = max(r[3] for r in char_rects)

        return [(x0, y0, x1, y1)]

    @staticmethod
    def _rects_overlap_images(page, rects: list[tuple]) -> bool:
        """检查 rect 列表是否与页面图像重叠"""
        import fitz

        image_rects = []
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            try:
                for r in page.get_image_rects(xref):
                    image_rects.append(fitz.Rect(r))
            except Exception:
                pass

        if not image_rects:
            return False

        for rect_tuple in rects:
            r = fitz.Rect(rect_tuple)
            for img_r in image_rects:
                if r.intersects(img_r):
                    return True
        return False

    @staticmethod
    def _rects_overlap_drawings(page, rects: list[tuple]) -> bool:
        """检查 rect 列表是否与页面矢量图重叠"""
        import fitz

        drawings = page.get_drawings()
        if not drawings:
            return False

        for rect_tuple in rects:
            r = fitz.Rect(rect_tuple)
            for draw_item in drawings:
                if "rect" in draw_item and draw_item["rect"]:
                    draw_r = fitz.Rect(draw_item["rect"])
                    if r.intersects(draw_r):
                        return True
                # 检查绘制项的 items（线条/曲线）
                for item in draw_item.get("items", []):
                    if item[0] == "re":  # 矩形
                        item_rect = fitz.Rect(item[1])
                        if r.intersects(item_rect):
                            return True
        return False

    @staticmethod
    def _get_line_match_rect(line_info: dict, start_idx: int, end_idx: int) -> list[tuple]:
        """根据行信息中的 span 字符计算匹配区域的矩形列表"""
        # 计算所有 span 的 chars 累计偏移
        char_offset = 0
        for span_detail in line_info.get("spans", []):
            span_text = span_detail["text"]
            span_len = len(span_text)
            # 检查匹配是否在此 span 内
            if start_idx < char_offset + span_len and end_idx > char_offset:
                # 计算在此 span 内的局部索引
                local_start = max(0, start_idx - char_offset)
                local_end = min(span_len, end_idx - char_offset)
                # 需要从原始 rawdict 获取 chars，但 line_info 中没有 chars
                # 所以返回空列表，由调用者通过其他方式检查重叠
            char_offset += span_len
        return []  # 整行重写方案下不需要精确的匹配矩形用于重叠检测

    @staticmethod
    def _apply_matches_to_text(text: str, matches: list[tuple[int, int, str]]) -> str:
        """将匹配列表应用到文本，返回替换后的文本（从后往前替换以保持索引有效）"""
        if not matches:
            return text
        # 从后往前替换
        result = text
        for start_idx, end_idx, replace_text in sorted(matches, key=lambda x: x[0], reverse=True):
            result = result[:start_idx] + replace_text + result[end_idx:]
        return result

    def _scan_page_lines(self, page) -> list[dict]:
        """
        扫描页面的所有文本行，返回行信息列表。
        每行包含: bbox, text, fontname, fontsize, color, spans
        """
        lines_info: list[dict] = []
        text_dict = page.get_text("rawdict")

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                line_bbox = line.get("bbox")
                line_text = ""
                # 取第一个有文本的 span 的字体信息作为行字体
                fontname = ""
                fontsize = 0.0
                color = 0
                span_details: list[dict] = []

                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    chars = span.get("chars", [])

                    if not span_text and chars:
                        span_text = "".join(c.get("c", "") for c in chars)

                    if not span_text:
                        continue

                    if not fontname:
                        fontname = span.get("font", "")
                        fontsize = span.get("size", 0.0)
                        color = span.get("color", 0)

                    line_text += span_text
                    span_details.append({
                        "text": span_text,
                        "font": span.get("font", ""),
                        "size": span.get("size", 0.0),
                        "color": span.get("color", 0),
                    })

                if line_text:
                    lines_info.append({
                        "bbox": line_bbox,
                        "text": line_text,
                        "fontname": fontname,
                        "fontsize": fontsize,
                        "color": color,
                        "spans": span_details,
                    })

        return lines_info

    def _match_text(self, text: str, criteria: ReplaceCriteria) -> list[tuple[int, int, str]]:
        """
        在文本中按条件查找匹配，返回 [(start, end, replacement_text), ...]
        """
        matches: list[tuple[int, int, str]] = []

        if criteria.regex:
            flags = 0 if criteria.case_sensitive else re.IGNORECASE
            try:
                pattern = re.compile(criteria.find, flags)
            except re.error:
                return matches
            for m in pattern.finditer(text):
                replace_text = m.expand(criteria.replace)
                matches.append((m.start(), m.end(), replace_text))
        else:
            find_text = criteria.find
            text_search = text if criteria.case_sensitive else text.lower()
            find_search = find_text if criteria.case_sensitive else find_text.lower()
            start = 0
            while True:
                idx = text_search.find(find_search, start)
                if idx == -1:
                    break
                matches.append((idx, idx + len(find_text), criteria.replace))
                start = idx + 1

        return matches

    def replace_text(
        self,
        pdf_path: Path,
        criteria: ReplaceCriteria,
        dry_run: bool = False,
        backup: bool = True,
    ) -> tuple[bool, int, list[int], str]:
        """
        查找并替换 PDF 中的文本（整行重写方案）
        返回 (是否修改, 替换数量, 影响页码列表, 消息)
        """
        import fitz
        import tempfile

        try:
            with fitz.open(str(pdf_path)) as doc:
                total_matches = 0
                affected_pages: set[int] = set()
                warnings: list[str] = []

                for page_idx in range(len(doc)):
                    page = doc[page_idx]
                    page_num = page_idx + 1

                    # 检测扫描版 PDF
                    page_text = page.get_text()
                    if not page_text.strip() and self._page_has_visual_content(page):
                        warnings.append(f"第{page_num}页可能为扫描版，无法替换文本")
                        continue

                    # 扫描所有行
                    lines_info = self._scan_page_lines(page)

                    # 找到需要替换的行
                    lines_to_rewrite: list[tuple] = []  # (line_bbox, new_text, fontname, fontsize, match_count)

                    for line_info in lines_info:
                        line_text = line_info["text"]
                        line_bbox = line_info["bbox"]
                        fontname = line_info["fontname"]
                        fontsize = line_info["fontsize"]

                        match_list = self._match_text(line_text, criteria)
                        if not match_list:
                            continue

                        # 检查图像/矢量重叠
                        match_rects = []
                        for start_idx, end_idx, _ in match_list:
                            char_rects = self._get_line_match_rect(line_info, start_idx, end_idx)
                            match_rects.extend(char_rects)
                        if match_rects and self._rects_overlap_images(page, match_rects):
                            warnings.append(f"第{page_num}页匹配区域与图像重叠，替换后图像可能被删除")
                        if match_rects and self._rects_overlap_drawings(page, match_rects):
                            warnings.append(f"第{page_num}页匹配区域与矢量图重叠，替换后矢量图可能被删除")

                        # 替换文本溢出检查
                        for start_idx, end_idx, replace_text in match_list:
                            matched_text = line_text[start_idx:end_idx]
                            if len(replace_text) > len(matched_text) * 2 and len(replace_text) > len(matched_text):
                                warnings.append(
                                    f"第{page_num}页替换文本\"{replace_text[:20]}\"比原文\"{matched_text[:20]}\"长很多，可能出现字号缩放"
                                )

                        # 构建替换后的整行文本
                        new_text = self._apply_matches_to_text(line_text, match_list)

                        total_matches += len(match_list)
                        affected_pages.add(page_num)
                        lines_to_rewrite.append((line_bbox, new_text, fontname, fontsize))

                    if not dry_run and lines_to_rewrite:
                        # Redact 所有需要修改的行
                        for line_bbox, _, _, _ in lines_to_rewrite:
                            page.add_redact_annot(fitz.Rect(line_bbox))

                        page.apply_redactions()

                        # 重写所有行
                        for line_bbox, new_text, fontname, fontsize in lines_to_rewrite:
                            builtin_font = self._map_to_builtin_font(fontname)
                            # insert_textbox 在 redacted 页面上有 fontsize*0.115 的 y 偏移，需补偿
                            y_compensate = fontsize * 0.115
                            insert_rect = fitz.Rect(
                                line_bbox[0], line_bbox[1] + y_compensate,
                                line_bbox[0] + 2000, line_bbox[3] + 4,
                            )
                            try:
                                page.insert_textbox(
                                    insert_rect, new_text,
                                    fontname=builtin_font, fontsize=fontsize, align=0,
                                )
                            except Exception:
                                # 字体不支持时回退到 Helvetica
                                page.insert_textbox(
                                    insert_rect, new_text,
                                    fontname="helv", fontsize=fontsize, align=0,
                                )

                # 输出警告
                for w in warnings:
                    logger.warning(f"  ⚠ {w}")

                if total_matches == 0:
                    return False, 0, [], "未找到匹配文本"

                if dry_run:
                    return False, total_matches, sorted(affected_pages), f"预览：找到 {total_matches} 处匹配（{len(affected_pages)} 页）"

                # 备份
                if backup:
                    backup_path = pdf_path.with_suffix(".pdf.bak")
                    try:
                        shutil.copy2(str(pdf_path), str(backup_path))
                        logger.info(f"已创建备份: {backup_path.name}")
                    except Exception as e:
                        logger.warning(f"创建备份失败: {e}")

                # 保存
                pdf_path.parent.mkdir(parents=True, exist_ok=True)
                fd, tmp_path = tempfile.mkstemp(suffix=".pdf", dir=str(pdf_path.parent))
                os.close(fd)
                doc.save(tmp_path, garbage=4, deflate=True)
                shutil.move(tmp_path, str(pdf_path))

            return True, total_matches, sorted(affected_pages), f"已替换 {total_matches} 处匹配（{len(affected_pages)} 页）"
        except Exception as e:
            logger.error(f"替换文本失败: {e}")
            return False, 0, [], str(e)

    def replace_text_batch(
        self,
        pdf_path: Path,
        criteria_list: list[ReplaceCriteria],
        dry_run: bool = False,
        backup: bool = True,
    ) -> tuple[bool, int, list[int], str]:
        """
        批量查找并替换 PDF 中的文本（多组规则，整行重写方案）
        在同一次文件打开中依次应用多组替换规则，仅保存一次。
        返回 (是否修改, 替换数量, 影响页码列表, 消息)
        """
        import fitz
        import tempfile

        try:
            with fitz.open(str(pdf_path)) as doc:
                total_matches = 0
                affected_pages: set[int] = set()
                warnings: list[str] = []
                rules_summary: list[str] = []

                for rule_idx, criteria in enumerate(criteria_list, 1):
                    rule_matches = 0
                    rule_tag = f"规则{rule_idx}(\"{criteria.find}\"→\"{criteria.replace}\")"

                    for page_idx in range(len(doc)):
                        page = doc[page_idx]
                        page_num = page_idx + 1

                        # 检测扫描版 PDF
                        page_text = page.get_text()
                        if not page_text.strip() and self._page_has_visual_content(page):
                            if rule_idx == 1:
                                warnings.append(f"第{page_num}页可能为扫描版，无法替换文本")
                            continue

                        # 扫描所有行
                        lines_info = self._scan_page_lines(page)

                        # 找到需要替换的行
                        lines_to_rewrite: list[tuple] = []

                        for line_info in lines_info:
                            line_text = line_info["text"]
                            line_bbox = line_info["bbox"]
                            fontname = line_info["fontname"]
                            fontsize = line_info["fontsize"]

                            match_list = self._match_text(line_text, criteria)
                            if not match_list:
                                continue

                            # 溢出检查
                            for start_idx, end_idx, replace_text in match_list:
                                matched_text = line_text[start_idx:end_idx]
                                if len(replace_text) > len(matched_text) * 2 and len(replace_text) > len(matched_text):
                                    warnings.append(
                                        f"{rule_tag} 第{page_num}页替换文本\"{replace_text[:20]}\"比原文\"{matched_text[:20]}\"长很多，可能出现字号缩放"
                                    )

                            new_text = self._apply_matches_to_text(line_text, match_list)

                            rule_matches += len(match_list)
                            affected_pages.add(page_num)
                            lines_to_rewrite.append((line_bbox, new_text, fontname, fontsize))

                        if not dry_run and lines_to_rewrite:
                            # Redact 所有需要修改的行
                            for line_bbox, _, _, _ in lines_to_rewrite:
                                page.add_redact_annot(fitz.Rect(line_bbox))

                            page.apply_redactions()

                            # 重写所有行
                            for line_bbox, new_text, fontname, fontsize in lines_to_rewrite:
                                builtin_font = self._map_to_builtin_font(fontname)
                                y_compensate = fontsize * 0.115
                                insert_rect = fitz.Rect(
                                    line_bbox[0], line_bbox[1] + y_compensate,
                                    line_bbox[0] + 2000, line_bbox[3] + 4,
                                )
                                try:
                                    page.insert_textbox(
                                        insert_rect, new_text,
                                        fontname=builtin_font, fontsize=fontsize, align=0,
                                    )
                                except Exception:
                                    page.insert_textbox(
                                        insert_rect, new_text,
                                        fontname="helv", fontsize=fontsize, align=0,
                                    )

                    total_matches += rule_matches
                    rules_summary.append(f"{rule_tag}: {rule_matches}处")

                # 输出警告
                for w in warnings:
                    logger.warning(f"  ⚠ {w}")

                if total_matches == 0:
                    return False, 0, [], "未找到匹配文本"

                if dry_run:
                    summary = " | ".join(rules_summary)
                    return False, total_matches, sorted(affected_pages), f"预览：{summary}（共 {len(affected_pages)} 页）"

                # 备份
                if backup:
                    backup_path = pdf_path.with_suffix(".pdf.bak")
                    try:
                        shutil.copy2(str(pdf_path), str(backup_path))
                        logger.info(f"已创建备份: {backup_path.name}")
                    except Exception as e:
                        logger.warning(f"创建备份失败: {e}")

                # 保存
                pdf_path.parent.mkdir(parents=True, exist_ok=True)
                fd, tmp_path = tempfile.mkstemp(suffix=".pdf", dir=str(pdf_path.parent))
                os.close(fd)
                doc.save(tmp_path, garbage=4, deflate=True)
                shutil.move(tmp_path, str(pdf_path))

            summary = " | ".join(rules_summary)
            return True, total_matches, sorted(affected_pages), f"已替换 {summary}（{len(affected_pages)} 页）"
        except Exception as e:
            logger.error(f"批量替换文本失败: {e}")
            return False, 0, [], str(e)

    @staticmethod
    def _get_first_span_font(page, find_text: str) -> tuple[str, float, int]:
        """获取第一个包含查找文本的 span 的字体信息"""
        text_dict = page.get_text("rawdict")
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if find_text in span.get("text", ""):
                        return (
                            span.get("font", ""),
                            span.get("size", 0.0),
                            span.get("color", 0),
                        )
        return ("", 0.0, 0)


@dataclass
class ImageMatchCriteria:
    md5s: list[str] | None = None
    pixel_md5s: list[str] | None = None
    min_width: int | None = None
    max_width: int | None = None
    min_height: int | None = None
    max_height: int | None = None
    min_size: int | None = None
    max_size: int | None = None
    formats: list[str] | None = None
    min_coverage: float | None = None
    max_coverage: float | None = None
    has_alpha: bool | None = None


@dataclass
class ImageInfo:
    xref: int
    page: int
    md5: str
    pixel_md5: str
    width: int
    height: int
    size: int
    format: str
    coverage: float | None
    has_alpha: bool


@dataclass
class ReplaceCriteria:
    """PDF 文本替换条件"""
    find: str                          # 查找文本或正则
    replace: str                       # 替换文本（空串表示删除）
    regex: bool = False                # 是否正则匹配
    case_sensitive: bool = False       # 是否大小写敏感


@dataclass
class TextMatchInfo:
    """PDF 文本匹配结果"""
    page: int                    # 1-based 页码
    rects: list[tuple]           # 匹配区域矩形列表（多行文本可能有多个 rect）
    matched_text: str            # 匹配到的文本
    fontname: str = ""           # 原始字体名
    fontsize: float = 0.0        # 原始字号
    color: int = 0               # 原始颜色
