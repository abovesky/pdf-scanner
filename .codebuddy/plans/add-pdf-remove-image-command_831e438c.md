---
name: add-pdf-remove-image-command
overview: 新增 pdf-remove-image 子命令，支持通过 MD5 哈希或图片文件匹配并删除 PDF 中的嵌入图片（如水印图）。
todos:
  - id: add-engine-methods
    content: 在 PDFEngine 中新增图片分析与按 MD5 删除方法
    status: completed
  - id: create-remove-image-cmd
    content: 创建 pdf-remove-image 子命令模块，支持 --md5 / --image / --pages / --dry-run
    status: completed
    dependencies:
      - add-engine-methods
  - id: update-main-epilog
    content: 更新 main.py 帮助文本，注册新子命令示例
    status: completed
    dependencies:
      - create-remove-image-cmd
  - id: test-verify
    content: 本地测试：创建含图片的 PDF，验证 MD5 匹配删除与 --dry-run
    status: completed
    dependencies:
      - create-remove-image-cmd
---

## 产品概述

在现有 CLI 工具包中新增 `pdf-remove-image` 子命令，用于多维度匹配并删除 PDF 中嵌入的指定图片（如水印图片）。

## 核心功能

### 匹配方式（多条件组合）

| 参数 | 说明 | 示例 |
| --- | --- | --- |
| `--md5` | 目标图片的 MD5 哈希值，可多次传入 | `--md5 a1b2c3... --md5 d4e5f6...` |
| `--image` | 水印图片文件路径，自动计算 MD5 后匹配，可多次传入 | `--image ./wm1.png --image ./wm2.jpg` |
| `--min-width` / `--max-width` | 图片原始像素宽度范围 | `--min-width 800 --max-width 1200` |
| `--min-height` / `--max-height` | 图片原始像素高度范围 | `--min-height 100 --max-height 200` |
| `--min-size` / `--max-size` | 嵌入图片大小范围，支持 `K/M` 单位 | `--min-size 10K --max-size 5M` |
| `--format` | 嵌入图片格式过滤，可多次传入 | `--format png --format jpeg` |
| `--min-coverage` / `--max-coverage` | 图片占页面面积比例（0.0-1.0） | `--min-coverage 0.5` |
| `--has-alpha` | 匹配带透明通道的图片 | `--has-alpha` |


- **组合逻辑**：**同类条件 OR，不同类条件 AND**。例如 `--md5 a --md5 b --format png` 表示匹配"(MD5=a 或 MD5=b) 且 格式为 PNG"的图片
- **必须条件**：至少传入一种匹配条件（`--md5`、`--image`、尺寸、大小、格式、覆盖率、`--has-alpha` 之一）
- **尺寸语义**：`--min/max-width/height` 指的是嵌入图片的**原始像素尺寸**（非页面显示尺寸）

### 通用选项

- **单文件 / 目录批量处理**：`--source` 支持 PDF 文件或目录，配合 `--recursive` 递归扫描
- **页码范围限制**：可选 `--pages` 参数限制只扫描指定页面（如 `1,3,5-10`）
- **预览模式**：`--dry-run` 只报告匹配到的图片信息，不实际修改文件
- **安全备份**：默认生成 `.bak` 备份，支持 `--no-backup` 跳过
- **无匹配不保存**：未匹配到目标图片时不触发文件写入
- **加密检测**：自动检测加密 PDF，提示先使用 `pdf-decrypt` 解密

## Tech Stack Selection

- **语言**：Python 3（与现有项目一致）
- **PDF 引擎**：PyMuPDF（fitz，已在 requirements.txt 中）
- **图像处理**：Pillow（已在 requirements.txt 中，用于生成替换用的透明像素图及 Alpha 检测）
- **架构**：继承现有命令注册体系（`BaseCommand` + 自动发现）

## Implementation Approach

