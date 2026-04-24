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
        backup_dir: Path | None = None,
        output_path: Path | None = None,
    ) -> bool:
        """
        删除指定页面
        page_nums: 1-based 页码列表
        backup_dir: 如果指定，先备份原文件
        output_path: 如果指定，输出到新路径；否则覆盖原文件
        """
        import fitz
        import tempfile

        try:
            if backup_dir:
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_path = backup_dir / pdf_path.name
                shutil.copy2(str(pdf_path), str(backup_path))
                logger.info(f"已备份至: {backup_path}")

            with fitz.open(str(pdf_path)) as doc:
                # 转换为 0-based 并去重排序（从大到小删除避免索引偏移）
                indices = sorted({p - 1 for p in page_nums if 1 <= p <= len(doc)}, reverse=True)
                if not indices:
                    return False

                for idx in indices:
                    doc.delete_page(idx)

                save_path = output_path or pdf_path
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

    def find_blank_pages(self, pdf_path: Path, min_text_length: int = 10) -> list[int]:
        """
        查找所有空白页的页码（1-based）
        """
        import fitz

        blank_pages = []
        page_number_pattern = re.compile(r"^[\s\-–—]*\d+[\s\-–—]*$")

        with fitz.open(str(pdf_path)) as doc:
            for i in range(len(doc)):
                page = doc[i]
                text = page.get_text()

                if not text:
                    blank_pages.append(i + 1)
                    continue

                text_stripped = text.strip()
                if not text_stripped:
                    blank_pages.append(i + 1)
                    continue

                if len(text_stripped) < min_text_length:
                    blank_pages.append(i + 1)
                    continue

                if page_number_pattern.match(text_stripped):
                    blank_pages.append(i + 1)
                    continue

        return blank_pages

    def remove_blank_pages(
        self,
        pdf_path: Path,
        backup_dir: Path | None = None,
        output_path: Path | None = None,
        min_text_length: int = 10,
    ) -> tuple[bool, list[int]]:
        """
        删除所有空白页
        返回 (是否成功, 删除的页码列表)
        """
        blank_pages = self.find_blank_pages(pdf_path, min_text_length)
        if not blank_pages:
            return False, []

        success = self.delete_pages(pdf_path, blank_pages, backup_dir, output_path)
        return success, blank_pages
