# 多用途 CLI 工具包

一个基于子命令架构的命令行工具集，当前包含 PDF 页面处理和文件批量重命名功能。

## 安装

```bash
pip install -r requirements.txt
```

如需使用 OCR 功能，按需安装对应依赖：

```bash
# 本地 Tesseract OCR
pip install pytesseract

# 百度 OCR
pip install baidu-aip

# 火山引擎 OCR
pip install volcengine-python-sdk

# 科大讯飞 OCR（需要 requests）
pip install requests
```

## 用法

### 查看帮助

```bash
python main.py --help                # 查看所有子命令
python main.py <子命令> --help       # 查看子命令详细用法
```

### pdf-keyword — 删除 PDF 中包含指定关键词的页面

通过 OCR 识别 PDF 页面文本，自动删除包含指定关键词的页面。

```bash
# 使用 settings.json 中的配置运行
python main.py pdf-keyword

# 指定源目录和关键词
python main.py pdf-keyword --source ./pdfs --keywords "出版发行,版权"

# 处理单个文件
python main.py pdf-keyword --source ./doc.pdf --keywords "版权"

# 仅检测不删除
python main.py pdf-keyword --source ./pdfs --keywords "版权" --dry-run

# 使用火山引擎 OCR
python main.py pdf-keyword --source ./pdfs --ocr-mode volc

# 保存当前参数到配置文件
python main.py pdf-keyword --source ./pdfs --save-config

# 重置扫描进度
python main.py pdf-keyword --reset-progress
```

**OCR 配置**：在项目根目录创建 `.env` 文件，填入对应平台的密钥：

```env
BAIDU_API_KEY=your_key
BAIDU_SECRET_KEY=your_secret
# VOLC_ACCESS_KEY=your_key
# VOLC_SECRET_KEY=your_secret
# IFLYTEK_APP_ID=your_id
# IFLYTEK_API_KEY=your_key
# IFLYTEK_SECRET_KEY=your_secret
```

### pdf-blank — 删除 PDF 空白页

扫描 PDF 文件，查找并删除空白页（仅基于文本分析，无需 OCR）。

```bash
# 删除空白页
python main.py pdf-blank --source ./pdfs

# 处理单个文件
python main.py pdf-blank --source ./doc.pdf

# 预览模式（不实际删除）
python main.py pdf-blank --source ./pdfs --dry-run

# 调整空白页判定阈值（默认 10，值越大判定越严格）
python main.py pdf-blank --source ./pdfs --min-text-length 20

# 递归扫描子目录
python main.py pdf-blank --source ./pdfs --recursive
```

### pdf-decrypt — 清除 PDF 密码保护

移除 PDF 文件的密码保护，保存为无密码的 PDF。

```bash
# 清除单文件密码（无密码或已知密码）
python main.py pdf-decrypt --source ./doc.pdf

# 指定密码
python main.py pdf-decrypt --source ./doc.pdf --password 123456

# 指定输出路径（仅单文件时有效）
python main.py pdf-decrypt --source ./doc.pdf --output ./unlocked.pdf

# 批量处理目录下所有加密 PDF
python main.py pdf-decrypt --source ./pdfs

# 递归扫描子目录
python main.py pdf-decrypt --source ./pdfs --recursive

# 预览模式（只显示哪些文件加密，不实际操作）
python main.py pdf-decrypt --source ./pdfs --dry-run

# 不创建备份文件
python main.py pdf-decrypt --source ./doc.pdf --no-backup
```

### rename — 文件批量重命名

支持序号格式化、查找替换、正则匹配，内置预览模式。

```bash
# 序号模式 — 将文件重命名为 IMG_001.jpg, IMG_002.jpg ...
python main.py rename ./pics/*.jpg --pattern "IMG_{seq:03d}"

# 查找替换 — 将文件名中的 IMG 替换为 Photo
python main.py rename ./pics/*.jpg --replace "IMG>Photo"

# 正则替换 — 日期格式转换
python main.py rename ./* --regex "(\d{4})-(\d{2})-(\d{2})>$1$2$3"

# 预览模式（不实际执行）
python main.py rename ./pics/*.jpg --pattern "IMG_{seq:03d}" --dry-run

# 指定序号起始值和步长
python main.py rename ./pics/*.jpg --pattern "IMG_{seq:03d}" --start 10 --step 2

# 按修改时间排序
python main.py rename ./pics/*.jpg --pattern "IMG_{seq:03d}" --sort time

# 递归处理子目录
python main.py rename ./photos/ --pattern "Photo_{seq:04d}" --recursive

# 仅处理指定扩展名
python main.py rename ./mixed/ --replace "old>new" --include-ext jpg,png
```

## 项目结构

```
├── main.py                 # CLI 统一入口（子命令分发）
├── settings.json           # pdf-keyword 配置文件
├── requirements.txt        # Python 依赖
├── commands/               # 子命令模块
│   ├── __init__.py         # 命令基类与自动注册
│   ├── pdf_keyword.py      # 删除含关键词页面命令
│   ├── pdf_blank.py        # 删除空白页命令
│   ├── pdf_decrypt.py      # 清除密码保护命令
│   ├── pdf_unsign.py       # 清除数字签名命令
│   └── rename.py           # 文件批量重命名命令
└── core/                   # 核心功能模块
    ├── __init__.py
    ├── config.py           # 配置管理（.env + settings.json）
    ├── models.py           # 数据模型
    ├── scanner.py          # PDF 扫描器核心
    ├── pdf_engine.py       # PDF 操作引擎
    └── ocr_engines.py      # OCR 引擎集合
```

## 扩展新命令

1. 在 `commands/` 下新建 Python 文件
2. 继承 `BaseCommand`，设置 `name`、`help_text`、`description`
3. 实现 `add_arguments()` 和 `execute()` 方法
4. 命令会被自动发现和注册

```python
from commands import BaseCommand
import argparse

class MyCommand(BaseCommand):
    name = "my-cmd"
    help_text = "我的自定义命令"
    description = "详细描述"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--input", help="输入参数")

    def execute(self, args: argparse.Namespace) -> None:
        print(f"执行: {args.input}")
```
