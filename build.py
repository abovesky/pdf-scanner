"""
PyInstaller 打包 + 一键分发脚本
生成单文件 CLI exe，并打包成可分发的 zip
"""
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

APP_NAME = "PDFScanner"
VERSION = "1.0.0"


def build():
    """执行打包"""
    print("=" * 50)
    print(f"{APP_NAME} 打包脚本 v{VERSION}")
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
        "--name", APP_NAME,
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

    if result.returncode != 0:
        print("\n打包失败，请检查错误信息。")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("打包成功!")
    print("=" * 50)


def package():
    """打包成可分发的 zip"""
    exe_path = Path(f"dist/{APP_NAME}.exe")
    if not exe_path.exists():
        print(f"错误: 找不到 {exe_path}，请先执行打包")
        sys.exit(1)

    # 分发目录
    release_dir = Path("release")
    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir()

    # 复制 exe
    shutil.copy2(exe_path, release_dir / exe_path.name)

    # 复制 settings.json
    settings_src = Path("settings.json")
    if settings_src.exists():
        shutil.copy2(settings_src, release_dir / "settings.json")
    else:
        # 生成默认配置
        import json
        default_settings = {
            "source_dir": ".",
            "backup_dir": None,
            "keywords": ["出版发行", "侵权", "版权"],
            "search_logic": "AND",
            "case_sensitive": False,
            "pages_to_check": "-1",
            "remove_copyright_pages": True,
            "remove_blank_pages": True,
            "debug_mode": False,
            "recognition_mode": "baidu",
            "ocr_accuracy": "accurate_basic",
            "ocr_lang": "chi_sim",
            "dpi": 300,
            "filter_spaces": True,
            "fuzzy_match": True,
            "max_interfering_chars": 2,
            "max_workers": 4,
            "ocr_max_workers": 2,
        }
        with open(release_dir / "settings.json", "w", encoding="utf-8") as f:
            json.dump(default_settings, f, ensure_ascii=False, indent=2)

    # 生成 .env 模板
    env_template = """\
# 百度 OCR 密钥（在 https://cloud.baidu.com/doc/OCR/s/dk3iqnq51 申请）
BAIDU_APP_ID=
BAIDU_API_KEY=
BAIDU_SECRET_KEY=

# 火山引擎 OCR 密钥（在 https://www.volcengine.com/docs/6797/46974 申请）
VOLC_ACCESS_KEY=
VOLC_SECRET_KEY=

# 科大讯飞 OCR 密钥（在 https://www.xfyun.cn/doc/words/ocr/API.html 申请）
IFLYTEK_APP_ID=
IFLYTEK_API_KEY=
IFLYTEK_SECRET_KEY=
"""
    with open(release_dir / ".env", "w", encoding="utf-8") as f:
        f.write(env_template)

    # 生成使用说明
    readme_content = f"""\
{APP_NAME} v{VERSION} - PDF 版权页扫描工具
{"=" * 50}

快速开始：
  1. 编辑 .env 文件，填入 OCR 密钥（至少填一种）
  2. 编辑 settings.json，设置 source_dir 为 PDF 所在目录
  3. 双击运行 PDFScanner.exe

常用命令：
  PDFScanner.exe                          使用 settings.json 配置运行
  PDFScanner.exe --source-dir ./pdfs      指定源目录
  PDFScanner.exe --keywords "出版发行,版权"  指定关键词
  PDFScanner.exe --no-remove-copyright    仅检测不删除版权页
  PDFScanner.exe --no-remove-blank        不删除空白页
  PDFScanner.exe --verbose                显示详细日志
  PDFScanner.exe --reset-progress         重置进度，重新扫描
  PDFScanner.exe --help                   查看所有参数

OCR 密钥申请：
  百度（免费额度）:  https://cloud.baidu.com/doc/OCR/s/dk3iqnq51
  火山引擎:         https://www.volcengine.com/docs/6797/46974
  科大讯飞（免费额度）: https://www.xfyun.cn/doc/words/ocr/API.html

注意：
  - 首次使用请先编辑 .env 填入密钥
  - 修改 PDF 前会自动备份到 backup_dir 目录
  - 进度自动保存，中断后再次运行可继续
"""
    with open(release_dir / "使用说明.txt", "w", encoding="utf-8") as f:
        f.write(readme_content)

    # 打包成 zip
    zip_name = f"{APP_NAME}_v{VERSION}"
    zip_path = Path(f"dist/{zip_name}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in release_dir.iterdir():
            zf.write(file, f"{zip_name}/{file.name}")

    print(f"\n分发包已生成: {zip_path.absolute()}")
    print(f"包含文件:")
    for file in sorted(release_dir.iterdir()):
        size = file.stat().st_size
        if size > 1024 * 1024:
            print(f"  {file.name}  ({size / 1024 / 1024:.1f} MB)")
        else:
            print(f"  {file.name}  ({size / 1024:.1f} KB)")

    # 清理临时目录
    shutil.rmtree(release_dir)
    print(f"\n请将 {zip_path.name} 发给对方，解压后即可使用。")


if __name__ == "__main__":
    build()
    package()
