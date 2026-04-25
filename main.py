"""
多用途 CLI 工具包 — 统一入口
支持子命令：pdf-keyword, pdf-blank, rename 等
"""
import argparse
import sys

from commands import BaseCommand, discover_commands, get_all_commands

__version__ = "2.0.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="toolkit",
        description="多用途 CLI 工具包",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
可用子命令:
  pdf-keyword   删除 PDF 中包含指定关键词的页面
  pdf-blank     删除 PDF 空白页
  pdf-decrypt   清除 PDF 密码保护
  rename        文件批量重命名

使用 'python main.py <子命令> --help' 查看子命令详细用法

示例:
  python main.py pdf-keyword --source ./pdfs --keywords "版权"
  python main.py pdf-keyword --source ./doc.pdf --keywords "版权"
  python main.py pdf-blank --source ./pdfs --dry-run
  python main.py pdf-blank --source ./doc.pdf
  python main.py pdf-decrypt --source ./doc.pdf --password 123456
  python main.py pdf-decrypt --source ./pdfs --recursive
  python main.py rename ./pics/*.jpg --pattern "IMG_{seq:03d}" --dry-run
""",
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--verbose", action="store_true", help="显示详细日志")
    parser.add_argument("--quiet", action="store_true", help="静默模式，仅显示错误")

    # 自动注册子命令
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    for name, cmd_class in get_all_commands().items():
        cmd = cmd_class()
        sub = subparsers.add_parser(
            name,
            help=cmd.help_text,
            description=cmd.description,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        # 全局选项
        sub.add_argument("--verbose", action="store_true", help="显示详细日志")
        sub.add_argument("--quiet", action="store_true", help="静默模式")
        # 子命令专属参数
        cmd.add_arguments(sub)

    return parser


def main():
    # 自动发现命令
    discover_commands()

    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 查找并执行对应命令
    commands = get_all_commands()
    cmd_class = commands.get(args.command)
    if cmd_class:
        cmd = cmd_class()
        cmd.execute(args)
    else:
        print(f"未知子命令: {args.command}")
        parser.print_help()


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