- **图片检测**：通过 `page.get_images(full=True)` 获取每页所有嵌入图片的 xref，提取原始字节流、尺寸、格式、大小等信息
- **信息提取**：
- MD5：对 `doc.extract_image(xref)["image"]` 字节流计算 `hashlib.md5()`，统一转小写比较
- 尺寸/格式：`doc.extract_image(xref)` 返回的 `width`、`height`、`ext`
- 字节大小：原始字节流 `len()`
- 覆盖率：通过 `page.get_image_rects(xref)` 计算图片 bbox 总面积 / `page.rect` 面积。若返回空列表则视为 coverage 未知，该条件视为不满足
- Alpha 通道：仅当 `ext == "png"` 时用 Pillow 解码检测模式是否含 `"A"`，其他格式直接视为 `False`
- **格式映射**：用户输入 `--format jpg` 时自动映射为 `jpeg`，所有比较统一小写
- **图片删除策略**：将匹配到的图片 XObject 数据流替换为 1x1 透明 PNG，并**同步修正 XObject 字典**（更新 `Width`、`Height`、`ColorSpace`、`BitsPerComponent`，清除 `Mask`、`SMask` 等冲突键），确保所有阅读器正确渲染
- **批量处理**：复用现有 `pdf_dewatermark.py` 的目录遍历、进度输出、汇总统计模式
- **页码解析**：复用现有 `parse_pages_to_check` 工具函数
- **xref 副作用说明**：`update_stream` 是文档级操作，若 xref 被多页共享，替换后所有引用页面均受影响。即使通过 `--pages` 限定扫描范围，匹配到的 xref 仍会在全局被替换。此行为在帮助文档中说明

## Architecture Design

```
main.py                     # [MODIFY] 更新 epilog 帮助文本
commands/pdf_remove_image.py # [NEW] 子命令实现
core/pdf_engine.py          # [MODIFY] 新增 ImageMatchCriteria / ImageInfo / analyze_images() / remove_images_by_criteria()
```

### 数据流

用户输入（匹配条件 + --source / --pages / --dry-run） → PdfRemoveImageCommand 参数解析并构建 `ImageMatchCriteria` → PDFEngine.analyze_images / remove_images_by_criteria → PyMuPDF 提取图片元信息 → 按条件过滤匹配 → 替换匹配图片为透明像素（同步修正字典） → 保存文件

### 新增数据类型

```python
class ImageMatchCriteria:
    md5s: list[str] | None          # MD5 哈希值列表（小写）
    min_width: int | None           # 最小原始像素宽度
    max_width: int | None           # 最大原始像素宽度
    min_height: int | None          # 最小原始像素高度
    max_height: int | None          # 最大原始像素高度
    min_size: int | None            # 最小字节大小
    max_size: int | None            # 最大字节大小
    formats: list[str] | None       # 格式列表（小写，如 ["png", "jpeg"]）
    min_coverage: float | None      # 最小覆盖率
    max_coverage: float | None      # 最大覆盖率
    has_alpha: bool | None          # 是否含透明通道

class ImageInfo:
    xref: int
    page: int                       # 首次出现的页码（1-based）
    md5: str                        # 小写 MD5
    width: int
    height: int
    size: int                       # 字节大小
    format: str                     # 扩展名，如 png/jpeg
    coverage: float | None          # 占页面面积比例（无法计算时为 None）
    has_alpha: bool
```

## Implementation Notes

- **透明替换图生成**：使用 Pillow 创建 1x1 RGBA 透明 PNG，编码为字节流。替换时同步调用 `doc.xref_set_key()` 更新 `Width=1`、`Height=1`、`ColorSpace=/DeviceRGB`、`BitsPerComponent=8`，并将 `Mask`、`SMask` 设为 `null`
- **MD5 计算**：对 `doc.extract_image(xref)["image"]` 原始字节使用 `hashlib.md5()`，结果转小写。确保与外部工具计算结果一致
- **覆盖率计算**：`page.get_image_rects(xref)` 返回图片在页面上的 bbox 列表，取总面积 / `page.rect` 面积。同一 xref 在页面可能出现多次。若返回空列表则 `coverage=None`
- **大小参数解析**：支持纯数字（字节）或带 `K/k`（KB）、`M/m`（MB）后缀，如 `10K`、`5M`，解析为整数字节
- **`--dry-run` 输出**：列出每张候选图片的 xref、page、width×height、format、size、md5、coverage、has_alpha，方便用户据此构造精确条件
- **加密检测**：处理前先调用 `PDFEngine.is_encrypted()`，加密文件直接跳过并提示
- **统计报告**：按**页面实例**计数（用户视角），但替换时按 xref 去重
- **性能**：大文件中单页图片数量通常有限（<100），信息提取为 O(总图片数)，无性能瓶颈
- **Blast radius**：`pdf_engine.py` 仅新增方法/类，不改动现有方法签名；`main.py` 仅更新帮助文本字符串