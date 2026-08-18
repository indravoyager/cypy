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


def get_system_font_map() -> Dict[str, str]:
    """
    Scans system font directories (Windows, Linux, macOS) for clean, popular font families.
    Filters out hundreds of raw font variants to ensure instant 0ms UI dropdown loading.
    """
    font_map: Dict[str, str] = {}
    dirs = []
    if sys.platform == "win32":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        dirs = [
            os.path.join(windir, "Fonts"),
            os.path.expanduser(r"~\AppData\Local\Microsoft\Windows\Fonts")
        ]
    elif sys.platform == "darwin":
        dirs = ["/Library/Fonts", "/System/Library/Fonts", os.path.expanduser("~/Library/Fonts")]
    else:
        dirs = [
            "/usr/share/fonts", "/usr/local/share/fonts",
            os.path.expanduser("~/.fonts"), os.path.expanduser("~/.local/share/fonts")
        ]

    FAMILY_MAP = [
        ("Arial", ["arial.ttf", "arial.otf"]),
        ("Calibri", ["calibri.ttf", "calibri.otf"]),
        ("Comic Sans MS", ["comic.ttf", "comic.otf"]),
        ("Consolas", ["consolas.ttf", "consolas.otf"]),
        ("Courier New", ["courier.ttf", "cour.ttf"]),
        ("Georgia", ["georgia.ttf"]),
        ("Impact", ["impact.ttf"]),
        ("Lucida Console", ["lucon.ttf"]),
        ("Segoe UI", ["segoeui.ttf"]),
        ("Tahoma", ["tahoma.ttf"]),
        ("Times New Roman", ["times.ttf"]),
        ("Trebuchet MS", ["trebuc.ttf"]),
        ("Verdana", ["verdana.ttf"]),
        ("Garamond", ["gara.ttf"]),
        ("Palatino", ["pala.ttf"]),
        ("Century Gothic", ["gothic.ttf"]),
    ]

    all_found: Dict[str, str] = {}
    for d in dirs:
        if os.path.exists(d):
            for root, _, files in os.walk(d):
                for f in files:
                    if f.lower().endswith((".ttf", ".otf")):
                        all_found[f.lower()] = os.path.join(root, f)

    # 1. Add curated popular font families first
    for family_name, file_candidates in FAMILY_MAP:
        for fc in file_candidates:
            if fc.lower() in all_found:
                font_map[family_name] = all_found[fc.lower()]
                break

    # 2. Add custom user installed fonts (e.g. AppData font dir or ~/.local/share/fonts)
    for file_name, full_path in all_found.items():
        if len(font_map) >= 25:
            break
        if "appdata" in full_path.lower() or ".local" in full_path.lower():
            clean_name = os.path.splitext(os.path.basename(full_path))[0].replace("_", " ").title()
            if clean_name not in font_map:
                font_map[clean_name] = full_path

    return font_map


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
        if len(_font_object_cache) >= 500:
            try:
                first_key = next(iter(_font_object_cache))
                _font_object_cache.pop(first_key, None)
            except Exception:
                pass
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

    # Latin text -> Always prefer configured manga font (config.FONT_MANGA)
    manga_font_path = config.FONT_MANGA
    font = _get_font_object(manga_font_path, size)
    if font:
        return font

    # Fallback to universal asset font
    font = _get_font_object(FONT_UNIVERSAL, size)
    if font:
        return font

    return ImageFont.load_default()
