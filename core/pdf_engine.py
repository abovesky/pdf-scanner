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
