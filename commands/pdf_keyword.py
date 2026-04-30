"""
pdf-keyword 子命令 — 删除 PDF 中包含指定关键词的页面
基于 OCR 识别 + 关键词匹配，支持多种 OCR 引擎
"""
from __future__ import annotations

import argparse
import logging
import signal
import threading
import unicodedata
from pathlib import Path

from commands import BaseCommand
from core.config import AppConfig
from core.models import FileStatus, ScanResult
from core.scanner import PDFScanner

STATUS_LABELS = {
    FileStatus.MODIFIED: "已修改",
    FileStatus.UNMODIFIED: "未修改",
    FileStatus.FAILED: "失败",
    FileStatus.SKIPPED: "已跳过",
}


def _display_width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def _pad(s: str, width: int) -> str:
    return s + " " * (width - _display_width(s))


def _truncate_by_width(s: str, max_width: int) -> str:
    """按显示宽度截断字符串，超出部分以 .. 结尾"""
    width = 0
    result = []
    for char in s:
        char_width = 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
        if width + char_width > max_width - 2:
            result.append("..")
            break
        result.append(char)
        width += char_width
    return "".join(result)


def print_results(results: list[ScanResult]):
    if not results:
        return

    COL_NAME, COL_STATUS, COL_KP, COL_TP, COL_ET = 30, 10, 10, 8, 8

    def row(*cols_with_width):
        return "  " + " ".join(_pad(s, w) for s, w in cols_with_width)

    print(f"\n{'=' * 75}")
    print("  扫描结果")
    print(f"{'=' * 75}")
    print(row(("文件名", COL_NAME), ("状态", COL_STATUS), ("关键词页", COL_KP), ("总页数", COL_TP), ("耗时", COL_ET)))
    print(row(("-" * COL_NAME, COL_NAME), ("-" * COL_STATUS, COL_STATUS), ("-" * COL_KP, COL_KP), ("-" * COL_TP, COL_TP), ("-" * COL_ET, COL_ET)))

    for r in results:
        status_str = STATUS_LABELS.get(r.status, str(r.status))
        kp = str(r.matched_pages) if r.matched_pages else "-"
        tp = str(r.total_pages) if r.total_pages else "-"
        et = f"{r.elapsed_seconds}s" if r.elapsed_seconds else "-"
        name = _truncate_by_width(r.file_name, COL_NAME)
        print(row((name, COL_NAME), (status_str, COL_STATUS), (kp, COL_KP), (tp, COL_TP), (et, COL_ET)))

    modified = sum(1 for r in results if r.status == FileStatus.MODIFIED)
    unmodified = sum(1 for r in results if r.status == FileStatus.UNMODIFIED)
    failed = sum(1 for r in results if r.status == FileStatus.FAILED)
    skipped = sum(1 for r in results if r.status == FileStatus.SKIPPED)

    print(f"{'=' * 75}")
    print(f"  总计: {len(results)} 个文件 | 已修改: {modified} | 未修改: {unmodified} | 失败: {failed} | 跳过: {skipped}")
    print(f"{'=' * 75}")


