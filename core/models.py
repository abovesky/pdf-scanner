"""
数据模型定义
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal


class FileStatus(str, Enum):
    """文件处理状态"""
    MODIFIED = "modified"
    UNMODIFIED = "unmodified"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ScanResult:
    """单个文件的扫描结果"""
    file_name: str
    file_path: Path
    status: FileStatus
    matched_pages: list[int] = field(default_factory=list)
    blank_pages_removed: int = 0
    total_pages: int = 0
    message: str = ""
    elapsed_seconds: float = 0.0


@dataclass
class ScanProgress:
    """扫描进度数据"""
    scanned_files: set[str] = field(default_factory=set)
    modified_files: set[str] = field(default_factory=set)
    unmodified_files: set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        return {
            "scanned_files": sorted(self.scanned_files),
            "modified_files": sorted(self.modified_files),
            "unmodified_files": sorted(self.unmodified_files),
        }

    @classmethod
    def from_dict(cls, data: dict) -> ScanProgress:
        return cls(
            scanned_files=set(data.get("scanned_files", [])),
            modified_files=set(data.get("modified_files", [])),
            unmodified_files=set(data.get("unmodified_files", [])),
        )
