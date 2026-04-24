---
name: pdf-scanner-optimization
overview: 将 PDF 版权页扫描工具全面升级为基于 PyMuPDF 的高性能版本，重构代码结构、提升运行性能并增强功能。
todos:
  - id: create-config-pdfutils
    content: 创建 config.py 和 pdf_utils.py，实现 PyMuPDF 统一封装与配置管理
    status: pending
  - id: extract-ocr-engines
    content: 提取 ocr_engines.py，将原 pdf_scanner.py 中的 OCR 层完整剥离并保持接口兼容
    status: pending
  - id: implement-concurrent-scanner
    content: 实现 scanner.py 并发扫描核心，支持多文件并行与页面级 OCR 并发
    status: pending
    dependencies:
      - create-config-pdfutils
      - extract-ocr-engines
  - id: build-unified-cli
    content: 构建 main.py 统一 CLI，整合 scan / remove-blank / remove-pages 子命令，清理旧脚本
    status: pending
    dependencies:
      - create-config-pdfutils
      - extract-ocr-engines
      - implement-concurrent-scanner
  - id: polish-logging-docs
    content: 完善日志配置、错误处理、.env 模板与使用文档更新
    status: pending
    dependencies:
      - build-unified-cli
---

## 产品概述

PDF 版权页扫描与清理工具，通过 OCR 识别 PDF 中的版权关键词，自动删除版权页和空白页。

## 核心功能

- OCR 扫描指定页面范围，检测版权关键词（支持百度/火山/讯飞/本地 Tesseract）
- 支持 AND/OR 搜索逻辑、模糊匹配、大小写控制
- 自动删除检测到的版权页
- 自动删除空白页（基于文本长度和页码模式判断）
- 断点续扫（进度持久化到 JSON）
- 文件备份机制

## Tech Stack

- **Python 3.9+**（保持现有项目语言）
- **PyMuPDF (fitz)**：统一替代 PyPDF2 + pdf2image + poppler，负责 PDF 渲染、页面删除、文本提取
- **Pillow**：图像格式转换（PyMuPDF Pixmap -> PIL Image 供 OCR 使用）
- **pydantic-settings**：配置管理，支持 `.env` 环境变量与 JSON 配置文件
- **concurrent.futures**：多线程并发（多文件并行扫描 + 同文件多页面 OCR 并行）
- **标准 logging**：统一日志配置

## Implementation Approach

### 总体策略

以 PyMuPDF 为唯一 PDF 底层库，彻底移除 PyPDF2 和 pdf2image/poppler 的外部依赖。将原来分散在 3 个文件中的重复逻辑（页面范围解析、备份逻辑、PDF 读写）抽取为公共模块，重构为分层架构。

### 关键技术决策

1. **PyMuPDF 统一替换**

- 页面渲染：`fitz.Page.get_pixmap(dpi=...).pil_image()` 直接输出 PIL Image，无需外部 poppler，渲染速度提升 3-5 倍
- 页面删除：`Document.delete_page()` 原地或另存为，替代 PyPDF2 的读写流程
- 文本提取：`Page.get_text()` 替代 PyPDF2.extract_text()，稳定性更好
- 空白页检测：基于 PyMuPDF 文本提取，保持原有判断逻辑（文本长度、页码正则）

2. **并发模型**

- 文件级并发：使用 `ThreadPoolExecutor` 并行处理多个 PDF，避免 I/O 阻塞
- 页面级并发：同一 PDF 的多个待检查页面 OCR 识别并行执行（受 `ocr_max_workers` 限制，防止云 API 限流）
- 瓶颈分析：OCR 网络请求是主要瓶颈，并发可显著缩短多文件场景的总耗时；PyMuPDF 渲染为 CPU 密集型，线程并发可提升吞吐量

3. **配置外置化**

- 使用 `pydantic-settings` 从 `.env` 文件和环境变量读取敏感配置（API 密钥、目录路径）
- 非敏感配置（关键词、页面范围、DPI）支持 `config.json` 配置文件
- 完全移除代码中的硬编码密钥和绝对路径

4. **架构分层**

- `config`：配置层，统一校验和默认值
- `pdf_utils`：PDF 基础设施层（渲染、删除、文本提取、空白页检测、页面范围解析）
- `ocr_engines`：OCR 适配层（保留原有 4 种引擎，统一接口）
- `scanner`：业务逻辑层（并发扫描、版权检测、结果汇总）
- `main`：接入层（CLI 子命令：scan / remove-blank / remove-pages）

### 性能与可靠性

- 消除 poppler 外部依赖，减少环境配置失败率
- 引入指数退避重试机制处理 OCR 网络超时
- 进度保存改为异步批量 + 异常安全回退，降低 I/O 频率
- 保留向后兼容的扫描进度 JSON 格式

## Implementation Notes