class PdfKeywordCommand(BaseCommand):
    name = "pdf-keyword"
    help_text = "删除 PDF 中包含指定关键词的页面"
    description = "通过 OCR 识别 PDF 页面文本，自动删除包含指定关键词的页面"

    def __init__(self):
        self._completed = 0
        self._total = 0
        self._print_lock = threading.Lock()
        self._log_level = 0

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        # 源路径
        dir_group = parser.add_argument_group("路径配置")
        dir_group.add_argument("--source", type=str, help="源路径（PDF 文件或目录）")

        # 关键词
        kw_group = parser.add_argument_group("关键词配置")
        kw_group.add_argument("--keywords", type=str, help="关键词，逗号分隔（如: 出版发行,版权,侵权）")
        kw_group.add_argument("--search-logic", choices=["AND", "OR"], help="关键词搜索逻辑")
        kw_group.add_argument("--case-sensitive", action="store_true", default=None, help="区分大小写")
        kw_group.add_argument("--pages-to-check", type=str, help="检查页面范围（如: 2,-1 或 2:5）")

        parser.add_argument("--dry-run", "-n", action="store_true", help="预览模式，只显示结果不实际删除")
        parser.add_argument("--debug", action="store_true", default=None, help="调试模式")

        # OCR
        ocr_group = parser.add_argument_group("OCR 配置")
        ocr_group.add_argument("--ocr-mode", choices=["local", "baidu", "volc", "iflytek"], help="OCR 识别模式")
        ocr_group.add_argument("--ocr-accuracy", choices=["general_basic", "accurate_basic", "general", "accurate"], help="OCR 识别精度")
        ocr_group.add_argument("--ocr-lang", type=str, help="OCR 语言（如: chi_sim, eng）")
        ocr_group.add_argument("--dpi", type=int, help="渲染 DPI（默认 150）")
        ocr_group.add_argument("--no-filter-spaces", action="store_true", default=None, help="不过滤空格")
        ocr_group.add_argument("--no-fuzzy-match", action="store_true", default=None, help="禁用模糊匹配")
        ocr_group.add_argument("--max-interfering-chars", type=int, help="模糊匹配允许的最大干扰字符数")

        # 并发
        conc_group = parser.add_argument_group("并发配置")
        conc_group.add_argument("--max-workers", type=int, help="文件并发数（默认 4）")
        conc_group.add_argument("--ocr-max-workers", type=int, help="OCR 并发数（默认 2）")

        # 杂项
        parser.add_argument("--output", type=str, help="输出路径（仅单文件时有效，默认覆盖原文件）")
        parser.add_argument("--no-backup", action="store_true", help="覆盖原文件时不创建 .bak 备份")
        parser.add_argument("--save-config", action="store_true", help="保存当前配置到 settings.json")
        parser.add_argument("--reset-progress", action="store_true", help="重置扫描进度（重新扫描所有文件）")

    def _log_handler(self, level: str, msg: str):
        level_priority = {"error": 0, "warning": 1, "info": 2, "debug": 3}
        if level_priority.get(level, 2) <= self._log_level:
            label = {"error": "错误", "warning": "警告", "info": "信息", "debug": "调试"}.get(level, level)
            with self._print_lock:
                print(f"  [{label}] {msg}")

    def _result_handler(self, result: ScanResult):
        with self._print_lock:
            self._completed += 1
            status = STATUS_LABELS.get(result.status, str(result.status))
            parts = [f"[{self._completed}/{self._total}]", result.file_name, status]
            if result.matched_pages:
                parts.append(f"关键词页:{result.matched_pages}")
            if result.elapsed_seconds:
                parts.append(f"{result.elapsed_seconds}s")
            if result.status == FileStatus.FAILED and result.message:
                parts.append(result.message)
            print("  " + " | ".join(parts))

    def execute(self, args: argparse.Namespace) -> None:
        # 加载配置
        config = AppConfig()
        config = self._apply_cli_args(config, args)

        # 处理 source 路径（支持单文件和目录）
        source_path = config.source_path or config.source_dir
        output_path = Path(args.output) if args.output else None

        if source_path.is_file():
            if source_path.suffix.lower() != ".pdf":
                print(f"  错误: 不是 PDF 文件: {source_path}")
                return
            if output_path and output_path.is_dir():
                output_path = output_path / source_path.name
            config.source_dir = source_path.parent
            config.source_files = [source_path]
        elif source_path.is_dir():
            if output_path:
                print("  错误: --output 仅在处理单个文件时有效")
                return
            config.source_dir = source_path
            config.source_files = None
        else:
            print(f"  错误: 路径不存在: {source_path}")
            return

        # 日志级别
        if args.verbose:
            self._log_level = 2
        elif args.quiet:
            self._log_level = 0
        else:
            self._log_level = 1

        # 保存配置
        if args.save_config:
            try:
                config.save_settings()
                print("配置已保存到 settings.json")
            except Exception as e:
                print(f"保存配置失败: {e}")
            return

        # 验证配置
        errors = config.validate()
        if errors:
            print("配置错误:")
            for e in errors:
                print(f"  - {e}")
            return

        # 重置进度（在配置验证通过后执行）
        if args.reset_progress:
            progress_file = config.get_resume_file_path()
            if progress_file.exists():
                progress_file.unlink()
                print("已重置扫描进度")

        # 打印配置摘要
        action = "仅检测" if config.dry_run else "检测并删除"
        print(f"\n{'─' * 50}")
        print(f"  PDF 关键词页面扫描工具")
        print(f"{'─' * 50}")
        print(f"  源路径:    {source_path}")
        print(f"  输出路径:  {output_path or '覆盖原文件'}")
        print(f"  关键词:    {', '.join(config.keywords)}")
        print(f"  搜索逻辑:  {config.search_logic}")
        print(f"  检查页面:  {config.pages_to_check}")
        print(f"  OCR 模式:  {config.recognition_mode}")
        print(f"  操作模式:  {action}")
        print(f"  文件并发:  {config.max_workers}")
        print(f"  OCR 并发:  {config.ocr_max_workers}")
        print(f"  备份:      {'否' if args.no_backup else '是'}")
        print(f"{'─' * 50}\n")

        # Ctrl+C 取消
        cancel_event = threading.Event()

        def _signal_handler(sig, frame):
            print("\n  正在取消扫描...")
            cancel_event.set()

        signal.signal(signal.SIGINT, _signal_handler)

        # 创建扫描器
        scanner = PDFScanner(config=config, cancel_event=cancel_event, backup=not args.no_backup)
        scanner.log_callback = self._log_handler
        scanner.result_callback = self._result_handler

        # 预计算文件列表，避免 get_pdf_files() 二次扫描产生不一致
        pdf_files = scanner.get_pdf_files()
        self._completed = 0
        self._total = len(pdf_files)
        config.source_files = pdf_files

        if self._total == 0:
            print("  没有发现新的未处理 PDF 文件。\n")
            return

        print(f"  开始扫描 {self._total} 个文件...\n")
        results = scanner.run(output_path=output_path)
        print_results(results)

    @staticmethod
    def _apply_cli_args(config: AppConfig, args: argparse.Namespace) -> AppConfig:
        _SIMPLE_MAP = {
            "source": ("source_path", lambda v: Path(v)),
            "search_logic": ("search_logic", None),
            "pages_to_check": ("pages_to_check", None),
            "ocr_mode": ("recognition_mode", None),
            "ocr_accuracy": ("ocr_accuracy", None),
            "ocr_lang": ("ocr_lang", None),
            "dpi": ("dpi", None),
            "max_interfering_chars": ("max_interfering_chars", None),
            "max_workers": ("max_workers", None),
            "ocr_max_workers": ("ocr_max_workers", None),
        }
        for arg_name, (attr, transform) in _SIMPLE_MAP.items():
            val = getattr(args, arg_name, None)
            if val is not None:
                setattr(config, attr, transform(val) if transform else val)

        if args.keywords is not None:
            config.keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]

        _FLAG_MAP = {
            "case_sensitive": ("case_sensitive", True),
            "dry_run": ("dry_run", True),
            "debug": ("debug_mode", True),
            "no_filter_spaces": ("filter_spaces", False),
            "no_fuzzy_match": ("fuzzy_match", False),
        }
        for arg_name, (attr, value) in _FLAG_MAP.items():
            val = getattr(args, arg_name, None)
            if val is not None and val:
                setattr(config, attr, value)

        return config
