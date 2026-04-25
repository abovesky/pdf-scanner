"""
配置管理模块
支持 .env 环境变量、settings.json 配置文件、环境变量三源合并
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

_DEFAULT_KEYWORDS = ["出版发行", "侵权", "版权"]


class AppConfig:
    """应用配置"""

    def __init__(self):
        # 目录配置
        self.source_dir: Path = Path(".")
        self.source_path: Path | None = None  # 命令行指定的源路径（文件或目录）
        self.source_files: list[Path] | None = None  # 指定的单文件列表（覆盖 glob 扫描）

        # 扫描参数
        self.keywords: list[str] = _DEFAULT_KEYWORDS.copy()
        self.search_logic: Literal["AND", "OR"] = "AND"
        self.case_sensitive: bool = False
        self.pages_to_check: str = "-1"
        self.dry_run: bool = False
        self.debug_mode: bool = False

        # OCR 配置
        self.recognition_mode: str = "baidu"
        self.ocr_accuracy: str = "accurate_basic"
        self.ocr_lang: str = "chi_sim"
        self.dpi: int = 150
        self.filter_spaces: bool = True
        self.fuzzy_match: bool = True
        self.max_interfering_chars: int = 2

        # 并发配置
        self.max_workers: int = 4
        self.ocr_max_workers: int = 2

        # 进度文件
        self.resume_file: Path = Path("pdf_scan_progress.json")

        # OCR 密钥（从 .env 或环境变量读取）
        self.baidu_app_id: str = ""
        self.baidu_api_key: str = ""
        self.baidu_secret_key: str = ""
        self.volc_access_key: str = ""
        self.volc_secret_key: str = ""
        self.iflytek_app_id: str = ""
        self.iflytek_api_key: str = ""
        self.iflytek_secret_key: str = ""

        self._load_env()
        self._load_settings_file()

    def _load_env(self) -> None:
        """从 .env 文件和环境变量加载敏感配置"""
        env_path = Path(__file__).parent.parent / ".env"

        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        else:
            import logging
            logging.getLogger("pdf_scanner").warning(f".env 文件未找到: {env_path}")

        # 从环境变量读取
        self.baidu_app_id = os.getenv("BAIDU_APP_ID", "")
        self.baidu_api_key = os.getenv("BAIDU_API_KEY", "")
        self.baidu_secret_key = os.getenv("BAIDU_SECRET_KEY", "")
        self.volc_access_key = os.getenv("VOLC_ACCESS_KEY", "")
        self.volc_secret_key = os.getenv("VOLC_SECRET_KEY", "")
        self.iflytek_app_id = os.getenv("IFLYTEK_APP_ID", "")
        self.iflytek_api_key = os.getenv("IFLYTEK_API_KEY", "")
        self.iflytek_secret_key = os.getenv("IFLYTEK_SECRET_KEY", "")

    def _load_settings_file(self) -> None:
        """从 settings.json 加载非敏感配置"""
        settings_path = self._get_settings_path()
        if not settings_path.exists():
            return
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._apply_dict(data)
        except Exception:
            pass

    def save_settings(self) -> None:
        """保存当前配置到 settings.json"""
        data = {
            "source_dir": str(self.source_dir),
            "keywords": self.keywords,
            "search_logic": self.search_logic,
            "case_sensitive": self.case_sensitive,
            "pages_to_check": self.pages_to_check,
            "debug_mode": self.debug_mode,
            "recognition_mode": self.recognition_mode,
            "ocr_accuracy": self.ocr_accuracy,
            "ocr_lang": self.ocr_lang,
            "dpi": self.dpi,
            "filter_spaces": self.filter_spaces,
            "fuzzy_match": self.fuzzy_match,
            "max_interfering_chars": self.max_interfering_chars,
            "max_workers": self.max_workers,
            "ocr_max_workers": self.ocr_max_workers,
        }
        settings_path = self._get_settings_path()
        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise RuntimeError(f"保存配置失败: {e}")

    def _apply_dict(self, data: dict) -> None:
        """从字典应用配置"""
        if "source_dir" in data:
            self.source_dir = Path(data["source_dir"])
        if "keywords" in data:
            self.keywords = data["keywords"]
        if "search_logic" in data:
            self.search_logic = data["search_logic"]
        if "case_sensitive" in data:
            self.case_sensitive = data["case_sensitive"]
        if "pages_to_check" in data:
            self.pages_to_check = data["pages_to_check"]
        if "debug_mode" in data:
            self.debug_mode = data["debug_mode"]
        if "recognition_mode" in data:
            self.recognition_mode = data["recognition_mode"]
        if "ocr_accuracy" in data:
            self.ocr_accuracy = data["ocr_accuracy"]
        if "ocr_lang" in data:
            self.ocr_lang = data["ocr_lang"]
        if "dpi" in data:
            self.dpi = data["dpi"]
        if "filter_spaces" in data:
            self.filter_spaces = data["filter_spaces"]
        if "fuzzy_match" in data:
            self.fuzzy_match = data["fuzzy_match"]
        if "max_interfering_chars" in data:
            self.max_interfering_chars = data["max_interfering_chars"]
        if "max_workers" in data:
            self.max_workers = data["max_workers"]
        if "ocr_max_workers" in data:
            self.ocr_max_workers = data["ocr_max_workers"]

    def _get_app_data_dir(self) -> Path:
        """获取项目根目录"""
        return Path(__file__).parent.parent

    def _get_settings_path(self) -> Path:
        """获取配置文件路径"""
        return self._get_app_data_dir() / "settings.json"

    def get_resume_file_path(self) -> Path:
        """获取进度文件路径"""
        return self._get_app_data_dir() / "pdf_scan_progress.json"

    def validate(self) -> list[str]:
        """验证配置，返回错误信息列表"""
        errors = []
        if not self.source_dir.exists():
            errors.append(f"源目录不存在: {self.source_dir}")
        if not self.keywords:
            errors.append("关键词不能为空")
        if self.search_logic not in ("AND", "OR"):
            errors.append("搜索逻辑必须是 AND 或 OR")
        if self.recognition_mode not in ("local", "baidu", "volc", "iflytek"):
            errors.append(f"不支持的 OCR 模式: {self.recognition_mode}")

        # 检查 OCR 密钥是否配置
        key_checks = {
            "baidu": [("BAIDU_API_KEY", self.baidu_api_key), ("BAIDU_SECRET_KEY", self.baidu_secret_key)],
            "volc": [("VOLC_ACCESS_KEY", self.volc_access_key), ("VOLC_SECRET_KEY", self.volc_secret_key)],
            "iflytek": [("IFLYTEK_APP_ID", self.iflytek_app_id), ("IFLYTEK_API_KEY", self.iflytek_api_key), ("IFLYTEK_SECRET_KEY", self.iflytek_secret_key)],
        }
        if self.recognition_mode in key_checks:
            missing = [name for name, val in key_checks[self.recognition_mode] if not val]
            if missing:
                errors.append(f"OCR 模式 '{self.recognition_mode}' 缺少密钥配置: {', '.join(missing)}，请在 .env 文件或环境变量中设置")

        return errors
