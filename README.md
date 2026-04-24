# PDF 版权页扫描工具

命令行工具，自动识别并删除 PDF 中的版权页和空白页。

## 功能

- **OCR 识别版权页** — 渲染指定页面，通过 OCR 匹配关键词
- **自动删除版权页** — 检测到版权页后自动删除，修改前可备份
- **自动删除空白页** — 基于文本内容智能检测并删除空白页
- **断点续扫** — 进度自动保存，中断后可继续
- **并发处理** — 多文件并行 + 页面级 OCR 并发
- **多种 OCR 引擎** — 百度 / 火山引擎 / 科大讯飞 / 本地 Tesseract
- **模糊匹配** — 容许少量干扰字符，提高识别准确率

## 安装

```bash
pip install -r requirements.txt
```

可选 OCR 依赖按需安装：

```bash
pip install pytesseract      # 本地 Tesseract
pip install baidu-aip        # 百度 OCR
pip install volcengine       # 火山引擎 OCR
pip install requests         # 科大讯飞 OCR
```

## 配置

### settings.json

非敏感配置保存在 `settings.json`（打包后在 `%APPDATA%/PDFScanner/settings.json`）：

```json
{
  "source_dir": "C:\\Users\\xxx\\pdfs",
  "backup_dir": "C:\\Users\\xxx\\backup",
  "keywords": ["出版发行", "侵权", "版权"],
  "search_logic": "AND",
  "pages_to_check": "-1",
  "recognition_mode": "baidu",
  "ocr_accuracy": "accurate_basic",
  "dpi": 300,
  "remove_copyright_pages": true,
  "remove_blank_pages": true,
  "max_workers": 4,
  "ocr_max_workers": 2
}
```

### .env 环境变量

OCR 密钥通过 `.env` 文件或系统环境变量配置：

```env
BAIDU_APP_ID=your_app_id
BAIDU_API_KEY=your_api_key
BAIDU_SECRET_KEY=your_secret_key

VOLC_ACCESS_KEY=your_access_key
VOLC_SECRET_KEY=your_secret_key

IFLYTEK_APP_ID=your_app_id
IFLYTEK_API_KEY=your_api_key
IFLYTEK_SECRET_KEY=your_secret_key
```

## 使用

```bash
# 使用 settings.json 配置运行
python main.py

# 指定源目录和关键词
python main.py --source-dir ./pdfs --keywords "出版发行,版权"

# 仅检测不删除
python main.py --no-remove-copyright --no-remove-blank

# 重置进度，重新扫描所有文件
python main.py --reset-progress

# 保存当前参数到 settings.json
python main.py --source-dir ./pdfs --keywords "版权" --save-config

# 使用火山引擎 OCR
python main.py --ocr-mode volc

# 查看所有参数
python main.py --help
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--source-dir` | 源目录（包含 PDF 文件） | `.` |
| `--backup-dir` | 备份目录 | 自动 |
| `--keywords` | 关键词，逗号分隔 | `出版发行,侵权,版权` |
| `--search-logic` | 搜索逻辑 `AND` / `OR` | `AND` |
| `--case-sensitive` | 区分大小写 | 否 |
| `--pages-to-check` | 检查页面范围 | `-1`（最后一页） |
| `--no-remove-copyright` | 不删除版权页 | - |
| `--no-remove-blank` | 不删除空白页 | - |
| `--ocr-mode` | OCR 模式 `local`/`baidu`/`volc`/`iflytek` | `baidu` |
| `--ocr-accuracy` | OCR 精度 `general_basic`/`accurate_basic`/`general`/`accurate` | `accurate_basic` |
| `--ocr-lang` | OCR 语言 | `chi_sim` |
| `--dpi` | 渲染 DPI | `300` |
| `--no-filter-spaces` | 不过滤空格 | - |
| `--no-fuzzy-match` | 禁用模糊匹配 | - |
| `--max-interfering-chars` | 模糊匹配最大干扰字符数 | `2` |
| `--max-workers` | 文件并发数 | `4` |
| `--ocr-max-workers` | OCR 并发数 | `2` |
| `--debug` | 调试模式（输出 OCR 识别详情） | - |
| `--save-config` | 保存配置到 settings.json | - |
| `--reset-progress` | 重置扫描进度 | - |

### 页面范围格式

| 格式 | 说明 |
|------|------|
| `2` | 只检查第 2 页 |
| `2:5` | 检查第 2 到 5 页 |
| `2,-1` | 检查第 2 页和最后一页 |
| `2:5,7:10,-3:-1` | 组合多个范围 |

负数表示从后往前（`-1` = 最后一页，`-2` = 倒数第二页）。

## 项目结构

```
├── main.py              # CLI 入口
├── requirements.txt     # 依赖
├── settings.json        # 用户配置
└── core/
    ├── config.py        # 配置管理（.env + settings.json + 环境变量）
    ├── models.py        # 数据模型（ScanResult, ScanProgress）
    ├── scanner.py       # 扫描器核心（并发、进度、关键词匹配）
    ├── pdf_engine.py    # PDF 操作（渲染、删除、空白页检测）
    └── ocr_engines.py   # OCR 引擎（百度/火山/讯飞/本地）
```
