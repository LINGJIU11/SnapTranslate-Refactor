"""Tesseract OCR 适配器（原 ``main.py:1069-1206``）。

把原版散在应用逻辑里的四件事收敛到这里：依赖探测、Tesseract 可执行文件挑选、
语言包探测与 ``TESSDATA_PREFIX`` 修正、截屏（含超大区域降采样）与识别。
"""

from __future__ import annotations

import os
from typing import Any

from snaptranslate.config.paths import (
    FORCE_TESSERACT_PATH,
    OCR_LANG,
    OCR_MAX_PIXELS,
    TESSERACT_CANDIDATE_DIRS,
)
from snaptranslate.domain.errors import OcrError, OcrUnavailableError
from snaptranslate.domain.models.geometry import BBox
from snaptranslate.domain.ports.ocr import OcrStage, StageCallback

try:  # pragma: no cover - 依赖缺失时保持与原版一致的降级行为
    from PIL import ImageGrab
except Exception:  # pragma: no cover
    ImageGrab = None  # type: ignore[assignment]

try:  # pragma: no cover
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None  # type: ignore[assignment]


class TesseractOcrEngine:
    """实现 :class:`~snaptranslate.domain.ports.ocr.OcrEngine`。"""

    def __init__(
        self,
        *,
        ocr_lang: str = OCR_LANG,
        max_pixels: int = OCR_MAX_PIXELS,
        candidate_dirs: tuple[str, ...] = TESSERACT_CANDIDATE_DIRS,
        force_path: str = FORCE_TESSERACT_PATH,
        image_grab: Any = ImageGrab,
        pytesseract_module: Any = pytesseract,
    ) -> None:
        self._ocr_lang = ocr_lang
        self._max_pixels = max_pixels
        self._candidate_dirs = candidate_dirs
        self._force_path = force_path
        self._grab = image_grab
        self._tess = pytesseract_module
        self._langs_cache: set[str] | None = None

    @property
    def is_available(self) -> bool:
        return self._grab is not None and self._tess is not None

    # —— 主流程 ——
    def extract_text(self, bbox: BBox, on_stage: StageCallback | None = None) -> str:
        if not self.is_available:
            raise OcrUnavailableError(
                "OCR 不可用",
                detail="缺少 OCR 依赖：请安装 pillow 与 pytesseract，并确保系统已安装 Tesseract-OCR。",
            )

        tesseract_bin = self.pick_tesseract_binary()
        if tesseract_bin:
            self._tess.pytesseract.tesseract_cmd = tesseract_bin
        tessdata_dir, lang_files = self._discover_tessdata(tesseract_bin)
        langs = self._select_langs(tessdata_dir, lang_files)

        if on_stage:
            on_stage(OcrStage.CAPTURING)
        old_prefix = os.environ.get("TESSDATA_PREFIX")
        image = None
        try:
            if tessdata_dir:
                # 强制覆盖错误的全局 TESSDATA_PREFIX（例如指向 E:\tes）
                os.environ["TESSDATA_PREFIX"] = tessdata_dir
            image = self._grab.grab(bbox=bbox.as_tuple(), all_screens=True)
            try:
                width, height = image.size
                if width > 0 and height > 0:
                    pixels = width * height
                    if pixels > self._max_pixels:
                        scale = (self._max_pixels / float(pixels)) ** 0.5
                        image = image.resize((max(1, int(width * scale)), max(1, int(height * scale))))
            except Exception:
                pass
            if on_stage:
                on_stage(OcrStage.RECOGNIZING)
            text = self._tess.image_to_string(image, lang=langs)
        except OcrError:
            raise
        except Exception as exc:
            message = str(exc)
            if "TESSDATA_PREFIX" in message or "couldn't load any languages" in message.lower():
                message = (
                    "OCR 失败：未找到可用语言包。请安装 Tesseract 的 eng/chi_sim 语言文件，"
                    "或修正 TESSDATA_PREFIX 到 tessdata 目录。"
                )
            detail = f"[tesseract={tesseract_bin or '未找到'} | tessdata={tessdata_dir or '未找到'} | lang={langs}]"
            raise OcrError(message, detail=detail, cause=exc) from exc
        finally:
            if image is not None:
                try:
                    image.close()
                except Exception:
                    pass
            if old_prefix is None:
                os.environ.pop("TESSDATA_PREFIX", None)
            else:
                os.environ["TESSDATA_PREFIX"] = old_prefix
        return text

    # —— 可执行文件与语言包 ——
    def pick_tesseract_binary(self) -> str | None:
        """选择最合适的 ``tesseract.exe``（原 ``_pick_tesseract_binary``）。

        优先官方默认目录且语言包齐全，避免被历史 PATH 中的旧版本（如 ``E:\\tes``）劫持。
        """
        if os.path.isfile(self._force_path):
            return self._force_path

        candidates: list[str] = []
        for base in self._candidate_dirs:
            candidate = os.path.join(base, "tesseract.exe")
            if os.path.isfile(candidate):
                candidates.append(candidate)
        from_path = shutil_which("tesseract")
        if from_path and from_path not in candidates:
            candidates.append(from_path)
        if not candidates:
            return None
        # 分值越高越好：优先中英齐全，其次仅英文；同分时取先出现者（max 语义）
        return max(candidates, key=self._lang_score)

    @staticmethod
    def _lang_score(exe_path: str) -> tuple[int, int]:
        tessdata = os.path.join(os.path.dirname(exe_path), "tessdata")
        if not os.path.isdir(tessdata):
            return (0, 0)
        has_eng = os.path.isfile(os.path.join(tessdata, "eng.traineddata"))
        has_zh = os.path.isfile(os.path.join(tessdata, "chi_sim.traineddata"))
        return (1 if has_eng else 0) + (2 if has_zh else 0), 1

    @staticmethod
    def _discover_tessdata(tesseract_bin: str | None) -> tuple[str, set[str]]:
        tessdata_dir = ""
        lang_files: set[str] = set()
        if tesseract_bin:
            maybe_dir = os.path.join(os.path.dirname(tesseract_bin), "tessdata")
            if os.path.isdir(maybe_dir):
                tessdata_dir = maybe_dir
                for name in os.listdir(maybe_dir):
                    if name.endswith(".traineddata"):
                        lang_files.add(name.replace(".traineddata", ""))
        return tessdata_dir, lang_files

    def _select_langs(self, tessdata_dir: str, lang_files: set[str]) -> str:
        """按可用语言包选择识别语言（原版逻辑：中英齐全用 ``eng+chi_sim``，否则退而求其次）。"""
        langs = self._ocr_lang
        if self._langs_cache is None:
            try:
                self._langs_cache = set(self._tess.get_languages())
            except Exception:
                self._langs_cache = set()
        known = self._langs_cache or lang_files
        if known:
            if {"eng", "chi_sim"}.issubset(known):
                langs = "eng+chi_sim"
            elif "eng" in known:
                langs = "eng"
            elif "chi_sim" in known:
                langs = "chi_sim"
            else:
                langs = next(iter(known))
        return langs


def shutil_which(command: str) -> str | None:
    """薄封装 ``shutil.which``（单独成函数便于测试替换）。"""
    import shutil

    return shutil.which(command)
