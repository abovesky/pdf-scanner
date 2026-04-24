"""
PDF 版权页扫描工具 - CLI 入口
"""
import argparse
import logging
import signal
import sys
import threading
import unicodedata
from pathlib import Path

from core.config import AppConfig
from core.models import FileStatus, ScanResult
from core.scanner import PDFScanner

__version__ = "1.0.0"


STATUS_LABELS = {
    FileStatus.MODIFIED:   "已修改",
    FileStatus.UNMODIFIED: "未修改",
    FileStatus.FAILED:     "失败",
    FileStatus.SKIPPED:    "已跳过",
}

# 扫描过程中由 result_callback 实时打印，无需独立进度条
_completed = 0
_total = 0
_print_lock = threading.Lock()
_log_level = 0  # 0=error, 1=warning, 2=info, 3=debug


def _log_handler(level: str, msg: str):
    """scanner 回调 → 根据 verbose/quiet 设置输出"""
    level_priority = {"error": 0, "warning": 1, "info": 2, "debug": 3}
    if level_priority.get(level, 2) <= _log_level:
        label = {"error": "错误", "warning": "警告", "info": "信息", "debug": "调试"}.get(level, level)
        print(f"  [{label}] {msg}")


def _result_handler(result: ScanResult):
    """单文件完成 → 实时打印一行紧凑结果"""
    global _completed
    with _print_lock:
        _completed += 1
        status = STATUS_LABELS.get(result.status, str(result.status))
        parts = [f"[{_completed}/{_total}]", result.file_name, status]
        if result.copyright_pages:
            parts.append(f"版权页:{result.copyright_pages}")
        if result.blank_pages_removed:
            parts.append(f"删空白页:{result.blank_pages_removed}")
        if result.elapsed_seconds:
            parts.append(f"{result.elapsed_seconds}s")
        if result.status == FileStatus.FAILED and result.message:
            parts.append(result.message)
        print("  " + " | ".join(parts))


# ── 结果展示 ──────────────────────────────────────────────

