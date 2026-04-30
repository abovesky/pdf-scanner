---
name: add-output-param-to-pdf-commands
overview: 为 pdf-keyword、pdf-blank、pdf-dewatermark 三个子命令增加 --output 参数，支持单文件处理时指定输出路径，行为与已有的 pdf-decrypt/pdf-unsign 保持一致。
todos:
  - id: extend-scanner
    content: 扩展 `core/scanner.py` 的 `process_pdf` 和 `run` 方法以支持 `output_path` 参数
    status: completed
  - id: output-pdf-keyword
    content: 为 `commands/pdf_keyword.py` 添加 `--output` 参数及单文件输出逻辑
    status: completed
    dependencies:
      - extend-scanner
  - id: output-pdf-blank-dewatermark
    content: 为 `commands/pdf_blank.py` 和 `commands/pdf_dewatermark.py` 添加 `--output` 参数及单文件输出逻辑
    status: completed
  - id: update-readme
    content: 更新 `README.md`，补充三个子命令的 `--output` 用法示例
    status: completed
    dependencies:
      - output-pdf-keyword
      - output-pdf-blank-dewatermark
---

## 产品概述

为现有 CLI 工具包的三个 PDF 处理子命令（`pdf-keyword`、`pdf-blank`、`pdf-dewatermark`）增加 `--output` 参数，使用户在处理单个 PDF 文件时能够指定输出路径，而非默认覆盖原文件。

## 核心功能

- `pdf-keyword --output <路径>`：删除含关键词页面后，将结果保存到指定路径
- `pdf-blank --output <路径>`：删除空白页后，将结果保存到指定路径
- `pdf-dewatermark --output <路径>`：去除注释型水印后，将结果保存到指定路径
- `--output` 行为与现有 `pdf-decrypt`、`pdf-unsign` 保持一致：
- 仅在处理**单个文件**时有效
- 若 `--output` 指向目录，自动拼接原文件名作为输出名
- 批量处理目录时若指定 `--output`，提示错误并退出
- 不指定时默认覆盖原文件（备份行为仍由 `--no-backup` 控制）

## Tech Stack Selection

- 语言与框架：Python 3 + argparse（延续现有 CLI 架构）
- PDF 引擎：PyMuPDF（fitz）（现有 `core/pdf_engine.py`）
- 扫描器：`core/scanner.PDFScanner`（现有并发扫描核心）

## Implementation Approach

### 策略概述

完全复用项目中 `pdf-decrypt` 和 `pdf-unsign` 的 `--output` 实现模式，保持用户界面和内部行为的一致性。

1. **pdf-keyword**：该命令通过 `PDFScanner` 并发处理文件。需要扩展 `PDFScanner.process_pdf()` 和 `run()` 方法，增加可选的 `output_path` 参数，并在调用 `PDFEngine.delete_pages()` 时向下传递。命令层在 `execute()` 中解析 `--output`，验证单文件/目录约束，再传入 Scanner。
2. **pdf-blank**：命令层直接调用 `PDFEngine`。在 `execute()` 中解析 `--output`，验证约束后，将 `output_path` 传入 `PDFEngine.delete_pages()`（`remove_blank_pages` 已支持 `output_path`，可直接复用）。
3. **pdf-dewatermark**：同样在 `execute()` 中解析并验证 `--output`，然后将 `output_path` 传入 `PDFEngine.remove_annotation_watermarks()`（该方法已支持 `output_path`）。
4. **备份控制**：底层 `PDFEngine` 的 `delete_pages`、`remove_annotation_watermarks` 等已实现“若 `save_path == pdf_path` 则创建 `.bak` 备份”的逻辑，因此命令层只需透传 `output_path` 和 `backup=not args.no_backup`，无需额外处理备份。

### 关键设计决策

- **不将 `output_path` 加入 `AppConfig`**：`output_path` 是一次性 CLI 参数，不属于持久化配置，与 `pdf-decrypt`/`pdf-unsign` 的设计保持一致。
- **最小改动原则**：`pdf-blank` 和 `pdf-dewatermark` 的底层引擎已原生支持 `output_path`，仅需修改命令层的参数解析和透传逻辑。
- **单文件验证前置**：在 `execute()` 最前端根据 `source.is_file()` 判断，若目录模式且带 `--output` 立即报错，避免进入扫描/处理流程后再中断。

## Implementation Notes

- **Grounded**：`core/pdf_engine.py` 中的 `delete_pages`、`remove_blank_pages`、`remove_annotation_watermarks` 均已包含 `output_path: Path | None = None` 参数及对应的保存/备份逻辑，命令层只需透传即可。
- **Scanner 改动**：`PDFScanner.run()` 使用 `ThreadPoolExecutor` 并发调用 `process_pdf`。改为 `executor.submit(self.process_pdf, fp, output_path)` 即可将输出路径传入每个任务；由于单文件场景下 `files` 列表长度为 1，不会误将同一输出路径用于多个文件。
- **目录自动拼接**：若 `output.is_dir()`，则令 `output = output / source.name`，与 `pdf-decrypt` 逻辑一致。
- **Blast radius control**：改动完全局限于三个命令文件和 `scanner.py`，不影响 OCR 引擎、配置管理、进度保存等其他模块。

## Directory Structure

```
d:/code/a1/
├── core/
│   └── scanner.py              # [MODIFY] process_pdf 与 run 增加 output_path 参数并透传给 delete_pages
├── commands/
│   ├── pdf_keyword.py          # [MODIFY] 添加 --output 参数、单文件校验、将 output_path 传入 Scanner
│   ├── pdf_blank.py            # [MODIFY] 添加 --output 参数、单文件校验、将 output_path 传入 PDFEngine
│   └── pdf_dewatermark.py      # [MODIFY] 添加 --output 参数、单文件校验、将 output_path 传入 PDFEngine
└── README.md                   # [MODIFY] 补充三个子命令的 --output 用法示例
```