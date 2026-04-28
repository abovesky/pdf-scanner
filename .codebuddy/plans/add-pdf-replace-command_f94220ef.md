---
name: add-pdf-replace-command
overview: 新增 pdf-replace 子命令，支持按规则（正则/精确匹配）查找并替换 PDF 文本内容
todos:
  - id: add-engine-structures
    content: 在 core/pdf_engine.py 中新增 ReplaceCriteria、TextMatchInfo 数据类和 find_text、replace_text 方法
    status: completed
  - id: create-pdf-replace-cmd
    content: 创建 commands/pdf_replace.py 子命令，实现参数定义和执行逻辑
    status: completed
    dependencies:
      - add-engine-structures
  - id: update-main-help
    content: 更新 main.py epilog 添加 pdf-replace 帮助信息和示例
    status: completed
    dependencies:
      - create-pdf-replace-cmd
---

## 产品概述

为现有 PDF CLI 工具包新增 `pdf-replace` 子命令，支持按规则查找并替换 PDF 中的文本内容。

## 核心功能

- 精确文本查找与替换（`--find "旧文本" --replace "新文本"`）— 主要功能，最可靠
- 正则表达式匹配与替换（`--regex` 标志）— 增强功能，实验性质，仅限单 span 内匹配
- 大小写敏感/不敏感匹配（`--case-sensitive` 标志，默认不敏感）
- 支持单文件和目录批量处理（`--source` + `--recursive`）
- 预览模式查看匹配结果不实际修改（`--dry-run`）
- 备份控制（`--no-backup`）
- 替换时尽量保持原文档字体和字号
- 替换文本为空串时语义为删除匹配文本（`--replace ""`）
- 加密文件自动跳过并提示
- 扫描版/图片型 PDF 检测与警告

## 已知局限性（应在帮助信息中说明）

- 仅适用于**可解析文本型** PDF，扫描版/图片型 PDF 无法替换（会输出警告）
- 表单域（Form field）中的文本不可搜索和替换
- 批注（Annotation）中的文本不可搜索和替换
- `apply_redactions()` 会移除 redaction 区域覆盖下的所有内容（包括背景图片/线条），不仅是文本
- 正则匹配仅限单 span 内，跨 span 的文本无法被一条正则匹配到
- 替换文本可能因长度差异导致字号缩放

## 技术栈

- 语言：Python（与现有项目一致）
- PDF 引擎：PyMuPDF (fitz)（与现有项目一致）
- 命令框架：argparse + BaseCommand 自动注册机制

## 实现方案

### 核心策略

基于 PyMuPDF 的 redaction（涂黑）机制实现文本替换：先用 `page.search_for()` 或自定义 span 匹配定位文本位置，再用 `page.add_redact_annot(rect, text=replacement)` 标记替换区域，最后 `page.apply_redactions()` 统一应用替换。此方案无需重建 PDF，保留原有页面结构和非文本元素。

### 匹配策略（按优先级）

1. **精确匹配（大小写敏感）**：直接使用 `page.search_for(find_text)` — PyMuPDF 原生支持，最可靠，首选路径。注意 `search_for()` 对多行文本会返回多个 rect（每行一个），一个逻辑匹配对应多个 rect 时，需为每个 rect 添加 redaction annot 并使用相同的替换文本
2. **精确匹配（大小写不敏感）+ 正则匹配**：通过 `page.get_text("rawdict")` 提取字符级文本（每个 char 有独立 bbox），逐 span 执行匹配后，根据匹配子串的字符范围精确计算 bbox 区域。若匹配跨 span 则合并矩形区域
3. **正则匹配（`--regex`，实验性质）**：同样基于 `rawdict` 字符级提取，对每个 span 逐个执行正则匹配，仅限**单 span 内**匹配，不处理跨 span 情况。正则分组替换支持 `re.sub` 语义（如 `\1` 引用分组）

### 字符级定位

使用 `page.get_text("rawdict")` 替代 `"dict"` — `rawdict` 为每个字符提供独立的 bbox，可以精确计算匹配子串的区域：

- 遍历 span 中的 chars 列表，找到匹配子串的起始和结束字符
- 合并起始~结束字符的 bbox 得到精确匹配区域
- 比基于字符偏移估算位置更准确

### 字体保持

