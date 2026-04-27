---
name: fix-pdf-keyword-reliability
overview: 修复 pdf-keyword 子命令在参数解析、数值处理、并发日志、执行顺序等方面的可靠性缺陷。
todos:
  - id: fix-cli-args-mapping
    content: 修复 `pdf_keyword.py` CLI 参数映射与数值判定缺陷
    status: completed
  - id: fix-concurrent-output
    content: 修复 `pdf_keyword.py` 并发日志锁与表格对齐
    status: completed
    dependencies:
      - fix-cli-args-mapping
  - id: fix-execution-flow
    content: 修复 `pdf_keyword.py` 执行流程时序与一致性
    status: completed
    dependencies:
      - fix-cli-args-mapping
---

## 修复目标

修复 `pdf-keyword` 子命令在参数解析、并发输出、执行时序与文本截断等方面的可靠性缺陷，确保命令行稳定运行。

## 核心修复项

1. 补全缺失的 `--verbose` / `--quiet` 参数定义，避免 `AttributeError`
2. 修复数值参数 `0` 被静默忽略的问题（`dpi`、`max_workers` 等）
3. 修复 `--keywords ""` 空字符串时未按用户意图清空关键词的问题
4. 为 `_log_handler` 增加线程锁，防止 OCR 并发时日志输出交错
5. 修正 `reset_progress` 与 `config.validate()` 的执行时序
6. 修复 `get_pdf_files()` 被调用两次可能导致进度计数不一致的问题
7. 移除冗余的 `hasattr(config, "source_path")` 判断
8. 修复结果表格中文件名截断未考虑中文等宽字符显示宽度的问题

## 技术方案

基于现有 Python CLI 架构，仅修改 `commands/pdf_keyword.py`，不侵入 `core/` 模块，保持最小改动范围。

### 关键修改点

- **参数解析层 (`add_arguments` / `_apply_cli_args`)**：补全 `--verbose` / `--quiet`；数值参数判断改为 `is not None`；`keywords` 空字符串支持。
- **并发输出层 (`_log_handler`)**：复用已有的 `self._print_lock`，将日志输出纳入同一把锁保护。
- **执行流程层 (`execute`)**：调整 `validate` 与 `reset_progress` 顺序；在 `scanner.run()` 前预计算并固定 PDF 文件列表，消除二次扫描差异；简化 `source_path` 回退逻辑。
- **表格渲染层 (`print_results`)**：新增按显示宽度截断函数，确保中文对齐。