def _display_width(s: str) -> int:
    """计算字符串在终端的显示宽度（CJK 字符占 2 列）"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def _pad(s: str, width: int) -> str:
    """按显示宽度右填充空格"""
    return s + " " * (width - _display_width(s))


def print_results(results: list[ScanResult]):
    """打印扫描结果表格"""
    if not results:
        return

    # 列宽定义（按显示列数）
    COL_NAME, COL_STATUS, COL_CP, COL_BP, COL_TP, COL_ET = 30, 10, 10, 8, 8, 8

    def row(*cols_with_width):
        return "  " + " ".join(_pad(s, w) for s, w in cols_with_width)

    print(f"\n{'=' * 80}")
    print("  扫描结果")
    print(f"{'=' * 80}")
    print(row(("文件名", COL_NAME), ("状态", COL_STATUS), ("版权页", COL_CP), ("空白页", COL_BP), ("总页数", COL_TP), ("耗时", COL_ET)))
    print(row(("-" * COL_NAME, COL_NAME), ("-" * COL_STATUS, COL_STATUS), ("-" * COL_CP, COL_CP), ("-" * COL_BP, COL_BP), ("-" * COL_TP, COL_TP), ("-" * COL_ET, COL_ET)))

    for r in results:
        status_str = STATUS_LABELS.get(r.status, str(r.status))
        cp = str(r.copyright_pages) if r.copyright_pages else "-"
        bp = str(r.blank_pages_removed) if r.blank_pages_removed else "-"
        tp = str(r.total_pages) if r.total_pages else "-"
        et = f"{r.elapsed_seconds}s" if r.elapsed_seconds else "-"
        name = r.file_name[:28] + ".." if len(r.file_name) > 30 else r.file_name
        print(row((name, COL_NAME), (status_str, COL_STATUS), (cp, COL_CP), (bp, COL_BP), (tp, COL_TP), (et, COL_ET)))

    # 统计
    modified = sum(1 for r in results if r.status == FileStatus.MODIFIED)
    unmodified = sum(1 for r in results if r.status == FileStatus.UNMODIFIED)
    failed = sum(1 for r in results if r.status == FileStatus.FAILED)
    skipped = sum(1 for r in results if r.status == FileStatus.SKIPPED)

    print(f"{'=' * 80}")
    print(f"  总计: {len(results)} 个文件 | 已修改: {modified} | 未修改: {unmodified} | 失败: {failed} | 跳过: {skipped}")
    print(f"{'=' * 80}")


# ── 参数解析 ──────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf-scanner",
        description="PDF 版权页扫描工具 — 自动识别并删除 PDF 中的版权页",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  # 使用 settings.json 中的配置运行
  python main.py

  # 指定源目录和关键词
  python main.py --source-dir ./pdfs --keywords "出版发行,版权"

  # 仅检测不删除
  python main.py --source-dir ./pdfs --no-remove-copyright --no-remove-blank

  # 使用火山引擎 OCR
  python main.py --source-dir ./pdfs --ocr-mode volc
""",
    )

    # ── 目录 ──
    dir_group = parser.add_argument_group("目录配置")
    dir_group.add_argument("--source-dir", type=str, help="源目录（包含 PDF 文件）")
    dir_group.add_argument("--backup-dir", type=str, help="备份目录（留空则自动备份）")

    # ── 扫描 ──
    scan_group = parser.add_argument_group("扫描参数")
    scan_group.add_argument("--keywords", type=str, help="关键词，逗号分隔（如: 出版发行,版权,侵权）")
    scan_group.add_argument("--search-logic", choices=["AND", "OR"], help="关键词搜索逻辑")
    scan_group.add_argument("--case-sensitive", action="store_true", default=None, help="区分大小写")
    scan_group.add_argument("--pages-to-check", type=str, help="检查页面范围（如: 2,-1 或 2:5）")
    scan_group.add_argument("--no-remove-copyright", action="store_true", default=None, help="不删除版权页")
    scan_group.add_argument("--no-remove-blank", action="store_true", default=None, help="不删除空白页")
    scan_group.add_argument("--debug", action="store_true", default=None, help="调试模式")

    # ── OCR ──
    ocr_group = parser.add_argument_group("OCR 配置")
    ocr_group.add_argument("--ocr-mode", choices=["local", "baidu", "volc", "iflytek"], help="OCR 识别模式")
    ocr_group.add_argument("--ocr-accuracy", choices=["general_basic", "accurate_basic", "general", "accurate"], help="OCR 识别精度")
    ocr_group.add_argument("--ocr-lang", type=str, help="OCR 语言（如: chi_sim, eng）")
    ocr_group.add_argument("--dpi", type=int, help="渲染 DPI（默认 300）")
    ocr_group.add_argument("--no-filter-spaces", action="store_true", default=None, help="不过滤空格")
    ocr_group.add_argument("--no-fuzzy-match", action="store_true", default=None, help="禁用模糊匹配")
    ocr_group.add_argument("--max-interfering-chars", type=int, help="模糊匹配允许的最大干扰字符数")

    # ── 并发 ──
    conc_group = parser.add_argument_group("并发配置")
    conc_group.add_argument("--max-workers", type=int, help="文件并发数（默认 4）")
    conc_group.add_argument("--ocr-max-workers", type=int, help="OCR 并发数（默认 2）")

    # ── 其他 ──
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--verbose", action="store_true", help="显示详细日志（warning/info）")
    parser.add_argument("--quiet", action="store_true", help="静默模式，仅显示错误")
    parser.add_argument("--save-config", action="store_true", help="保存当前配置到 settings.json")
    parser.add_argument("--reset-progress", action="store_true", help="重置扫描进度（重新扫描所有文件）")

    return parser


