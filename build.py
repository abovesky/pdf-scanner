"""
PyInstaller 打包脚本
生成单文件 CLI exe
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def build():
    """执行打包"""
    print("=" * 50)
    print("PDF Scanner 打包脚本 (CLI)")
    print("=" * 50)

    # 清理旧构建
    dist_dir = Path("dist")
    build_dir = Path("build")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)

    # PyInstaller 参数
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--name", "PDFScanner",
        "--onefile",
        "--console",
        "--clean",
        "--noconfirm",
        # 隐藏导入
        "--hidden-import", "core",
        "--hidden-import", "core.config",
        "--hidden-import", "core.models",
        "--hidden-import", "core.ocr_engines",
        "--hidden-import", "core.pdf_engine",
        "--hidden-import", "core.scanner",
        "--hidden-import", "fitz",
        "--hidden-import", "PIL",
        # 图标（如果有的话）
        # "--icon", "assets/icon.ico",
        "main.py",
    ]

    print("执行命令:")
    print(" ".join(cmd))
    print()

    result = subprocess.run(cmd, capture_output=False, text=True)

    if result.returncode == 0:
        print("\n" + "=" * 50)
        print("打包成功!")
        print(f"输出路径: {Path('dist/PDFScanner.exe').absolute()}")
        print("=" * 50)
    else:
        print("\n打包失败，请检查错误信息。")
        sys.exit(1)


if __name__ == "__main__":
    build()
