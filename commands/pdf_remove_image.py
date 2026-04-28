"""
pdf-remove-image 子命令 — 按条件删除 PDF 嵌入图片
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from commands import BaseCommand
from core.pdf_engine import ImageMatchCriteria, PDFEngine


class PdfRemoveImageCommand(BaseCommand):
    name = "pdf-remove-image"
    help_text = "按条件删除 PDF 中的嵌入图片"
    description = "通过 MD5、尺寸、格式、覆盖率等多种条件匹配并删除 PDF 中的嵌入图片（如水印）"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        # 匹配条件
        match_group = parser.add_argument_group("匹配条件（至少指定一项）")
        match_group.add_argument("--md5", action="append", help="目标图片 MD5 哈希值，可多次传入")
        match_group.add_argument("--image", action="append", help="水印图片文件路径，自动计算 MD5，可多次传入")
        match_group.add_argument("--min-width", type=int, help="最小原始像素宽度")
        match_group.add_argument("--max-width", type=int, help="最大原始像素宽度")
        match_group.add_argument("--min-height", type=int, help="最小原始像素高度")
        match_group.add_argument("--max-height", type=int, help="最大原始像素高度")
        match_group.add_argument("--min-size", type=str, help="最小嵌入大小（支持 K/M 单位）")
        match_group.add_argument("--max-size", type=str, help="最大嵌入大小（支持 K/M 单位）")
        match_group.add_argument("--format", action="append", help="图片格式过滤（png/jpeg 等），可多次传入")
        match_group.add_argument("--min-coverage", type=float, help="最小页面覆盖率（0.0-1.0）")
        match_group.add_argument("--max-coverage", type=float, help="最大页面覆盖率（0.0-1.0）")
        match_group.add_argument("--has-alpha", action="store_true", help="匹配带透明通道的图片")

        # 路径配置
        path_group = parser.add_argument_group("路径配置")
        path_group.add_argument("--source", type=str, required=True, help="源路径（PDF 文件或目录）")
        path_group.add_argument("--recursive", action="store_true", help="递归扫描子目录")

        # 执行选项
        parser.add_argument("--dry-run", "-n", action="store_true", help="预览模式，只显示匹配到的图片信息不删除")
        parser.add_argument("--no-backup", action="store_true", help="覆盖原文件时不创建 .bak 备份")

    def _build_criteria(self, args: argparse.Namespace) -> ImageMatchCriteria:
        md5s: list[str] = []
        pixel_md5s: list[str] = []
        if args.md5:
            md5s.extend(m.lower() for m in args.md5)
        if args.image:
            for img_path_str in args.image:
                img_path = Path(img_path_str)
                if not img_path.exists():
                    raise FileNotFoundError(f"图片文件不存在: {img_path}")
                raw = img_path.read_bytes()
                # 像素 MD5（不受重编码影响，统一 RGB 模式）
                try:
                    from PIL import Image
                    import io
                    pil_img = Image.open(io.BytesIO(raw))
                    pil_img = pil_img.convert("RGB")
                    pixel_md5s.append(hashlib.md5(pil_img.tobytes()).hexdigest().lower())
                except Exception:
                    pass

        formats: list[str] | None = None
        if args.format:
            fmt_map = {"jpg": "jpeg"}
            formats = [fmt_map.get(f.lower(), f.lower()) for f in args.format]

        engine = PDFEngine()
        min_size = engine._parse_size_str(args.min_size) if args.min_size else None
        max_size = engine._parse_size_str(args.max_size) if args.max_size else None

        return ImageMatchCriteria(
            md5s=md5s if md5s else None,
            pixel_md5s=pixel_md5s if pixel_md5s else None,
            min_width=args.min_width,
            max_width=args.max_width,
            min_height=args.min_height,
            max_height=args.max_height,
            min_size=min_size,
            max_size=max_size,
            formats=formats,
            min_coverage=args.min_coverage,
            max_coverage=args.max_coverage,
            has_alpha=True if args.has_alpha else None,
        )

    def _validate_criteria(self, criteria: ImageMatchCriteria, dry_run: bool = False) -> None:
        has_any = (
            criteria.md5s is not None
            or criteria.pixel_md5s is not None
            or criteria.min_width is not None
            or criteria.max_width is not None
            or criteria.min_height is not None
            or criteria.max_height is not None
            or criteria.min_size is not None
            or criteria.max_size is not None
            or criteria.formats is not None
            or criteria.min_coverage is not None
            or criteria.max_coverage is not None
            or criteria.has_alpha is not None
        )
        if not has_any and not dry_run:
            raise ValueError("至少指定一项匹配条件（--md5、--image、尺寸、大小、格式、覆盖率、--has-alpha），或使用 --dry-run 查看所有图片")

    def _print_images(self, images: list) -> None:
        if not images:
            print("  未找到图片。")
            return
        print(f"  {'xref':>6} {'page':>5} {'size':>10} {'format':>8} {'dims':>12} {'coverage':>10} {'alpha':>6} {'md5':>34}")
        print("  " + "-" * 95)
        for img in images:
            cov_str = f"{img.coverage:.2%}" if img.coverage is not None else "N/A"
            alpha_str = "yes" if img.has_alpha else "no"
            dims = f"{img.width}x{img.height}"
            size_str = self._human_readable_size(img.size)
            print(f"  {img.xref:>6} {img.page:>5} {size_str:>10} {img.format:>8} {dims:>12} {cov_str:>10} {alpha_str:>6} {img.md5:>34}")

    @staticmethod
    def _human_readable_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}K"
        else:
            return f"{size_bytes / (1024 * 1024):.1f}M"

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

        try:
            criteria = self._build_criteria(args)
            self._validate_criteria(criteria, args.dry_run)
        except Exception as e:
            print(f"  参数错误: {e}")
            return

        engine = PDFEngine()
        total_instances = 0
        modified_count = 0
        failed_count = 0

        print(f"\n  扫描 {len(files)} 个 PDF 文件...\n")

        for i, pdf_path in enumerate(files, 1):
            try:
                # 加密检测
                if engine.is_encrypted(pdf_path):
                    print(f"  [{i}/{len(files)}] {pdf_path.name} | 文件已加密，请先使用 pdf-decrypt 解密")
                    failed_count += 1
                    continue

                # 分析图片
                images = engine.analyze_images(pdf_path)
                if args.dry_run:
                    # dry-run 模式下如果没有指定条件，列出所有图片
                    has_criteria = (
                        criteria.md5s is not None
                        or criteria.pixel_md5s is not None
                        or criteria.min_width is not None
                        or criteria.max_width is not None
                        or criteria.min_height is not None
                        or criteria.max_height is not None
                        or criteria.min_size is not None
                        or criteria.max_size is not None
                        or criteria.formats is not None
                        or criteria.min_coverage is not None
                        or criteria.max_coverage is not None
                        or criteria.has_alpha is not None
                    )
                    matched = images if not has_criteria else [img for img in images if engine._image_matches(img, criteria)]
                    if not matched:
                        print(f"  [{i}/{len(files)}] {pdf_path.name} | 无图片")
                        continue
                    print(f"  [{i}/{len(files)}] {pdf_path.name} | 发现 {len(matched)} 个图片 (预览)")
                    self._print_images(matched)
                    continue
                else:
                    matched = [img for img in images if engine._image_matches(img, criteria)]

                if not matched:
                    print(f"  [{i}/{len(files)}] {pdf_path.name} | 无匹配图片")
                    continue

                modified, instances, _, msg = engine.remove_images_by_criteria(
                    pdf_path,
                    criteria,
                    backup=not args.no_backup,
                )
                if modified:
                    modified_count += 1
                    total_instances += instances
                    print(f"  [{i}/{len(files)}] {pdf_path.name} | {msg}")
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
            print(f"  完成！共 {len(files)} 个文件 | 已处理 {modified_count} 个 | 删除 {total_instances} 个图片实例", end="")
            if failed_count:
                print(f" | 失败 {failed_count} 个", end="")
            print()
        print(f"{'=' * 50}")
