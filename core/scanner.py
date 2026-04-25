"""
并发扫描器核心
支持多文件并行、页面级 OCR 并发、暂停/取消控制
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from .config import AppConfig
from .models import FileStatus, ScanProgress, ScanResult
from .ocr_engines import OCREngineFactory, OCRConfig
from .pdf_engine import PDFEngine, parse_pages_to_check

logger = logging.getLogger("pdf_scanner")


class PDFScanner:
    """PDF 版权页扫描器"""

    def __init__(
        self,
        config: AppConfig,
        pdf_engine: PDFEngine | None = None,
        ocr_engine: OCREngine | None = None,
        cancel_event: threading.Event | None = None,
    ):
        self.config = config
        self.pdf_engine = pdf_engine or PDFEngine()
        self.ocr_engine = ocr_engine
        self.cancel_event = cancel_event

        # 回调函数（供 GUI 调用）
        self.log_callback: Callable[[str, str], None] | None = None
        self.result_callback: Callable[[ScanResult], None] | None = None

        # 内部状态
        self.keywords = config.keywords if config.case_sensitive else [kw.lower() for kw in config.keywords]
        self.progress_data = self._load_progress()
        self._pending_saves: list[str] = []

        if self.ocr_engine is None:
            self._init_ocr_engine()

    def _init_ocr_engine(self) -> None:
        """初始化 OCR 引擎"""
        ocr_config = OCRConfig(
            app_id=self.config.baidu_app_id or self.config.iflytek_app_id,
            api_key=self.config.baidu_api_key or self.config.iflytek_api_key,
            secret_key=self.config.baidu_secret_key or self.config.iflytek_secret_key or self.config.volc_secret_key,
            access_key=self.config.volc_access_key,
        )
        self.ocr_engine = OCREngineFactory.create(
            self.config.recognition_mode,
            ocr_config,
            lang=self.config.ocr_lang,
            accuracy=self.config.ocr_accuracy,
            case_sensitive=self.config.case_sensitive,
        )
        self._log("info", f"已初始化 {self.config.recognition_mode} OCR 引擎")

    def _log(self, level: str, msg: str) -> None:
        """统一日志输出"""
        getattr(logger, level, logger.info)(msg)
        if self.log_callback:
            self.log_callback(level, msg)

    def _emit_result(self, result: ScanResult) -> None:
        if self.result_callback:
            self.result_callback(result)

    def _check_cancel(self) -> bool:
        """检查取消信号，返回 True 表示已取消"""
        if self.cancel_event and self.cancel_event.is_set():
            return True
        return False

    def _load_progress(self) -> ScanProgress:
        resume_file = self.config.get_resume_file_path()
        if resume_file.exists():
            try:
                with open(resume_file, "r", encoding="utf-8") as f:
                    return ScanProgress.from_dict(json.load(f))
            except Exception:
                pass
        return ScanProgress()

    def _save_progress(self) -> None:
        resume_file = self.config.get_resume_file_path()
        try:
            with open(resume_file, "w", encoding="utf-8") as f:
                json.dump(self.progress_data.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log("error", f"保存进度失败: {e}")

    def _mark_processed(self, file_path: Path, modified: bool = False) -> None:
        file_key = str(file_path.relative_to(self.config.source_dir))

        self.progress_data.scanned_files.add(file_key)
        if modified:
            self.progress_data.modified_files.add(file_key)
            self.progress_data.unmodified_files.discard(file_key)
        else:
            self.progress_data.unmodified_files.add(file_key)
            self.progress_data.modified_files.discard(file_key)
        self._pending_saves.append(file_key)

        if len(self._pending_saves) >= 10:
            self._save_progress()
            self._pending_saves.clear()

    def get_pdf_files(self) -> list[Path]:
        scanned = self.progress_data.scanned_files
        try:
            # 如果指定了单文件列表，直接使用
            if self.config.source_files:
                return [
                    fp for fp in self.config.source_files
                    if fp.is_file() and str(fp.relative_to(self.config.source_dir)) not in scanned
                ]
            return [
                fp
                for fp in self.config.source_dir.glob("*.pdf")
                if fp.is_file() and str(fp.relative_to(self.config.source_dir)) not in scanned
            ]
        except Exception as e:
            self._log("error", f"扫描PDF文件出错: {e}")
            return []

    def preprocess_text(self, text: str) -> str:
        processed = text if self.config.case_sensitive else text.lower()
        if self.config.filter_spaces:
            processed = re.sub(r"[\s\t\r\n]+", "", processed)
        return processed

    def find_keyword_fuzzy(self, text: str, keyword: str) -> tuple[bool, int, str]:
        """模糊匹配关键词"""
        if not self.config.fuzzy_match:
            pos = text.find(keyword)
            return (True, pos, keyword) if pos != -1 else (False, -1, "")

        keyword_len = len(keyword)
        text_len = len(text)
        max_interfering = self.config.max_interfering_chars

        for i in range(text_len - keyword_len + 1):
            segment = text[i : i + keyword_len + max_interfering]
            matched = 0
            interfering = 0
            k_pos = 0

            for char in segment:
                if k_pos < keyword_len and char == keyword[k_pos]:
                    matched += 1
                    k_pos += 1
                else:
                    interfering += 1
                if interfering > max_interfering:
                    break

            if matched == keyword_len and interfering <= max_interfering:
                return True, i, segment

        return False, -1, ""

    def check_keywords(self, text: str, page_desc: str) -> bool:
        """检查关键词是否匹配"""
        processed_text = self.preprocess_text(text)
        found_keywords = set()
        matches_info = {}

        for kw in self.keywords:
            proc_kw = self.preprocess_text(kw)
            found, _, match = self.find_keyword_fuzzy(processed_text, proc_kw)

            if found:
                found_keywords.add(kw)
                matches_info[kw] = match

        condition_met = (
            len(found_keywords) == len(self.keywords)
            if self.config.search_logic == "AND"
            else len(found_keywords) > 0
        )

        status = "发现" if condition_met else "未发现"
        self._log("info", f"  [{page_desc}] 关键词检测结果: {status}")
        if condition_met:
            for kw in found_keywords:
                self._log("info", f"    - 发现 '{kw}': ...{matches_info[kw]}...")

        return condition_met

    def _ocr_page(self, page_num: int, img) -> tuple[int, bool]:
        """对单页进行 OCR 并检测关键词，返回 (页码, 是否命中)"""
        text = self.ocr_engine.recognize(img)

        if self.config.debug_mode:
            if text:
                self._log("debug", f"    第{page_num}页识别到 {len(text)} 个字符，预览: {text[:100]}...")
            else:
                self._log("warning", f"    第{page_num}页未识别到任何文本")

        matched = self.check_keywords(text, f"第{page_num}页")
        return page_num, matched

    def process_pdf(self, pdf_path: Path) -> ScanResult:
        """处理单个 PDF 文件"""
        start_time = time.time()
        self._log("info", f"\n[{pdf_path.name}] 开始处理...")

        if self._check_cancel():
            return ScanResult(
                file_name=pdf_path.name,
                file_path=pdf_path,
                status=FileStatus.SKIPPED,
                message="用户取消",
            )

        try:
            total_pages = self.pdf_engine.get_page_count(pdf_path)
        except Exception as e:
            self._log("error", f"  读取页数失败: {e}")
            self._mark_processed(pdf_path, False)
            return ScanResult(
                file_name=pdf_path.name,
                file_path=pdf_path,
                status=FileStatus.FAILED,
                message=f"读取页数失败: {e}",
            )

        self._log("info", f"  总页数: {total_pages}")
        pages_to_check = parse_pages_to_check(self.config.pages_to_check, total_pages)
        if not pages_to_check:
            self._log("warning", f"  没有有效的页面需要检查")
            self._mark_processed(pdf_path, False)
            return ScanResult(
                file_name=pdf_path.name,
                file_path=pdf_path,
                status=FileStatus.UNMODIFIED,
                message="无有效检查页面",
            )

        self._log("info", f"  将检查页面: {pages_to_check}")

        # 渲染页面为图片
        images = self.pdf_engine.render_pages(pdf_path, pages_to_check, self.config.dpi)
        if not images:
            self._log("error", f"  PDF转图片失败")
            self._mark_processed(pdf_path, False)
            return ScanResult(
                file_name=pdf_path.name,
                file_path=pdf_path,
                status=FileStatus.FAILED,
                message="PDF转图片失败",
            )

        # OCR 检测（支持页面级并发）
        matched_pages = []
        if len(images) > 1 and self.config.ocr_max_workers > 1:
            with ThreadPoolExecutor(max_workers=self.config.ocr_max_workers) as executor:
                futures = {
                    executor.submit(self._ocr_page, page_num, img): page_num
                    for page_num, img in images
                }
                for future in as_completed(futures):
                    if self._check_cancel():
                        for f in futures:
                            f.cancel()
                        return ScanResult(
                            file_name=pdf_path.name,
                            file_path=pdf_path,
                            status=FileStatus.SKIPPED,
                            message="用户取消",
                        )
                    page_num, matched = future.result()
                    if matched:
                        matched_pages.append(page_num)
        else:
            for page_num, img in images:
                if self._check_cancel():
                    return ScanResult(
                        file_name=pdf_path.name,
                        file_path=pdf_path,
                        status=FileStatus.SKIPPED,
                        message="用户取消",
                    )
                page_num, matched = self._ocr_page(page_num, img)
                if matched:
                    matched_pages.append(page_num)

        # 处理结果
        file_modified = False

        if matched_pages:
            self._log("info", f"  -> 发现匹配页面: {matched_pages}")

            # 删除匹配页
            if not self.config.dry_run:
                success = self.pdf_engine.delete_pages(pdf_path, matched_pages)
                if success:
                    file_modified = True
                    self._log("info", f"  已删除匹配页: {matched_pages}")
                else:
                    self._log("warning", f"  删除匹配页失败")

            self._mark_processed(pdf_path, file_modified)
            result = ScanResult(
                file_name=pdf_path.name,
                file_path=pdf_path,
                status=FileStatus.MODIFIED if file_modified else FileStatus.UNMODIFIED,
                matched_pages=matched_pages,
                total_pages=total_pages,
                message=f"删除匹配页 {matched_pages}" if file_modified else "未删除",
                elapsed_seconds=round(time.time() - start_time, 2),
            )
            self._emit_result(result)
            return result

        else:
            self._log("info", f"  -> 未找到匹配页面")
            self._mark_processed(pdf_path, file_modified)
            result = ScanResult(
                file_name=pdf_path.name,
                file_path=pdf_path,
                status=FileStatus.UNMODIFIED,
                total_pages=total_pages,
                message="无匹配页",
                elapsed_seconds=round(time.time() - start_time, 2),
            )
            self._emit_result(result)
            return result

    def run(self) -> list[ScanResult]:
        """运行完整扫描流程"""
        files = self.get_pdf_files()
        total = len(files)
        results = []

        if total == 0:
            self._log("info", "没有发现新的未处理PDF文件。")
            return results

        self._log("info", f"\n本次共发现 {total} 个新文件，准备开始工作...")

        try:
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = {executor.submit(self.process_pdf, fp): fp for fp in files}
                completed = 0

                for future in as_completed(futures):
                    if self.cancel_event and self.cancel_event.is_set():
                        for f in futures:
                            f.cancel()
                        self._log("info", "扫描已取消")
                        break

                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        fp = futures[future]
                        self._log("error", f"处理 {fp.name} 时异常: {e}")
                        results.append(ScanResult(
                            file_name=fp.name,
                            file_path=fp,
                            status=FileStatus.FAILED,
                            message=str(e),
                        ))

                    completed += 1
        finally:
            self._save_progress()

        # 所有文件处理完成后，自动删除进度文件
        if not self.get_pdf_files():
            resume_file = self.config.get_resume_file_path()
            if resume_file.exists():
                try:
                    resume_file.unlink()
                    self._log("info", "所有文件已处理完成，已自动删除进度文件")
                except Exception as e:
                    self._log("warning", f"删除进度文件失败: {e}")

        self._log("info", "\n" + "=" * 50)
        self._log("info", "=== 扫描完成 ===")
        return results