- 从匹配 span 中提取 `font`、`size`、`color` 信息
- `add_redact_annot` 时传入原始字号 `fontsize`
- 新增 `_map_to_builtin_font()` 方法：将原始字体名映射为 PyMuPDF 内置字体
- CJK 字体映射：含 `SimSun`/`Song`/`宋` → `china-s`，含 `Ming`/`MingLiu` → `china-t`，含 `YaHei`/`Hei`/`黑` → `china-s`，含 `Kai`/`楷` → `china-s`
- 非中文字体默认使用 `helv`（Helvetica）
- 若原始字体名已是内置名（`china-s`/`china-t`/`helv`/`tiro`/`cour`/`symb`/`zadb`），直接使用

### 安全与兼容性

- **加密检测**：复用 `PDFEngine.is_encrypted()`，加密文件跳过并提示先用 `pdf-decrypt`
- **扫描版 PDF 检测**：页面无可解析文本（`page.get_text()` 为空）但含图像/矢量图时，输出警告 "该页可能为扫描版，无法替换文本"
- **替换文本溢出**：dry-run 输出中标注原文与替换文长度差异，超出 2 倍时发出警告
- **rect 内缩**：添加 redaction annot 前，将 rect 四周内缩 0.5pt，减少误删相邻内容的风险
- **图像/矢量重叠检测**：添加 redaction 前检查 rect 是否与页面图像或矢量图重叠，若重叠则发出警告（`apply_redactions()` 会删除 rect 下的所有内容，不仅是文本）

### 性能考量

- 每个文件只打开一次，遍历页面时完成查找+替换标记，最后统一 apply_redactions + save
- 大文件逐页处理，不一次性加载全部页面文本到内存
- 文件保存采用与现有命令一致的 tempfile + move 策略，避免 Windows 句柄占用

## 目录结构

```
d:/code/a1/
├── commands/
│   └── pdf_replace.py    # [NEW] pdf-replace 子命令，继承 BaseCommand
├── core/
│   └── pdf_engine.py     # [MODIFY] 新增 TextMatchInfo、ReplaceCriteria 数据类及 find_text / replace_text / _map_to_builtin_font 方法
└── main.py               # [MODIFY] epilog 中添加 pdf-replace 帮助信息和示例
```

### 文件详细说明

**commands/pdf_replace.py** [NEW]

- 定义 `PdfReplaceCommand(BaseCommand)`，`name = "pdf-replace"`
- `add_arguments()`: 注册 --source, --find, --replace, --regex, --case-sensitive, --recursive, --dry-run, --no-backup 参数
- `execute()`: 收集文件 → 加密检测 → 构建替换条件 → 逐文件调用 PDFEngine.replace_text → 输出结果汇总
- 遵循现有轻量命令模式（参考 pdf-dewatermark / pdf-remove-image）

**core/pdf_engine.py** [MODIFY]

- 新增 `TextMatchInfo` dataclass：page, rects, matched_text, fontname, fontsize, color
- 新增 `ReplaceCriteria` dataclass：find, replace, regex, case_sensitive
- 新增 `_map_to_builtin_font()` 静态方法：CJK/常见字体名 → PyMuPDF 内置字体名映射
- 新增 `find_text()` 方法：按条件查找匹配文本，返回 `list[TextMatchInfo]`
- 精确+大小写敏感：使用 `page.search_for()`
- 其他模式：使用 `page.get_text("rawdict")` 字符级定位
- 新增 `replace_text()` 方法：查找并替换文本，返回 `(是否修改, 替换数量, 影响页码, 消息)`
- 支持替换文本为空串（语义为删除匹配文本）

**main.py** [MODIFY]

- epilog 可用子命令列表中添加 `pdf-replace` 行
- epilog 示例中添加 pdf-replace 使用示例

## 关键代码结构

```python
@dataclass
class ReplaceCriteria:
    find: str                          # 查找文本或正则
    replace: str                       # 替换文本（空串表示删除）
    regex: bool = False                # 是否正则匹配
    case_sensitive: bool = False       # 是否大小写敏感

@dataclass
class TextMatchInfo:
    page: int                    # 1-based 页码
    rects: list[tuple]           # 匹配区域矩形列表（多行文本可能有多个 rect）
    matched_text: str            # 匹配到的文本
    fontname: str = ""           # 原始字体名
    fontsize: float = 0.0        # 原始字号
    color: int = 0               # 原始颜色
```