"""
OCR 引擎集合
从原 pdf_scanner.py 提取并优化
"""
from __future__ import annotations

import io
import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger("pdf_scanner")


@dataclass(frozen=True)
class OCRConfig:
    """OCR 引擎配置"""
    app_id: str = ""
    api_key: str = ""
    secret_key: str = ""
    access_key: str = ""


class OCREngine(ABC):
    """OCR 引擎抽象基类"""

    @abstractmethod
    def recognize(self, image) -> str:
        """识别图片中的文字"""
        pass

    @staticmethod
    def _image_to_bytes(image, format: str = "JPEG", quality: int = 95) -> bytes:
        """将 PIL Image 转换为 bytes"""
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format=format, quality=quality)
        return img_byte_arr.getvalue()


class LocalOCREngine(OCREngine):
    """本地 Tesseract OCR"""

    def __init__(self, lang: str = "chi_sim", case_sensitive: bool = False):
        self.lang = lang
        self.case_sensitive = case_sensitive
        import pytesseract
        self._pytesseract = pytesseract

    def recognize(self, image) -> str:
        try:
            text = self._pytesseract.image_to_string(image, lang=self.lang)
            return text if self.case_sensitive else text.lower()
        except Exception as e:
            logger.error(f"本地OCR错误: {e}")
            return ""


class BaiduOCREngine(OCREngine):
    """百度 OCR — 带 QPS 速率控制与自动重试"""

    _last_request_time: float = 0.0
    _min_interval: float = 0.6
    _lock = threading.Lock()

    def __init__(self, config: OCRConfig, accuracy: str = "general_basic", case_sensitive: bool = False):
        from aip import AipOcr
        self.client = AipOcr(config.app_id, config.api_key, config.secret_key)
        self.accuracy = accuracy
        self.case_sensitive = case_sensitive
        self._method_map = {
            "accurate_basic": "basicAccurate",
            "accurate": "accurate",
            "general_basic": "basicGeneral",
            "general": "general",
        }

    def _rate_limit(self) -> None:
        """类级别速率限制，确保全局请求间隔不小于 _min_interval 秒"""
        with BaiduOCREngine._lock:
            now = time.time()
            elapsed = now - BaiduOCREngine._last_request_time
            if elapsed < BaiduOCREngine._min_interval:
                time.sleep(BaiduOCREngine._min_interval - elapsed)
            BaiduOCREngine._last_request_time = time.time()

    def recognize(self, image) -> str:
        try:
            image_bytes = self._image_to_bytes(image)
            method_name = self._method_map.get(self.accuracy, "general")
            method = getattr(self.client, method_name)

            self._rate_limit()
            res = method(image_bytes)

            # QPS 限制错误自动重试（最多 2 次，指数退避）
            retry_count = 0
            max_retries = 2
            while res.get("error_code") == 18 and retry_count < max_retries:
                retry_count += 1
                wait = 0.8 * retry_count
                logger.warning(f"百度OCR QPS超限，{wait}s 后第 {retry_count} 次重试...")
                time.sleep(wait)
                self._rate_limit()
                res = method(image_bytes)

            if "error_code" in res:
                logger.error(f"百度OCR返回错误: {res}")
                return ""

            if "words_result" in res:
                text = "\n".join(item["words"] for item in res["words_result"])
                return text if self.case_sensitive else text.lower()
            return ""
        except Exception as e:
            logger.error(f"百度OCR错误: {e}")
            return ""


class VolcOCREngine(OCREngine):
    """火山引擎 OCR"""

    def __init__(self, config: OCRConfig, case_sensitive: bool = False):
        from volcengine.visual.VisualService import VisualService
        self.client = VisualService()
        self.client.set_ak(config.access_key)
        self.client.set_sk(config.secret_key)
        self.case_sensitive = case_sensitive

    def recognize(self, image) -> str:
        try:
            import base64
            image_base64 = base64.b64encode(self._image_to_bytes(image)).decode("utf-8")
            response = self.client.ocr_normal({"image_base64": image_base64})
            time.sleep(0.5)

            if response and "data" in response and response["data"] and "line_texts" in response["data"]:
                text = "\n".join(response["data"]["line_texts"])
                return text if self.case_sensitive else text.lower()
            return ""
        except Exception as e:
            logger.error(f"火山OCR错误: {e}")
            return ""


