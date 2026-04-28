"""
pdf-dewatermark 子命令 — 去除 PDF 注释型水印
"""
from __future__ import annotations

import argparse
from pathlib import Path

from commands import BaseCommand
from core.pdf_engine import PDFEngine


class PdfDewatermarkCommand(BaseCommand):
    name = "pdf-dewatermark"
    help_text = "去除 PDF 注释型水印"
    description = "扫描 PDF 文件，查找并删除注释型水印（Watermark / Stamp）"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        # 源路径
        dir_group = parser.add_argument_group("路径配置")
        dir_group.add_argument("--source", type=str, required=True, help="源路径（PDF 文件或目录）")
        dir_group.add_argument("--recursive", action="store_true", help="递归扫描子目录")

        # 执行选项
        parser.add_argument("--dry-run", "-n", action="store_true", help="预览模式，只显示检测到的水印信息不删除")
        parser.add_argument("--no-backup", action="store_true", help="覆盖原文件时不创建 .bak 备份")

    def execute(self, args: argparse.Namespace) -> None:
        source = Path(args.source)
        if not source.exists():
            print(f"  错误: 路径不存在: {source}")
            return

        # 收集文件
        if source.is_file():
            if source.suffix.lower() != ".pdf":
                print(f"  错误: 不是 PDF 文件: {source}")
                return
            files = [source]
        elif args.recursive:
            files = sorted(f for f in source.rglob("*.pdf") if f.is_file())
        else:
            files = sorted(f for f in source.glob("*.pdf") if f.is_file())

        if not files:
            print("  没有找到 PDF 文件。")
            return

        engine = PDFEngine()
        total_removed = 0
        modified_count = 0
        failed_count = 0

        print(f"\n  扫描 {len(files)} 个 PDF 文件...\n")

        for i, pdf_path in enumerate(files, 1):
            try:
                # 检测水印
                watermarks = engine.analyze_annotation_watermarks(pdf_path)

                if not watermarks:
                    print(f"  [{i}/{len(files)}] {pdf_path.name} | 无水印")
                    continue

                # 统计类型
                type_counts: dict[str, int] = {}
                for w in watermarks:
                    type_counts[w["type"]] = type_counts.get(w["type"], 0) + 1

                type_summary = ", ".join(f"{k}:{v}" for k, v in type_counts.items())

                if args.dry_run:
                    print(f"  [{i}/{len(files)}] {pdf_path.name} | 发现 {len(watermarks)} 个水印 ({type_summary}) (预览)")
                else:
                    modified, removed, affected_pages, msg = engine.remove_annotation_watermarks(
                        pdf_path, backup=not args.no_backup
                    )
                    if modified:
                        modified_count += 1
                        total_removed += removed
                        print(f"  [{i}/{len(files)}] {pdf_path.name} | {msg} ({type_summary})")
                    else:
                        print(f"  [{i}/{len(files)}] {pdf_path.name} | {msg}")
            except Exception as e:
                failed_count += 1
                print(f"  [{i}/{len(files)}] {pdf_path.name} | 失败: {e}")

        # 汇总
        print(f"\n{'=' * 50}")
        if args.dry_run:
            print(f"  [预览] 共 {len(files)} 个文件")
        else:
            print(f"  完成！共 {len(files)} 个文件 | 已处理 {modified_count} 个 | 删除 {total_removed} 个水印注释", end="")
            if failed_count:
                print(f" | 失败 {failed_count} 个", end="")
            print()
        print(f"{'=' * 50}")
