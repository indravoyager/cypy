"""
cypy/core/services/font_service.py
✦ Font Management Service — Instant Local Assets Font Provider~ ♪ ✦

Uses bundled local assets (Komika Axis.ttf for Latin, KosugiMaru.ttf for CJK/non-Latin).
100% offline, zero network requests, zero freezing.
"""
import os
import re
import sys
import threading
import types
from typing import Dict, Optional, Tuple

from PIL import ImageFont

import cypy.core.config as config


# ==========================================
# ✦ LOCAL BUNDLED FONT PATHS ✦
# ==========================================
FONT_MANGA = config.FONT_MANGA  # Komika Axis.ttf
FONT_UNIVERSAL = os.path.join(config.ASSETS_DIR, "KosugiMaru.ttf")  # Full CJK/Unicode font


# Regex for non-Latin script letters (CJK, Hiragana, Katakana, Hangul, Thai, Cyrillic, Arabic)
_NON_LATIN_SCRIPT_REGEX = re.compile(
    r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\uac00-\ud7af\u0e00-\u0e7f\u0400-\u04ff\u0600-\u06ff]'
)


# ==========================================
# ✦ THREAD-SAFE FONT OBJECT CACHING ✦
# ==========================================
_font_lock = threading.Lock()
_font_object_cache: Dict[Tuple[str, int], Optional[ImageFont.FreeTypeFont]] = {}


def _get_font_object(path: str, size: int) -> Optional[ImageFont.FreeTypeFont]:
    """Return a cached PIL ImageFont instance for (path, size), loading if needed."""
    key = (path, int(size))
    with _font_lock:
        if key in _font_object_cache:
            return _font_object_cache[key]

    font = None
    try:
        if os.path.exists(path):
            font = ImageFont.truetype(path, int(size))
    except Exception:
        font = None

    if font is None:
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

    if font is not None and not hasattr(font, 'getsize'):
        try:
            def _getsize(txt, f=font):
                m = f.getmask(txt)
                return m.size

            font.getsize = types.MethodType(lambda self, txt: _getsize(txt), font)
        except Exception:
            pass

    with _font_lock:
        _font_object_cache[key] = font
    return font


def has_non_latin(text: str) -> bool:
    """Check if text contains CJK, Cyrillic, Thai, or Asian script letters."""
    return bool(_NON_LATIN_SCRIPT_REGEX.search(str(text)))


def get_font_for_text(text: str, size: int, language: Optional[str] = None) -> ImageFont.FreeTypeFont:
    """
    Returns the appropriate local font for the given text and target language.
    100% offline, zero network requests:
    - Non-Latin / CJK scripts -> KosugiMaru.ttf (Universal CJK asset)
    - Latin scripts -> Komika Axis.ttf (Manga font asset)
    """
    # Non-Latin (Japanese, Korean, Chinese, Thai, Cyrillic, etc.)
    if has_non_latin(text):
        font = _get_font_object(FONT_UNIVERSAL, size)
        if font:
            return font

    # Latin text -> Always prefer Komika Axis.ttf (FONT_MANGA)
    font = _get_font_object(FONT_MANGA, size)
    if font:
        return font

    # Fallback to universal asset font
    font = _get_font_object(FONT_UNIVERSAL, size)
    if font:
        return font

    return ImageFont.load_default()
