"""
rename 子命令 — 文件批量重命名
支持：序号格式化、查找替换、正则匹配、预览模式
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from commands import BaseCommand


class RenameCommand(BaseCommand):
    name = "rename"
    help_text = "文件批量重命名"
    description = "批量重命名文件，支持序号格式化、查找替换、正则匹配和预览模式"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        # 位置参数
        parser.add_argument(
            "paths",
            nargs="+",
            help="要重命名的文件或目录路径（支持通配符）",
        )

        # 重命名模式（互斥）
        mode_group = parser.add_mutually_exclusive_group(required=True)
        mode_group.add_argument(
            "--pattern", "-p",
            type=str,
            help='序号模式，用 {seq} 占位符。如 "IMG_{seq:03d}" → IMG_001, IMG_002 ...',
        )
        mode_group.add_argument(
            "--replace", "-r",
            type=str,
            help='查找替换，格式 "旧文本>新文本"。如 "IMG>Photo" 将 IMG 替换为 Photo',
        )
        mode_group.add_argument(
            "--regex",
            type=str,
            help='正则替换，格式 "正则>替换"。如 "(\\d{4})-(\\d{2})-(\\d{2})>$1$2$3"',
        )

        # 选项
        parser.add_argument(
            "--start", "-s",
            type=int,
            default=1,
            help="序号起始值（默认 1）",
        )
        parser.add_argument(
            "--step",
            type=int,
            default=1,
            help="序号步长（默认 1）",
        )
        parser.add_argument(
            "--sort",
            choices=["name", "time", "size"],
            default="name",
            help="排序方式：name=文件名, time=修改时间, size=文件大小（默认 name）",
        )
        parser.add_argument(
            "--reverse",
            action="store_true",
            help="倒序排列",
        )
        parser.add_argument(
            "--dry-run", "-n",
            action="store_true",
            help="预览模式，只显示变更不实际执行",
        )
        parser.add_argument(
            "--include-ext",
            type=str,
            help="仅包含指定扩展名，逗号分隔（如 jpg,png）",
        )
        parser.add_argument(
            "--exclude-ext",
            type=str,
            help="排除指定扩展名，逗号分隔（如 txt,md）",
        )
        parser.add_argument(
            "--recursive",
            action="store_true",
            help="递归处理子目录中的文件",
        )

    def execute(self, args: argparse.Namespace) -> None:
        # 收集文件
        files = self._collect_files(args)
        if not files:
            print("  没有找到匹配的文件。")
            return

        # 排序
        files = self._sort_files(files, args)

        # 过滤扩展名
        files = self._filter_by_ext(files, args)

        if not files:
            print("  过滤后没有匹配的文件。")
            return

        # 生成重命名计划
        plan = self._build_plan(files, args)

        if not plan:
            print("  没有需要重命名的文件。")
            return

        # 展示计划
        self._print_plan(plan, args)

        # 执行或预览
        if args.dry_run:
            print(f"\n  [预览模式] 共 {len(plan)} 个文件将被重命名（未实际执行）")
        else:
            self._execute_plan(plan)
            print(f"\n  完成！共重命名 {len(plan)} 个文件")

    def _collect_files(self, args: argparse.Namespace) -> list[Path]:
        """收集所有待重命名的文件"""
        files: list[Path] = []
        for p in args.paths:
            path = Path(p)
            if path.is_file():
                files.append(path)
            elif path.is_dir():
                if args.recursive:
                    files.extend(f for f in path.rglob("*") if f.is_file())
                else:
                    files.extend(f for f in path.iterdir() if f.is_file())
            else:
                # 可能是通配符模式，尝试展开
                import glob
                matches = glob.glob(p, recursive=args.recursive)
                for m in matches:
                    mp = Path(m)
                    if mp.is_file():
                        files.append(mp)
        # 去重并保持顺序
        seen = set()
        unique = []
        for f in files:
            resolved = f.resolve()
            if resolved not in seen:
                seen.add(resolved)
                unique.append(f)
        return unique

    def _sort_files(self, files: list[Path], args: argparse.Namespace) -> list[Path]:
        """按指定方式排序"""
        key_map = {
            "name": lambda f: f.name.lower(),
            "time": lambda f: f.stat().st_mtime,
            "size": lambda f: f.stat().st_size,
        }
        key = key_map.get(args.sort, key_map["name"])
        return sorted(files, key=key, reverse=args.reverse)

    def _filter_by_ext(self, files: list[Path], args: argparse.Namespace) -> list[Path]:
        """按扩展名过滤"""
        result = files
        if args.include_ext:
            exts = set(e.strip().lower().lstrip(".") for e in args.include_ext.split(","))
            result = [f for f in result if f.suffix.lower().lstrip(".") in exts]
        if args.exclude_ext:
            exts = set(e.strip().lower().lstrip(".") for e in args.exclude_ext.split(","))
            result = [f for f in result if f.suffix.lower().lstrip(".") not in exts]
        return result

    def _build_plan(self, files: list[Path], args: argparse.Namespace) -> list[tuple[Path, Path]]:
        """构建重命名计划，返回 [(旧路径, 新路径), ...]"""
        plan = []

        if args.pattern:
            plan = self._plan_pattern(files, args)
        elif args.replace:
            plan = self._plan_replace(files, args)
        elif args.regex:
            plan = self._plan_regex(files, args)

        # 过滤掉不需要重命名的（新旧相同）
        plan = [(old, new) for old, new in plan if old.resolve() != new.resolve()]

        return plan

    def _plan_pattern(self, files: list[Path], args: argparse.Namespace) -> list[tuple[Path, Path]]:
        """序号模式重命名"""
        plan = []
        seq = args.start
        for f in files:
            stem = f.stem
            suffix = f.suffix
            # 替换 {seq} 或 {seq:03d} 等格式
            pattern = args.pattern

            def _seq_replacer(match):
                fmt = match.group(1)
                if fmt:
                    return format(seq, fmt)
                return str(seq)

            new_name = re.sub(r"\{seq(?::([^}]+))?\}", _seq_replacer, pattern)
            new_name = new_name if suffix and "." in new_name else new_name + suffix
            # 如果 pattern 包含扩展名则保持，否则保留原扩展名
            if "." not in args.pattern:
                new_name = re.sub(r"\{seq(?::([^}]+))?\}", _seq_replacer, pattern) + suffix
            else:
                new_name = re.sub(r"\{seq(?::([^}]+))?\}", _seq_replacer, pattern)

            new_path = f.parent / new_name
            plan.append((f, new_path))
            seq += args.step

        return plan

    def _plan_replace(self, files: list[Path], args: argparse.Namespace) -> list[tuple[Path, Path]]:
        """查找替换重命名"""
        parts = args.replace.split(">", 1)
        if len(parts) != 2:
            print("  错误: --replace 格式应为 '旧文本>新文本'")
            return []
        old_text, new_text = parts
        plan = []
        for f in files:
            if old_text in f.name:
                new_name = f.name.replace(old_text, new_text)
                plan.append((f, f.parent / new_name))
        return plan

    def _plan_regex(self, files: list[Path], args: argparse.Namespace) -> list[tuple[Path, Path]]:
        """正则替换重命名"""
        parts = args.regex.split(">", 1)
        if len(parts) != 2:
            print("  错误: --regex 格式应为 '正则>替换'")
            return []
        pattern_str, replacement = parts
        try:
            regex = re.compile(pattern_str)
        except re.error as e:
            print(f"  错误: 无效的正则表达式: {e}")
            return []

        plan = []
        for f in files:
            new_name, count = regex.subn(replacement, f.name)
            if count > 0:
                plan.append((f, f.parent / new_name))
        return plan

    def _print_plan(self, plan: list[tuple[Path, Path]], args: argparse.Namespace) -> None:
        """打印重命名计划"""
        # 计算列宽
        old_names = [str(p.name) for p, _ in plan]
        new_names = [str(p.name) for _, p in plan]
        max_old = max(len(n) for n in old_names) if old_names else 20
        max_new = max(len(n) for n in new_names) if new_names else 20
        max_old = min(max_old, 50)
        max_new = min(max_new, 50)

        print(f"\n  {'旧文件名':<{max_old}}  →  {'新文件名':<{max_new}}")
        print(f"  {'-' * max_old}  →  {'-' * max_new}")
        for old, new in plan:
            old_display = old.name if len(old.name) <= max_old else "..." + old.name[-(max_old - 3):]
            new_display = new.name if len(new.name) <= max_new else "..." + new.name[-(max_new - 3):]
            print(f"  {old_display:<{max_old}}  →  {new_display:<{max_new}}")

    def _execute_plan(self, plan: list[tuple[Path, Path]]) -> None:
        """执行重命名"""
        errors = []
        for old_path, new_path in plan:
            try:
                old_path.rename(new_path)
            except OSError as e:
                errors.append((old_path, str(e)))

        if errors:
            print(f"\n  警告: {len(errors)} 个文件重命名失败:")
            for path, err in errors:
                print(f"    {path.name}: {err}")