- **Grounded**：保持原有 OCR 引擎的接口契约和识别行为不变；保留 `pdf_scan_progress.json` 的数据结构，避免用户已有进度丢失
- **Blast radius control**：`remove_pdf_blank_pages.py` 和 `remove_pdf_pages.py` 的功能将合并到统一 CLI 中，原文件标记删除；如用户有外部脚本引用，需在文档中说明迁移方式
- **Logging**：统一使用 `logging.getLogger("pdf_scanner")`，避免根日志污染；OCR 异常保留原有的 `logging.error` + `print` 双通道提示
- **性能**：PyMuPDF 渲染的 `Pixmap` 可直接转 bytes 供百度/讯飞/火山 OCR 使用（跳过 PIL 中转），减少一次图像编码开销；但本地 Tesseract 仍需 PIL Image，故保留 Image 转换接口

## Architecture Design

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI (main.py)                        │
│   scan │ remove-blank │ remove-pages │ resume │ config       │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                    Scanner (scanner.py)                      │
│   - ThreadPoolExecutor 多文件并行                            │
│   - 页面级 OCR 并发调度                                       │
│   - 进度管理与断点续扫                                        │
└────────────────────┬────────────────────────────────────────┘
                     │
    ┌────────────────┼────────────────┐
    ▼                ▼                ▼
┌─────────┐   ┌─────────────┐   ┌─────────────┐
│ OCR     │   │ PDF Engine  │   │ Config      │
│ Engines │   │ (pdf_utils) │   │ (config)    │
│         │   │             │   │             │
│- Baidu  │   │- render    │   │- .env       │
│- Volc   │   │- delete    │   │- json       │
│- Iflytek│   │- extract   │   │- validation │
│- Local  │   │- blank_chk │   │             │
└─────────┘   └─────────────┘   └─────────────┘
                     │
                     ▼
              ┌─────────────┐
              │  PyMuPDF    │
              │   (fitz)    │
              └─────────────┘
```

## Directory Structure

```
d:/code/a1/
├── config.py                   # [NEW] Pydantic 配置管理。支持 .env / config.json / 环境变量三源合并，包含所有 OCR 密钥、路径、扫描参数的定义与校验
├── pdf_utils.py                # [NEW] PDF 统一工具层。基于 PyMuPDF 实现：页面渲染转 PIL Image、页面删除（原地/另存）、文本提取、空白页检测、页面范围字符串解析
├── ocr_engines.py              # [NEW] OCR 引擎集合。从原 pdf_scanner.py 提取的 LocalOCREngine / BaiduOCREngine / VolcOCREngine / IflytekOCREngine / OCREngineFactory，保持原有识别行为
├── scanner.py                  # [NEW] 并发扫描器核心。重构后的 PDFScanner，支持多文件 ThreadPoolExecutor 并行、同文件多页面 OCR 并发、结果汇总与进度保存
├── main.py                     # [NEW] 统一 CLI 入口。使用 argparse 子命令实现 scan / remove-blank / remove-pages，替代原来分散的 3 个脚本入口
├── pdf_scanner.py              # [MODIFY] 改为向后兼容的顶层包装或删除。若保留，则导入新模块并打印迁移提示
├── remove_pdf_blank_pages.py   # [DELETE] 功能已合并至 pdf_utils.py + main.py
├── remove_pdf_pages.py         # [DELETE] 功能已合并至 pdf_utils.py + main.py
├── .env.example                # [NEW] 环境变量模板文件，包含 API 密钥、目录路径占位符
├── config.example.json         # [NEW] 非敏感配置模板（关键词、页面范围、DPI、并发数等）
└── PDF_SCANNER_USAGE.md        # [MODIFY] 更新使用文档，说明新安装方式（pip install pymupdf pydantic-settings）、配置方法、CLI 子命令用法
```

## Key Code Structures

```python
# pdf_utils.py - PDF 统一操作接口
class PDFEngine:
    def render_pages(self, pdf_path: Path, page_nums: list[int], dpi: int = 150) -> list[tuple[int, Image.Image]]: ...
    def extract_text(self, pdf_path: Path, page_num: int) -> str: ...
    def delete_pages(self, pdf_path: Path, page_nums: list[int], backup_dir: Path | None = None) -> bool: ...
    def find_blank_pages(self, pdf_path: Path, min_text_length: int = 10) -> list[int]: ...

# config.py - 统一配置定义
class AppConfig(BaseSettings):
    source_dir: Path
    backup_dir: Path | None = None
    keywords: list[str]
    search_logic: Literal["AND", "OR"] = "AND"
    dpi: int = 150
    max_workers: int = 4          # 文件级并发数
    ocr_max_workers: int = 2      # OCR 并发数（防止云 API 限流）
    pages_to_check: str = "-1"
    remove_copyright_pages: bool = True
    remove_blank_pages: bool = True
    recognition_mode: str = "baidu"
    # OCR 密钥通过 .env 注入，不再硬编码
```