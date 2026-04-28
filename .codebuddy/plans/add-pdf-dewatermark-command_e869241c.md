---
name: add-pdf-dewatermark-command
overview: 增加 pdf-dewatermark 子命令，支持去除 PDF 中的注释型水印和重复图片水印。
todos:
  - id: extend-pdf-engine
    content: 在 PDFEngine 中新增水印检测与去除方法
    status: completed
  - id: create-dewatermark-cmd
    content: 创建 pdf-dewatermark 子命令模块，集成文件遍历与参数解析
    status: completed
    dependencies:
      - extend-pdf-engine
  - id: update-main-epilog
    content: 更新 main.py 帮助文档，注册新命令并补充使用示例
    status: completed
    dependencies:
      - create-dewatermark-cmd
---

## 产品概述

为现有 CLI 工具包增加一个 `pdf-dewatermark` 子命令，仅用于去除 PDF 文件中的注释型水印。

## 核心功能

- **去除注释型水印**：遍历 PDF 所有页面的 annotations，删除 Subtype 为 Watermark 的注释，以及作为水印的 Stamp 注释
- 支持单文件与批量目录处理，支持 `--recursive` 递归扫描子目录
- 支持 `--dry-run` 预览模式，仅显示检测到的水印信息而不修改文件
- 支持 `--no-backup` 跳过 `.bak` 备份生成

## 技术栈

- Python + PyMuPDF (fitz)（项目已有依赖）
- 现有命令注册体系（`BaseCommand` 自动发现）

## 实现方案

在 `PDFEngine` 中新增注释型水印检测与去除方法：

1. **注释水印检测**：遍历 `page.annots()`，识别 `Subtype` 为 `/Watermark` 或 `/Stamp` 的注释对象，统计页码与类型
2. **注释水印删除**：调用 `page.delete_annot(annot)` 删除识别到的注释对象
3. **文件保存**：若存在修改且非 `--dry-run`，通过临时文件原子替换原文件；默认自动创建 `.bak` 备份，可通过 `--no-backup` 跳过

命令层负责文件收集、循环处理、结果汇总和 `--dry-run` 控制；引擎层负责检测、删除与保存。

## 实现注意事项

- **兼容性**：遵循现有 `delete_pages` / `remove_password` 的保存模式——覆盖原文件时先写入临时文件再通过 `shutil.move` 替换，避免 Windows 句柄占用问题；默认自动创建 `.bak` 备份
- **安全**：若 PDF 中未发现任何 Watermark/Stamp 注释，不执行保存操作，避免无意义重写文件；结果报告中区分输出注释类型（Watermark / Stamp），提高透明度

## 架构设计

- **命令层**：`PdfDewatermarkCommand`（`commands/pdf_dewatermark.py`），继承 `BaseCommand`，负责参数解析、文件遍历、进度输出与结果统计
- **引擎层**：`PDFEngine`（`core/pdf_engine.py`），新增 `analyze_annotation_watermarks()`（纯检测）与 `remove_annotation_watermarks()`（检测+删除+保存）方法
- **数据流**：Command 收集文件列表 → 对每个文件调用 Engine 检测方法 → Command 根据 `--dry-run` 决定仅打印或调用 Engine 执行删除与保存

## 目录结构

```
d:/code/a1/
├── commands/
│   └── pdf_dewatermark.py   # [NEW] 去水印子命令：参数解析、文件遍历、结果汇总
├── core/
│   └── pdf_engine.py        # [MODIFY] 新增注释水印检测/去除方法
└── main.py                  # [MODIFY] epilog 帮助文本中追加 pdf-dewatermark 说明与示例
```