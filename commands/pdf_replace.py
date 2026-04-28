"""
pdf-replace 子命令 — 按规则查找并替换 PDF 文本内容
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from commands import BaseCommand
from core.pdf_engine import PDFEngine, ReplaceCriteria


class PdfReplaceCommand(BaseCommand):
    name = "pdf-replace"
    help_text = "按规则查找并替换 PDF 文本内容"
    description = """\
扫描 PDF 文件，按规则查找并替换文本内容。

匹配模式：
  精确匹配（默认）：查找指定文本并替换，大小写默认不敏感
  正则匹配（--regex）：使用正则表达式匹配，实验性质，仅限单 span 内

批量替换：
  使用 --rules 指定 JSON 规则文件，支持多组查找替换规则。
  JSON 文件格式示例：
    [
      {"find": "旧文本1", "replace": "新文本1"},
      {"find": "旧文本2", "replace": "新文本2", "regex": true},
      {"find": "旧文本3", "replace": "新文本3", "case_sensitive": true}
    ]
  每条规则的 regex 和 case_sensitive 字段可省略（默认 false）。

已知限制：
  - 仅适用于可解析文本型 PDF，扫描版/图片型 PDF 无法替换
  - 表单域和批注中的文本不可搜索和替换
  - 替换区域下方的图像/线条可能一并被删除
  - 正则匹配仅限单 span 内，跨 span 文本无法匹配
  - 替换文本过长可能导致字号缩放"""

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        # 路径配置
        dir_group = parser.add_argument_group("路径配置")
        dir_group.add_argument("--source", type=str, required=True, help="源路径（PDF 文件或目录）")
        dir_group.add_argument("--recursive", action="store_true", help="递归扫描子目录")

        # 查找替换配置
        replace_group = parser.add_argument_group("查找替换")
        replace_group.add_argument("--find", type=str, help="查找文本或正则表达式（单条规则时使用）")
        replace_group.add_argument("--replace", type=str, default="", help="替换文本（默认为空，即删除匹配内容）")
        replace_group.add_argument("--regex", action="store_true", help="使用正则表达式匹配（实验性质，仅限单 span 内）")
        replace_group.add_argument("--case-sensitive", action="store_true", help="大小写敏感匹配（默认不敏感）")
        replace_group.add_argument("--rules", type=str, help="JSON 规则文件路径，支持多组查找替换（与 --find 互斥）")

        # 执行选项
        parser.add_argument("--dry-run", "-n", action="store_true", help="预览模式，只显示匹配结果不实际替换")
        parser.add_argument("--no-backup", action="store_true", help="覆盖原文件时不创建 .bak 备份")

    def _load_rules(self, rules_path: str) -> list[ReplaceCriteria] | None:
        """从 JSON 文件加载替换规则，失败返回 None"""
        path = Path(rules_path)
        if not path.exists():
            print(f"  错误: 规则文件不存在: {path}")
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"  错误: 规则文件 JSON 格式无效: {e}")
            return None
        except Exception as e:
            print(f"  错误: 读取规则文件失败: {e}")
            return None

        if not isinstance(data, list):
            print("  错误: 规则文件顶层必须是数组")
            return None

        if not data:
            print("  错误: 规则文件为空")
            return None

        criteria_list: list[ReplaceCriteria] = []
        for idx, rule in enumerate(data, 1):
            if not isinstance(rule, dict):
                print(f"  错误: 第{idx}条规则格式无效，必须是对象")
                return None

            find_text = rule.get("find")
            if not find_text or not isinstance(find_text, str):
                print(f"  错误: 第{idx}条规则缺少有效的 find 字段")
                return None

            replace_text = rule.get("replace", "")
            if not isinstance(replace_text, str):
                print(f"  错误: 第{idx}条规则 replace 字段必须是字符串")
                return None

            is_regex = bool(rule.get("regex", False))
            is_case_sensitive = bool(rule.get("case_sensitive", False))

            # 验证正则
            if is_regex:
                try:
                    re.compile(find_text)
                except re.error as e:
                    print(f"  错误: 第{idx}条规则正则表达式无效: {e}")
                    return None

            criteria_list.append(ReplaceCriteria(
                find=find_text,
                replace=replace_text,
                regex=is_regex,
                case_sensitive=is_case_sensitive,
            ))

        return criteria_list

    def execute(self, args: argparse.Namespace) -> None:
        source = Path(args.source)
        if not source.exists():
            print(f"  错误: 路径不存在: {source}")
            return

        # 参数互斥校验
        if args.rules and args.find:
            print("  错误: --rules 和 --find 不能同时使用")
            return
        if not args.rules and not args.find:
            print("  错误: 请指定 --find 或 --rules")
            return

        # 构建替换条件列表
        if args.rules:
            criteria_list = self._load_rules(args.rules)
            if criteria_list is None:
                return
        else:
            # 单条规则模式
            if args.regex:
                try:
                    re.compile(args.find)
                except re.error as e:
                    print(f"  错误: 正则表达式无效: {e}")
                    return
            criteria_list = [ReplaceCriteria(
                find=args.find,
                replace=args.replace,
                regex=args.regex,
                case_sensitive=args.case_sensitive,
            )]

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
        total_replaced = 0
        modified_count = 0
        skipped_count = 0
        failed_count = 0

        # 打印规则摘要
        if len(criteria_list) == 1:
            c = criteria_list[0]
            mode_desc = "正则" if c.regex else "精确"
            case_desc = "敏感" if c.case_sensitive else "不敏感"
            print(f"\n  查找 \"{c.find}\" → 替换为 \"{c.replace}\" ({mode_desc}匹配, {case_desc})")
        else:
            print(f"\n  批量替换模式，共 {len(criteria_list)} 条规则:")
            for idx, c in enumerate(criteria_list, 1):
                mode_desc = "正则" if c.regex else "精确"
                case_desc = "敏感" if c.case_sensitive else "不敏感"
                print(f"    {idx}. \"{c.find}\" → \"{c.replace}\" ({mode_desc}匹配, {case_desc})")
        print(f"  扫描 {len(files)} 个 PDF 文件...\n")

        for i, pdf_path in enumerate(files, 1):
            try:
                # 加密检测
                if engine.is_encrypted(pdf_path):
                    skipped_count += 1
                    print(f"  [{i}/{len(files)}] {pdf_path.name} | 跳过: 文件已加密，请先使用 pdf-decrypt 解密")
                    continue

                if len(criteria_list) == 1:
                    # 单条规则 — 使用原有 find_text / replace_text
                    criteria = criteria_list[0]
                    if args.dry_run:
                        matches = engine.find_text(pdf_path, criteria)
                        if not matches:
                            print(f"  [{i}/{len(files)}] {pdf_path.name} | 未找到匹配")
                        else:
                            pages = sorted(set(m.page for m in matches))
                            print(
                                f"  [{i}/{len(files)}] {pdf_path.name} | "
                                f"找到 {len(matches)} 处匹配（{len(pages)} 页）(预览)"
                            )
                            for m in matches[:10]:
                                preview = m.matched_text[:30] + ("..." if len(m.matched_text) > 30 else "")
                                print(f"      第{m.page}页: \"{preview}\"")
                            if len(matches) > 10:
                                print(f"      ... 还有 {len(matches) - 10} 处匹配")
                    else:
                        modified, count, affected_pages, msg = engine.replace_text(
                            pdf_path, criteria, dry_run=False, backup=not args.no_backup
                        )
                        if modified:
                            modified_count += 1
                            total_replaced += count
                        print(f"  [{i}/{len(files)}] {pdf_path.name} | {msg}")
                else:
                    # 多条规则 — 使用批量替换
                    if args.dry_run:
                        modified, count, affected_pages, msg = engine.replace_text_batch(
                            pdf_path, criteria_list, dry_run=True, backup=not args.no_backup
                        )
                        print(f"  [{i}/{len(files)}] {pdf_path.name} | {msg}")
                    else:
                        modified, count, affected_pages, msg = engine.replace_text_batch(
                            pdf_path, criteria_list, dry_run=False, backup=not args.no_backup
                        )
                        if modified:
                            modified_count += 1
                            total_replaced += count
                        print(f"  [{i}/{len(files)}] {pdf_path.name} | {msg}")

            except Exception as e:
                failed_count += 1
                print(f"  [{i}/{len(files)}] {pdf_path.name} | 失败: {e}")

        # 汇总
        print(f"\n{'=' * 50}")
        if args.dry_run:
            print(f"  [预览] 共 {len(files)} 个文件", end="")
        else:
            print(f"  完成！共 {len(files)} 个文件 | 已替换 {modified_count} 个 | {total_replaced} 处匹配", end="")
        if skipped_count:
            print(f" | 跳过 {skipped_count} 个", end="")
        if failed_count:
            print(f" | 失败 {failed_count} 个", end="")
        print()
        print(f"{'=' * 50}")
