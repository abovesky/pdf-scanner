"""
pdf-decrypt 子命令 — 清除 PDF 密码保护
独立轻量命令，直接使用 PDFEngine，无需 OCR
"""
from __future__ import annotations

import argparse
from pathlib import Path

from commands import BaseCommand
from core.pdf_engine import PDFEngine


class PdfDecryptCommand(BaseCommand):
    name = "pdf-decrypt"
    help_text = "清除 PDF 密码保护"
    description = "移除 PDF 文件的密码保护，保存为无密码的 PDF"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        # 源路径
        dir_group = parser.add_argument_group("路径配置")
        dir_group.add_argument("--source", type=str, required=True, help="源路径（PDF 文件或目录）")
        dir_group.add_argument("--output", type=str, help="输出路径（仅单文件时有效，默认覆盖原文件）")

        # 密码
        pw_group = parser.add_argument_group("密码配置")
        pw_group.add_argument("--password", type=str, default="", help="PDF 用户密码（默认为空）")

        # 执行选项
        parser.add_argument("--recursive", action="store_true", help="递归扫描子目录")
        parser.add_argument("--dry-run", "-n", action="store_true", help="预览模式，只显示结果不实际操作")
        parser.add_argument("--no-backup", action="store_true", help="覆盖原文件时不创建 .bak 备份")

    def execute(self, args: argparse.Namespace) -> None:
        source = Path(args.source)
        if not source.exists():
            print(f"  错误: 路径不存在: {source}")
            return

        output = Path(args.output) if args.output else None

        # 单文件 + 指定输出
        if source.is_file():
            if source.suffix.lower() != ".pdf":
                print(f"  错误: 不是 PDF 文件: {source}")
                return
            if output and output.is_dir():
                output = output / source.name
            self._process_file(source, args, output)
            return

        # 目录模式
        if output:
            print("  错误: --output 仅在处理单个文件时有效")
            return

        if args.recursive:
            files = sorted(f for f in source.rglob("*.pdf") if f.is_file())
        else:
            files = sorted(f for f in source.glob("*.pdf") if f.is_file())

        if not files:
            print("  没有找到 PDF 文件。")
            return

        engine = PDFEngine()
        encrypted_files = []

        print(f"\n  检查 {len(files)} 个 PDF 文件...\n")

        for pdf_path in files:
            try:
                if engine.is_encrypted(pdf_path):
                    encrypted_files.append(pdf_path)
            except Exception as e:
                print(f"  {pdf_path.name} | 检查失败: {e}")

        if not encrypted_files:
            print("  没有发现加密的 PDF 文件。")
            return

        print(f"  发现 {len(encrypted_files)} 个加密文件，开始处理...\n")
        success_count = 0
        failed_count = 0

        for i, pdf_path in enumerate(encrypted_files, 1):
            success, msg = self._process_file(pdf_path, args, None, index=i, total=len(encrypted_files))
            if success:
                success_count += 1
            else:
                failed_count += 1

        # 汇总
        print(f"\n{'=' * 50}")
        if args.dry_run:
            print(f"  [预览] 共 {len(encrypted_files)} 个加密文件")
        else:
            print(f"  完成！共 {len(encrypted_files)} 个加密文件 | 成功: {success_count} | 失败: {failed_count}")
        print(f"{'=' * 50}")

    def _process_file(
        self,
        pdf_path: Path,
        args: argparse.Namespace,
        output_path: Path | None = None,
        index: int = 1,
        total: int = 1,
    ) -> tuple[bool, str]:
        engine = PDFEngine()
        prefix = f"[{index}/{total}]" if total > 1 else ""

        try:
            is_encrypted = engine.is_encrypted(pdf_path)
        except Exception as e:
            print(f"  {prefix} {pdf_path.name} | 检查失败: {e}")
            return False, str(e)

        if not is_encrypted:
            print(f"  {prefix} {pdf_path.name} | 未加密，跳过")
            return False, "未加密"

        if args.dry_run:
            print(f"  {prefix} {pdf_path.name} | 已加密 (预览)")
            return False, "预览"

        success, msg = engine.remove_password(
            pdf_path,
            password=args.password,
            output_path=output_path,
            backup=not args.no_backup,
        )

        if success:
            print(f"  {prefix} {pdf_path.name} | 密码已清除")
        else:
            print(f"  {prefix} {pdf_path.name} | 失败: {msg}")

        return success, msg
