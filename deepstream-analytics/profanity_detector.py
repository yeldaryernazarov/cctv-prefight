import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)


def _normalize_text(s: str) -> str:
    s = s.lower().replace("ё", "е")
    # Keep letters/digits/space; OCR output can contain lots of noise.
    s = re.sub(r"[^a-zA-Zа-яА-Я0-9\s]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


class ProfanityDetector:
    """
    Profanity / swear-word detector.

    This implementation is intentionally plug-and-play:
    - By default it uses keyword matching against OCR text.
    - If `easyocr` isn't installed or keywords file missing, it becomes a no-op.
    """

    EVENT_TYPE = "PROFANITY_RISK"

    def __init__(
        self,
        *,
        enabled: bool,
        keywords: Sequence[str],
        ocr_every_n_frames: int = 15,
        event_cooldown_sec: float = 30.0,
        easyocr_languages: Optional[List[str]] = None,
        easyocr_use_gpu: bool = False,
        min_keywords_found: int = 1,
    ):
        self.enabled = bool(enabled)
        self.keywords = [k.strip().lower().replace("ё", "е") for k in keywords if k.strip()]
        self.ocr_every_n_frames = int(ocr_every_n_frames)
        self.event_cooldown_sec = float(event_cooldown_sec)
        self.min_keywords_found = int(min_keywords_found)

        self.last_event_ts = 0.0
        self._frame_idx = 0

        self.reader = None
        self.easyocr_loaded = False

        if not self.enabled or not self.keywords:
            return

        if easyocr_languages is None:
            easyocr_languages = ["ru", "en"]

        try:
            import easyocr  # type: ignore

            self.reader = easyocr.Reader(easyocr_languages, gpu=easyocr_use_gpu)
            self.easyocr_loaded = True
            logger.info("ProfanityDetector: easyocr enabled")
        except Exception as e:
            logger.warning(f"ProfanityDetector disabled (easyocr unavailable): {e}")
            self.enabled = False

    @classmethod
    def from_keywords_file(
        cls,
        *,
        enabled: bool,
        keywords_file: Optional[str],
        ocr_every_n_frames: int = 15,
        event_cooldown_sec: float = 30.0,
        easyocr_languages: Optional[List[str]] = None,
        easyocr_use_gpu: bool = False,
        min_keywords_found: int = 1,
    ) -> "ProfanityDetector":
        keywords: List[str] = []
        if keywords_file and os.path.exists(keywords_file):
            try:
                with open(keywords_file, "r", encoding="utf-8") as f:
                    # One keyword per line.
                    keywords = [line.strip() for line in f.readlines() if line.strip()]
            except Exception as e:
                logger.warning(f"Failed to read keywords file {keywords_file}: {e}")

        return cls(
            enabled=enabled,
            keywords=keywords,
            ocr_every_n_frames=ocr_every_n_frames,
            event_cooldown_sec=event_cooldown_sec,
            easyocr_languages=easyocr_languages,
            easyocr_use_gpu=easyocr_use_gpu,
            min_keywords_found=min_keywords_found,
        )

    def _ocr_text(self, frame: np.ndarray) -> str:
        if self.reader is None:
            return ""

        # easyocr returns: [ [bbox], text, confidence ]
        results = self.reader.readtext(frame, detail=1)
        texts: List[str] = []
        for item in results:
            if len(item) >= 2:
                texts.append(str(item[1]))
        return " ".join(texts)

    def update(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        if not self.enabled or self.reader is None or not self.keywords:
            return None

        self._frame_idx += 1
        if self._frame_idx % max(1, self.ocr_every_n_frames) != 0:
            return None

        now = time.time()
        if (now - self.last_event_ts) < self.event_cooldown_sec:
            return None

        try:
            raw_text = self._ocr_text(frame)
        except Exception as e:
            logger.warning(f"Profanity OCR failed: {e}")
            return None

        normalized = _normalize_text(raw_text)
        if not normalized:
            return None

        found: List[str] = []
        for kw in self.keywords:
            # Simple substring check; can be improved later to regex / fuzzy matching.
            if kw in normalized:
                found.append(kw)

        if len(found) < self.min_keywords_found:
            return None

        # Confidence is heuristic: more keywords found => higher confidence.
        conf = min(1.0, 0.5 + 0.1 * len(found))

        self.last_event_ts = now
        return {
            "type": self.EVENT_TYPE,
            "confidence": float(conf),
            "track_ids": [],
            "meta_data": {
                "found_keywords": found,
                "ocr_text": normalized[:500],
            },
        }