class IflytekOCREngine(OCREngine):
    """科大讯飞 OCR"""

    def __init__(self, config: OCRConfig, case_sensitive: bool = False):
        self.config = config
        self.case_sensitive = case_sensitive

    def recognize(self, image) -> str:
        import base64
        import hashlib
        import hmac
        from datetime import datetime, timezone
        from urllib.parse import urlencode

        import requests

        host = "api.xf-yun.com"
        url = "https://api.xf-yun.com/v1/private/sf8e6aca1"
        date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

        signature_origin = f"host: {host}\ndate: {date}\nPOST /v1/private/sf8e6aca1 HTTP/1.1"
        signature = base64.b64encode(
            hmac.new(
                self.config.secret_key.encode("utf-8"),
                signature_origin.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        auth = f'api_key="{self.config.api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
        authorization = base64.b64encode(auth.encode("utf-8")).decode("utf-8")
        request_url = url + "?" + urlencode({"authorization": authorization, "date": date, "host": host})
        image_base64 = base64.b64encode(self._image_to_bytes(image)).decode("utf-8")

        body = {
            "header": {"app_id": self.config.app_id, "status": 3},
            "parameter": {
                "sf8e6aca1": {
                    "category": "ch_en_public_cloud",
                    "result": {"encoding": "utf8", "compress": "raw", "format": "json"},
                }
            },
            "payload": {"sf8e6aca1_data_1": {"encoding": "jpg", "status": 3, "image": image_base64}},
        }

        try:
            response = requests.post(
                request_url,
                json=body,
                headers={"content-type": "application/json", "host": host, "date": date},
            )
            if response.status_code != 200:
                logger.error(f"讯飞请求失败: {response.status_code}")
                return ""

            resp_json = response.json()
            if resp_json["header"]["code"] != 0:
                logger.error(f"讯飞OCR错误: {resp_json['header']['message']}")
                return ""

            text_base64 = resp_json["payload"]["result"]["text"]
            text_json = json.loads(base64.b64decode(text_base64).decode("utf-8"))

            all_text = []
            for page in text_json.get("pages", []):
                for line in page.get("lines", []):
                    line_text = "".join(w["content"] for w in line.get("words", []))
                    all_text.append(line_text)

            final_text = "\n".join(all_text)
            return final_text if self.case_sensitive else final_text.lower()
        except Exception as e:
            logger.error(f"讯飞识别异常: {e}")
            return ""


class OCREngineFactory:
    """OCR 引擎工厂"""

    _engines: dict[str, type[OCREngine]] = {
        "local": LocalOCREngine,
        "baidu": BaiduOCREngine,
        "volc": VolcOCREngine,
        "iflytek": IflytekOCREngine,
    }

    @classmethod
    def create(cls, mode: str, config: OCRConfig, **kwargs) -> OCREngine:
        if mode not in cls._engines:
            raise ValueError(f"不支持的OCR模式: {mode}，可选: {list(cls._engines.keys())}")

        engine_class = cls._engines[mode]
        if mode == "local":
            return engine_class(lang=kwargs.get("lang", "chi_sim"), case_sensitive=kwargs.get("case_sensitive", False))
        elif mode == "baidu":
            return engine_class(config, accuracy=kwargs.get("accuracy", "general_basic"), case_sensitive=kwargs.get("case_sensitive", False))
        else:
            return engine_class(config, case_sensitive=kwargs.get("case_sensitive", False))

    @classmethod
    def register(cls, name: str, engine_class: type[OCREngine]) -> None:
        """注册新的 OCR 引擎"""
        cls._engines[name] = engine_class

    @classmethod
    def available_modes(cls) -> list[str]:
        return list(cls._engines.keys())
