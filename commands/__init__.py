"""
命令模块
支持子命令注册与自动发现
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse

# 命令注册表：{name: command_class}
_REGISTRY: dict[str, type[BaseCommand]] = {}


class BaseCommand:
    """命令基类，所有子命令必须继承此类"""

    # 子类必须设置的类属性
    name: str = ""           # 命令名（如 pdf-scan）
    help_text: str = ""      # 帮助简述
    description: str = ""    # 详细描述

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.name and cls.name not in _REGISTRY:
            _REGISTRY[cls.name] = cls

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """为子命令添加参数，子类可覆盖"""
        pass

    def execute(self, args: argparse.Namespace) -> None:
        """执行命令，子类必须实现"""
        raise NotImplementedError


def get_all_commands() -> dict[str, type[BaseCommand]]:
    """获取所有已注册的命令"""
    return _REGISTRY.copy()


def discover_commands() -> None:
    """自动发现并导入 commands/ 下的命令模块"""
    import importlib
    import pkgutil
    from pathlib import Path

    package_dir = Path(__file__).parent
    for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
        if module_name.startswith("_"):
            continue
        importlib.import_module(f"commands.{module_name}")


def resolve_output_path(
    pdf_path: Path,
    output: Path | None,
    source: Path,
    keep_dir_structure: bool = False,
) -> Path | None:
    """解析并返回 PDF 的最终输出路径。

    - output 为 None: 返回 None（覆盖原文件）。
    - output 是文件路径: 直接返回。
    - output 是目录 + keep_dir_structure=False: 平铺保存，文件名冲突时自动加序号。
    - output 是目录 + keep_dir_structure=True: 保持 source 下的相对目录结构保存。
    """
    if output is None:
        return None

    # 单文件模式：output 不是目录，直接作为目标文件
    if not output.is_dir():
        output.parent.mkdir(parents=True, exist_ok=True)
        return output

    # 目录模式
    if keep_dir_structure and source.is_dir():
        try:
            rel = pdf_path.relative_to(source)
        except ValueError:
            rel = pdf_path.name
        target = output / rel
    else:
        target = output / pdf_path.name

    target.parent.mkdir(parents=True, exist_ok=True)

    # 文件名冲突自动加序号
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        counter = 1
        while target.exists():
            target = target.parent / f"{stem}_{counter}{suffix}"
            counter += 1

    return target
