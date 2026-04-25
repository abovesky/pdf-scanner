"""
pdf-blank 子命令 — 删除 PDF 空白页
独立轻量命令，直接使用 PDFEngine，无需 OCR
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from commands import BaseCommand
from core.pdf_engine import PDFEngine


class PdfBlankCommand(BaseCommand):
    name = "pdf-blank"
    help_text = "删除 PDF 空白页"
    description = "扫描 PDF 文件，查找并删除空白页（仅基于文本分析，无需 OCR）"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        # 目录
        dir_group = parser.add_argument_group("目录配置")
        dir_group.add_argument("--source-dir", type=str, required=True, help="源目录（包含 PDF 文件）")
        dir_group.add_argument("--backup-dir", type=str, help="备份目录（留空则不备份）")

        # 扫描参数
        scan_group = parser.add_argument_group("扫描参数")
        scan_group.add_argument(
            "--min-text-length", type=int, default=10,
            help="空白页最小文本长度阈值，低于此值视为空白页（默认 10）",
        )
        scan_group.add_argument("--recursive", action="store_true", help="递归扫描子目录")

        # 执行选项
        parser.add_argument("--dry-run", "-n", action="store_true", help="预览模式，只显示结果不实际删除")

    def execute(self, args: argparse.Namespace) -> None:
        source = Path(args.source_dir)
        if not source.exists():
            print(f"  错误: 源目录不存在: {source}")
            return

        backup_dir = Path(args.backup_dir) if args.backup_dir else None

        # 收集文件
        if args.recursive:
            files = sorted(source.rglob("*.pdf"))
        else:
            files = sorted(source.glob("*.pdf"))
        files = [f for f in files if f.is_file()]

        if not files:
            print("  没有找到 PDF 文件。")
            return

        engine = PDFEngine()
        total_blank = 0
        modified_count = 0
        failed_count = 0

        print(f"\n  扫描 {len(files)} 个 PDF 文件...\n")

        for i, pdf_path in enumerate(files, 1):
            try:
                blank_pages = engine.find_blank_pages(pdf_path, args.min_text_length)
                if blank_pages:
                    modified_count += 1
                    total_blank += len(blank_pages)
                    if args.dry_run:
                        print(f"  [{i}/{len(files)}] {pdf_path.name} | 空白页: {blank_pages} (预览)")
                    else:
                        # 删除空白页（PDFEngine.delete_pages 内部处理备份）
                        success = engine.delete_pages(pdf_path, blank_pages, backup_dir=backup_dir)
                        if success:
                            print(f"  [{i}/{len(files)}] {pdf_path.name} | 空白页: {blank_pages} -> 已删除")
                        else:
                            print(f"  [{i}/{len(files)}] {pdf_path.name} | 空白页: {blank_pages} -> 删除失败")
                            failed_count += 1
                else:
                    print(f"  [{i}/{len(files)}] {pdf_path.name} | 无空白页")
            except Exception as e:
                failed_count += 1
                print(f"  [{i}/{len(files)}] {pdf_path.name} | 失败: {e}")

        # 汇总
        print(f"\n{'=' * 50}")
        if args.dry_run:
            print(f"  [预览] 共 {len(files)} 个文件 | {modified_count} 个含空白页 | 共 {total_blank} 页空白页")
        else:
            print(f"  完成！共 {len(files)} 个文件 | 已处理 {modified_count} 个 | 删除 {total_blank} 页空白页", end="")
            if failed_count:
                print(f" | 失败 {failed_count} 个", end="")
            print()
        print(f"{'=' * 50}")