def apply_cli_args(config: AppConfig, args: argparse.Namespace) -> AppConfig:
    """将 CLI 参数覆盖到 AppConfig（仅覆盖显式指定的参数）"""
    # 简单映射：arg_name -> (config_attr, transform)
    _SIMPLE_MAP = {
        "source_dir": ("source_dir", lambda v: Path(v)),
        "backup_dir": ("backup_dir", lambda v: Path(v)),
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
        if val:
            setattr(config, attr, transform(val) if transform else val)

    # 关键词特殊处理
    if args.keywords:
        config.keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]

    # 布尔标志（--no-xxx 形式取反）
    _FLAG_MAP = {
        "case_sensitive": ("case_sensitive", True),
        "no_remove_copyright": ("remove_copyright_pages", False),
        "no_remove_blank": ("remove_blank_pages", False),
        "debug": ("debug_mode", True),
        "no_filter_spaces": ("filter_spaces", False),
        "no_fuzzy_match": ("fuzzy_match", False),
    }
    for arg_name, (attr, value) in _FLAG_MAP.items():
        val = getattr(args, arg_name, None)
        if val is not None and val:
            setattr(config, attr, value)

    return config


# ── 主流程 ──────────────────────────────────────────────

def main():
    parser = build_parser()
    args = parser.parse_args()

    # 加载配置（.env + settings.json）
    config = AppConfig()
    config = apply_cli_args(config, args)

    # 日志级别
    global _log_level
    if args.verbose:
        _log_level = 2  # info
    elif args.quiet:
        _log_level = 0  # error only
    else:
        _log_level = 1  # warning

    # 保存配置
    if args.save_config:
        try:
            config.save_settings()
            print("配置已保存到 settings.json")
        except Exception as e:
            print(f"保存配置失败: {e}")
        return

    # 重置进度
    if args.reset_progress:
        progress_file = config.get_resume_file_path()
        if progress_file.exists():
            progress_file.unlink()
            print("已重置扫描进度")

    # 验证配置
    errors = config.validate()
    if errors:
        print("配置错误:")
        for e in errors:
            print(f"  - {e}")
        return

    # 打印当前配置摘要
    print(f"\n{'─' * 50}")
    print(f"  PDF 版权页扫描工具 v{__version__}")
    print(f"{'─' * 50}")
    print(f"  源目录:    {config.source_dir}")
    print(f"  备份目录:  {config.backup_dir or '(自动)'}")
    print(f"  关键词:    {', '.join(config.keywords)}")
    print(f"  搜索逻辑:  {config.search_logic}")
    print(f"  检查页面:  {config.pages_to_check}")
    print(f"  OCR 模式:  {config.recognition_mode}")
    print(f"  删除版权页: {'是' if config.remove_copyright_pages else '否'}")
    print(f"  删除空白页: {'是' if config.remove_blank_pages else '否'}")
    print(f"  文件并发:  {config.max_workers}")
    print(f"  OCR 并发:  {config.ocr_max_workers}")
    print(f"{'─' * 50}\n")

    # Ctrl+C 取消
    cancel_event = threading.Event()

    def _signal_handler(sig, frame):
        print("\n  正在取消扫描...")
        cancel_event.set()

    signal.signal(signal.SIGINT, _signal_handler)

    # 创建扫描器
    scanner = PDFScanner(
        config=config,
        cancel_event=cancel_event,
    )
    scanner.log_callback = _log_handler
    scanner.result_callback = _result_handler

    # 初始化计数
    global _completed, _total
    _completed = 0
    _total = len(scanner.get_pdf_files())

    if _total == 0:
        print("  没有发现新的未处理 PDF 文件。\n")
        return

    # 执行扫描
    print(f"  开始扫描 {_total} 个文件...\n")
    results = scanner.run()

    # 展示结果
    print_results(results)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n  程序出错: {e}")
    finally:
        # 双击 exe 时防止窗口闪退
        if getattr(sys, "frozen", False):
            print()
            input("按回车键退出...")
