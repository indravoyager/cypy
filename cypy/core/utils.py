import cv2
import os
import sys
import zipfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    import requests as _requests
except ImportError:
    _requests = None

import cypy.core.config as config

# ==========================================
# ✦ FONT MANAGEMENT - Smart font selection & auto-download~ ♪ ✦
# ==========================================

# Path to the bundled Japanese font
FONT_JAPANESE = os.path.join(config.ASSETS_DIR, "KosugiMaru.ttf")

# Directory to cache downloaded fonts
FONT_CACHE_DIR = os.path.join(config.ROOT_DIR, "cypy_cache", "fonts")

# The currently active target language (set by app.py before translation)
_active_target_language = None

# Font cache to avoid repeated lookups
_font_path_cache = {}

# Language → Google Fonts family name mapping for Noto Sans variants
_NOTO_SANS_MAP = {
    "korean": "Noto+Sans+KR",
    "chinese": "Noto+Sans+SC",
    "chinese (simplified)": "Noto+Sans+SC",
    "chinese (traditional)": "Noto+Sans+TC",
    "mandarin": "Noto+Sans+SC",
    "thai": "Noto+Sans+Thai",
    "arabic": "Noto+Sans+Arabic",
    "hindi": "Noto+Sans+Devanagari",
    "bengali": "Noto+Sans+Bengali",
    "tamil": "Noto+Sans+Tamil",
    "telugu": "Noto+Sans+Telugu",
    "russian": "Noto+Sans",
    "ukrainian": "Noto+Sans",
    "greek": "Noto+Sans",
    "hebrew": "Noto+Sans+Hebrew",
    "georgian": "Noto+Sans+Georgian",
    "armenian": "Noto+Sans+Armenian",
    "burmese": "Noto+Sans+Myanmar",
    "khmer": "Noto+Sans+Khmer",
    "lao": "Noto+Sans+Lao",
    "tibetan": "Noto+Sans+Tibetan",
    "mongolian": "Noto+Sans+Mongolian",
    "vietnamese": "Noto+Sans",
    "malay": "Noto+Sans",
    "turkish": "Noto+Sans",
    "persian": "Noto+Sans+Arabic",
    "urdu": "Noto+Sans+Arabic",
}


def set_active_language(language):
    """Set the current target language (called from app.py/translator)."""
    global _active_target_language
    _active_target_language = language.lower() if language else None


def _has_non_latin(text):
    """Check if text contains characters outside the basic Latin + Latin Extended range."""
    for ch in text:
        cp = ord(ch)
        # Allow ASCII + Latin Extended-A/B + Latin Supplement + common punctuation
        if cp > 0x024F and ch not in ' \t\n\r.,!?;:\'"\\-()[]{}…—–·•«»¡¿♪~':
            return True
    return False

_DIRECT_FONT_MAP = {
    "korean": ("https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/Korean/NotoSansCJKkr-Regular.otf", ".otf"),
    "chinese (simplified)": ("https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf", ".otf"),
    "chinese": ("https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf", ".otf"),
    "china": ("https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf", ".otf"),
    "chinese (traditional)": ("https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf", ".otf"),
    "mandarin": ("https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf", ".otf"),
    "thai": ("https://github.com/google/fonts/raw/main/ofl/notosansthai/NotoSansThai%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "thailand": ("https://github.com/google/fonts/raw/main/ofl/notosansthai/NotoSansThai%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "arabic": ("https://github.com/google/fonts/raw/main/ofl/notosansarabic/NotoSansArabic%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "urdu": ("https://github.com/google/fonts/raw/main/ofl/notosansarabic/NotoSansArabic%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "pakistan": ("https://github.com/google/fonts/raw/main/ofl/notosansarabic/NotoSansArabic%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "russian": ("https://github.com/google/fonts/raw/main/ofl/notosans/NotoSans%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "russia": ("https://github.com/google/fonts/raw/main/ofl/notosans/NotoSans%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "vietnamese": ("https://github.com/google/fonts/raw/main/ofl/notosans/NotoSans%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "vietnam": ("https://github.com/google/fonts/raw/main/ofl/notosans/NotoSans%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "bengali": ("https://github.com/google/fonts/raw/main/ofl/notosansbengali/NotoSansBengali%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "bangladesh": ("https://github.com/google/fonts/raw/main/ofl/notosansbengali/NotoSansBengali%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "hindi": ("https://github.com/google/fonts/raw/main/ofl/notosansdevanagari/NotoSansDevanagari%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "india": ("https://github.com/google/fonts/raw/main/ofl/notosansdevanagari/NotoSansDevanagari%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "hebrew": ("https://github.com/google/fonts/raw/main/ofl/notosanshebrew/NotoSansHebrew%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "tamil": ("https://github.com/google/fonts/raw/main/ofl/notosanstamil/NotoSansTamil%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "myanmar": ("https://github.com/google/fonts/raw/main/ofl/notosansmyanmar/NotoSansMyanmar%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "burmese": ("https://github.com/google/fonts/raw/main/ofl/notosansmyanmar/NotoSansMyanmar%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    
    "mongolia": ("https://github.com/google/fonts/raw/main/ofl/notosansmongolian/NotoSansMongolian-Regular.ttf", ".ttf"),
    "mongolian": ("https://github.com/google/fonts/raw/main/ofl/notosansmongolian/NotoSansMongolian-Regular.ttf", ".ttf"),
    "kamboja": ("https://github.com/google/fonts/raw/main/ofl/notosanskhmer/NotoSansKhmer%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "khmer": ("https://github.com/google/fonts/raw/main/ofl/notosanskhmer/NotoSansKhmer%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "laos": ("https://github.com/google/fonts/raw/main/ofl/notosanslao/NotoSansLao%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "lao": ("https://github.com/google/fonts/raw/main/ofl/notosanslao/NotoSansLao%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "telugu": ("https://github.com/google/fonts/raw/main/ofl/notosanstelugu/NotoSansTelugu%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "kannada": ("https://github.com/google/fonts/raw/main/ofl/notosanskannada/NotoSansKannada%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "malayalam": ("https://github.com/google/fonts/raw/main/ofl/notosansmalayalam/NotoSansMalayalam%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "gujarati": ("https://github.com/google/fonts/raw/main/ofl/notosansgujarati/NotoSansGujarati%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "punjabi": ("https://github.com/google/fonts/raw/main/ofl/notosansgurmukhi/NotoSansGurmukhi%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "gurmukhi": ("https://github.com/google/fonts/raw/main/ofl/notosansgurmukhi/NotoSansGurmukhi%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "georgia": ("https://github.com/google/fonts/raw/main/ofl/notosansgeorgian/NotoSansGeorgian%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "georgian": ("https://github.com/google/fonts/raw/main/ofl/notosansgeorgian/NotoSansGeorgian%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "armenia": ("https://github.com/google/fonts/raw/main/ofl/notosansarmenian/NotoSansArmenian%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "armenian": ("https://github.com/google/fonts/raw/main/ofl/notosansarmenian/NotoSansArmenian%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "kazakhstan": ("https://github.com/google/fonts/raw/main/ofl/notosans/NotoSans%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "kazakh": ("https://github.com/google/fonts/raw/main/ofl/notosans/NotoSans%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "uzbekistan": ("https://github.com/google/fonts/raw/main/ofl/notosans/NotoSans%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "uzbek": ("https://github.com/google/fonts/raw/main/ofl/notosans/NotoSans%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "kirgizstan": ("https://github.com/google/fonts/raw/main/ofl/notosans/NotoSans%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "kyrgyz": ("https://github.com/google/fonts/raw/main/ofl/notosans/NotoSans%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "kyrgyzstan": ("https://github.com/google/fonts/raw/main/ofl/notosans/NotoSans%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "ethiopia": ("https://github.com/google/fonts/raw/main/ofl/notosansethiopic/NotoSansEthiopic%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "amharic": ("https://github.com/google/fonts/raw/main/ofl/notosansethiopic/NotoSansEthiopic%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "eritrea": ("https://github.com/google/fonts/raw/main/ofl/notosansethiopic/NotoSansEthiopic%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "tigrinya": ("https://github.com/google/fonts/raw/main/ofl/notosansethiopic/NotoSansEthiopic%5Bwdth%2Cwght%5D.ttf", ".ttf"),
    "tigre": ("https://github.com/google/fonts/raw/main/ofl/notosansethiopic/NotoSansEthiopic%5Bwdth%2Cwght%5D.ttf", ".ttf")
}

def _download_noto_font(language):
    """
    Downloads Noto Sans font. For mapped languages, uses direct github links for full unsubsetted fonts.
    For everything else, tries CSS API as fallback.
    """
    if _requests is None:
        print("  [!] 'requests' library is not installed. Custom fonts cannot be downloaded automatically.")
        return None

    if not os.path.exists(FONT_CACHE_DIR):
        os.makedirs(FONT_CACHE_DIR)

    lang_key = language.lower()

    if lang_key in _DIRECT_FONT_MAP:
        url, ext = _DIRECT_FONT_MAP[lang_key]
        safe_name = f"NotoSans_{lang_key.replace(' ', '')}_v3"
        cached_file = os.path.join(FONT_CACHE_DIR, f"{safe_name}{ext}")
        
        if os.path.exists(cached_file):
            return cached_file
            
        print(f"  [Font] Downloading full font {safe_name}{ext}...")
        
        try:
            response = _requests.get(url, stream=True, timeout=30, allow_redirects=True)
            if response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0
                
                with open(cached_file, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            if total_size > 0:
                                percent = int(downloaded_size * 100 / total_size)
                                sys.stdout.write(f"\r  [Font] Downloading... {percent}% ({downloaded_size//1024}KB / {total_size//1024}KB)")
                                sys.stdout.flush()
                print() # newline
                return cached_file
            else:
                print(f"  [!] Font download failed with status: {response.status_code}")
        except Exception as e:
            print(f"  [!] Font download error: {e}")
            
        return None

    # Fallback to Google Fonts CSS API for other unmapped languages
    import re
    font_family = _NOTO_SANS_MAP.get(lang_key)
    if not font_family:
        for key, family in _NOTO_SANS_MAP.items():
            if key in lang_key or lang_key in key:
                font_family = family
                break

    if not font_family:
        font_family = "Noto+Sans"

    safe_name = font_family.replace("+", "").replace(" ", "")
    cached_ttf = os.path.join(FONT_CACHE_DIR, f"{safe_name}.ttf")

    if os.path.exists(cached_ttf):
        return cached_ttf

    print(f"  [Font] Fetching {font_family.replace('+', ' ')} from Google Fonts...")
    css_url = f"https://fonts.googleapis.com/css?family={font_family}"
    headers = {'User-Agent': 'Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1)'}
    
    try:
        css_resp = _requests.get(css_url, headers=headers, timeout=15)
        if css_resp.status_code == 200:
            match = re.search(r"url\((https://[^)]+)\)", css_resp.text)
            if match:
                ttf_url = match.group(1).strip("'\"")
                ttf_resp = _requests.get(ttf_url, stream=True, timeout=30)
                if ttf_resp.status_code == 200:
                    with open(cached_ttf, "wb") as f:
                        for chunk in ttf_resp.iter_content(chunk_size=8192):
                            f.write(chunk)
                    print(f"  [Font] Downloaded successfully: {os.path.basename(cached_ttf)}")
                    return cached_ttf
    except Exception as e:
        print(f"  [!] Font download error: {e}")
        
    return None


def _get_font_for_text(text, size, language=None):
    """
    Returns the appropriate font for the given text and target language.
    Priority: KosugiMaru (Japanese) → Downloaded Noto Sans (custom) → FONT_MANGA (Latin)~ ♪
    """
    if _has_non_latin(text):
        lang = language.lower() if language else ""
        if lang == "jepang":
            lang = "japanese"

        # Japanese uses bundled KosugiMaru.ttf
        if lang == "japanese" and os.path.exists(FONT_JAPANESE):
            try:
                return ImageFont.truetype(FONT_JAPANESE, size)
            except Exception:
                pass

        # Check cache first
        cache_key = f"lang_{lang}"
        if cache_key in _font_path_cache:
            cached = _font_path_cache[cache_key]
            if cached:
                try:
                    return ImageFont.truetype(cached, size)
                except Exception:
                    pass

        # Try downloading Noto Sans for this language
        if lang:
            noto_path = _download_noto_font(lang)
            _font_path_cache[cache_key] = noto_path
            if noto_path:
                try:
                    return ImageFont.truetype(noto_path, size)
                except Exception:
                    pass

        # Last resort: try KosugiMaru (covers CJK well)
        if os.path.exists(FONT_JAPANESE):
            try:
                return ImageFont.truetype(FONT_JAPANESE, size)
            except Exception:
                pass

    try:
        return ImageFont.truetype(config.FONT_MANGA, size)
    except Exception:
        return ImageFont.load_default()


def bersihkan_json_dari_gemini(teks_mentah):
    """Cleans Gemini's raw output so it can be parsed by json.loads() ♪"""
    teks = teks_mentah.strip()

    if teks.startswith("```json"):
        teks = teks[7:].strip()

    if teks.startswith("```"):
        teks = teks[3:].strip()

    if teks.endswith("```"):
        teks = teks[:-3].strip()

    awal = teks.find("{")
    akhir = teks.rfind("}")

    if awal != -1 and akhir != -1 and akhir > awal:
        teks = teks[awal:akhir + 1]

    return teks.strip()




def pecah_kata_hyphen_jika_panjang(draw, word, font, max_w):
    """
    Splits hyphenated words if they are too long. 
    Normal words without hyphens remain untouched~
    """
    word = str(word)

    bbox = draw.textbbox((0, 0), word, font=font)
    word_w = bbox[2] - bbox[0]

    if word_w <= max_w:
        return [word]

    if "-" not in word:
        return [word]

    parts = word.split("-")
    tokens = []

    for i, part in enumerate(parts):
        if part == "":
            continue

        if i < len(parts) - 1:
            tokens.append(part + "-")
        else:
            tokens.append(part)

    return tokens if tokens else [word]


def bungkus_teks_per_kata(draw, text, font, max_w):
    """
    Wraps text based on word widths. 
    Hyphenated words may be split at hyphens to allow larger font sizes~ ♪
    Supports languages without spaces (like Chinese) by splitting by character.
    """
    text = str(text)
    
    # If text has no spaces and contains non-latin chars (like Chinese), 
    # treat each character as a word for wrapping purposes.
    if " " not in text and _has_non_latin(text):
        raw_words = list(text)
    else:
        raw_words = text.split()

    if not raw_words:
        return ""

    words = []
    for word in raw_words:
        words.extend(pecah_kata_hyphen_jika_panjang(draw, word, font, max_w))

    lines = []
    current = ""

    for word in words:
        # If splitting by character, don't add spaces between "words"
        if " " not in text and _has_non_latin(text):
            candidate = word if current == "" else current + word
        else:
            candidate = word if current == "" else current + " " + word
            
        bbox = draw.textbbox((0, 0), candidate, font=font)
        candidate_w = bbox[2] - bbox[0]

        if candidate_w <= max_w:
            current = candidate
        else:
            if current:
                lines.append(current)
                current = word
            else:
                # If a single word is extremely long and doesn't have a hyphen,
                # we don't force split. Auto-fit will handle shrinking the font.
                lines.append(word)
                current = ""

    if current:
        lines.append(current)

    return "\n".join(lines)


def hitung_bbox_multiline(draw, text, font, spacing):
    """Calculates multiline text bounding box safely~"""
    return draw.multiline_textbbox(
        (0, 0),
        text,
        font=font,
        align="center",
        spacing=spacing
    )


def pilih_setting_teks(box_width, box_height, text):
    """
    Dynamic settings to maximize space in large bubbles with short text, 
    while keeping small/dense bubbles safe~
    """
    text_bersih = str(text).replace(" ", "").replace("\n", "")
    jumlah_char = len(text_bersih)
    area = box_width * box_height

    balon_besar = box_width >= 150 and box_height >= 130 and area >= 30000
    teks_pendek = jumlah_char <= 55
    teks_sangat_pendek = jumlah_char <= 28

    if balon_besar and teks_sangat_pendek:
        return {
            "skala_w": 0.85,
            "skala_h": 0.78,
            "font_scale": 0.95,
            "spacing_ratio": 0.055,
            "max_font": 86,
            "min_font": 7,
        }

    if balon_besar and teks_pendek:
        return {
            "skala_w": 0.82,
            "skala_h": 0.78,
            "font_scale": 0.94,
            "spacing_ratio": 0.060,
            "max_font": 82,
            "min_font": 7,
        }

    return {
        "skala_w": 0.76,
        "skala_h": 0.76,
        "font_scale": 0.92,
        "spacing_ratio": 0.075,
        "max_font": 76,
        "min_font": 6,
    }


def tulis_teks_jepang_vertikal(draw, text, font_func, x1, y1, x2, y2, setting, background_patch=False):
    """
    Draws Japanese text vertically (Top-to-Bottom, Right-to-Left).
    """
    text = text.replace(" ", "").replace("\n", "")
    box_width = max(1, x2 - x1)
    box_height = max(1, y2 - y1)
    
    max_w = box_width * setting["skala_w"]
    max_h = box_height * setting["skala_h"]
    
    min_font_size = setting["min_font"]
    max_font_size = setting["max_font"]
    
    best_font_size = min_font_size
    best_columns = []
    
    for f_size in range(max_font_size, min_font_size - 1, -1):
        char_h = f_size
        char_w = f_size
        chars_per_col = max(1, int(max_h // char_h))
        
        columns = [text[i:i+chars_per_col] for i in range(0, len(text), chars_per_col)]
        total_w = len(columns) * char_w
        
        if total_w <= max_w:
            best_font_size = f_size
            best_columns = columns
            break

    # If it still doesn't fit, just use the minimum font size
    if not best_columns:
        chars_per_col = max(1, int(max_h // min_font_size))
        best_columns = [text[i:i+chars_per_col] for i in range(0, len(text), chars_per_col)]
            
    best_font_size = max(min_font_size, int(best_font_size * setting["font_scale"]))
    font = font_func(text, best_font_size, "japanese")
    
    actual_w = len(best_columns) * best_font_size
    actual_h = max(len(col) for col in best_columns) * best_font_size if best_columns else 0
    
    # Start at right-most column
    start_x = x1 + (box_width + actual_w) / 2 - best_font_size
    start_y = y1 + (box_height - actual_h) / 2
    
    stroke_w = max(1, best_font_size // 11)
    
    if background_patch:
        pad = max(6, best_font_size // 2)
        patch_box = [
            int(start_x - actual_w + best_font_size - pad),
            int(start_y - pad),
            int(start_x + best_font_size + pad),
            int(start_y + actual_h + pad)
        ]
        draw.rectangle(patch_box, fill=(255, 255, 255, 255))
        
    for col in best_columns:
        curr_y = start_y
        for char in col:
            # Basic vertical punctuation handling
            offset_x, offset_y = 0, 0
            if char in ['。', '、', '.']:
                offset_x, offset_y = best_font_size * 0.6, -best_font_size * 0.6
            elif char in ['「', '」', '（', '）', '(', ')']:
                # Simplistic rotation/shift for brackets - in a real app you'd rotate the glyph
                pass 
            elif char == 'ー':
                char = '︱'  # Hack/Trik untuk chouonpu vertikal
                
            char_x = start_x + offset_x
            char_y = curr_y + offset_y
            
            # Text stroke
            draw.text(
                (char_x, char_y),
                char,
                font=font,
                fill=(255, 255, 255, 255),
                stroke_width=stroke_w,
                stroke_fill=(255, 255, 255, 255)
            )
            # Text body
            draw.text(
                (char_x, char_y),
                char,
                font=font,
                fill=(0, 0, 0, 255)
            )
            
            # "ー" (chouonpu) needs to be drawn vertically (rotated)
            # PIL text drawing doesn't easily rotate single characters inline without creating a new image
            # A simple hack for vertical chouonpu is drawing a line or a pipe '|' if not supported natively.
            
            curr_y += best_font_size
        start_x -= best_font_size


def tulis_teks_di_balon(draw, text, x1, y1, x2, y2, background_patch=False, target_language=None):
    """
    Auto-fits translated text into speech bubbles.
    Wraps words neatly, allows hyphen splits, and maximizes font size.
    Automatically uses a Unicode fallback font for non-Latin scripts~ ♪
    """
    text = str(text).strip()

    box_width = max(1, x2 - x1)
    box_height = max(1, y2 - y1)
    setting = pilih_setting_teks(box_width, box_height, text)
    
    lang_key = target_language.lower() if target_language else ""
    if lang_key == "jepang":
        lang_key = "japanese"

    # Japanese vertical routing
    if lang_key == "japanese":
        tulis_teks_jepang_vertikal(draw, text, _get_font_for_text, x1, y1, x2, y2, setting, background_patch)
        return

    # Only uppercase for Latin scripts (Korean/CJK/Arabic don't have uppercase)
    if not _has_non_latin(text):
        text = text.upper()

    max_w = box_width * setting["skala_w"]
    max_h = box_height * setting["skala_h"]

    min_font_size = setting["min_font"]
    max_font_size = setting["max_font"]

    best_font_size = min_font_size
    best_wrap = text
    best_spacing = 1
    best_score = -1

    # Looking for the largest font size that fits~
    # Selecting the layout that fills the bubble most beautifully ♪
    for f_size in range(max_font_size, min_font_size - 1, -1):
        font = _get_font_for_text(text, f_size, target_language)

        spacing = max(1, int(f_size * setting["spacing_ratio"]))
        wrapped_text = bungkus_teks_per_kata(draw, text, font, max_w)

        bbox = hitung_bbox_multiline(draw, wrapped_text, font, spacing)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        if tw <= max_w and th <= max_h:
            isi_w = tw / max(1, max_w)
            isi_h = th / max(1, max_h)
            score = (f_size * 10) + (isi_w + isi_h)

            if score > best_score:
                best_score = score
                best_font_size = f_size
                best_wrap = wrapped_text
                best_spacing = spacing

            # Since we search largest to smallest, the first match is usually the best~
            break

    # Don't shrink font size too much for big bubbles with short text~
    best_font_size = max(min_font_size, int(best_font_size * setting["font_scale"]))

    font = _get_font_for_text(text, best_font_size, target_language)

    best_spacing = max(1, int(best_font_size * setting["spacing_ratio"]))

    # Re-wrapping with the final font size~
    best_wrap = bungkus_teks_per_kata(draw, text, font, max_w)

    bbox = hitung_bbox_multiline(draw, best_wrap, font, best_spacing)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    center_x = x1 + (box_width - text_width) / 2
    center_y = y1 + (box_height - text_height) / 2

    stroke_w = max(1, best_font_size // 11)

    if background_patch:
        pad = max(6, best_font_size // 2)

        patch_box = [
            int(center_x - pad),
            int(center_y - pad),
            int(center_x + text_width + pad),
            int(center_y + text_height + pad)
        ]

        try:
            draw.rounded_rectangle(
                patch_box,
                radius=max(4, best_font_size // 2),
                fill=(255, 255, 255)
            )
        except Exception:
            draw.rectangle(
                patch_box,
                fill=(255, 255, 255)
            )

    draw.multiline_text(
        (center_x, center_y),
        best_wrap,
        fill=(0, 0, 0),
        font=font,
        align="center",
        spacing=best_spacing,
        stroke_width=stroke_w,
        stroke_fill=(255, 255, 255)
    )


def _area_box(box):
    x1, y1, x2, y2 = box
    return max(0, x2 - x1) * max(0, y2 - y1)


def _irisan_box(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    return max(0, ix2 - ix1) * max(0, iy2 - iy1)


def _perlu_digabung(a, b):
    """
    Checks if two boxes are duplicates or belong to the same bubble. 
    Won't merge if they are just close by~
    """
    area_a = _area_box(a)
    area_b = _area_box(b)

    if area_a == 0 or area_b == 0:
        return False

    inter = _irisan_box(a, b)

    if inter == 0:
        return False

    iou = inter / float(area_a + area_b - inter)
    cover_kotak_kecil = inter / float(min(area_a, area_b))

    if iou >= 0.28:
        return True

    if cover_kotak_kecil >= 0.82:
        return True

    return False


def buang_kotak_raksasa_palsu(boxes):
    """
    Discards large bounding boxes that engulf smaller boxes, as they are usually 
    false positives (like YOLO detecting the whole panel instead of just bubbles)~ ♪
    """
    if not boxes: return []
    
    boxes_with_area = [(b, _area_box(b)) for b in boxes]
    boxes_with_area.sort(key=lambda x: x[1], reverse=True)
    
    keep = [True] * len(boxes_with_area)
    
    for i in range(len(boxes_with_area)):
        if not keep[i]: continue
        box_i, area_i = boxes_with_area[i]
        
        for j in range(i+1, len(boxes_with_area)):
            if not keep[j]: continue
            box_j, area_j = boxes_with_area[j]
            
            if area_i > 2.5 * area_j:
                inter = _irisan_box(box_i, box_j)
                # Jika kotak kecil berada >80% di dalam kotak besar
                if inter >= 0.8 * area_j:
                    keep[i] = False
                    break
                    
    return [boxes_with_area[i][0] for i in range(len(boxes_with_area)) if keep[i]]


def gabung_kotak_tumpang_tindih(boxes):
    """Merges duplicate YOLO boxes without fusing separate bubbles~ ♪"""
    if not boxes:
        return []

    boxes = [list(map(int, b)) for b in boxes]
    berubah = True

    while berubah:
        berubah = False
        hasil = []
        dipakai = [False] * len(boxes)

        for i in range(len(boxes)):
            if dipakai[i]:
                continue

            x1, y1, x2, y2 = boxes[i]

            for j in range(i + 1, len(boxes)):
                if dipakai[j]:
                    continue

                if _perlu_digabung([x1, y1, x2, y2], boxes[j]):
                    ox1, oy1, ox2, oy2 = boxes[j]

                    x1 = min(x1, ox1)
                    y1 = min(y1, oy1)
                    x2 = max(x2, ox2)
                    y2 = max(y2, oy2)

                    dipakai[j] = True
                    berubah = True

            hasil.append([x1, y1, x2, y2])
            dipakai[i] = True

        boxes = hasil

    return sorted(boxes, key=lambda b: (b[1], b[0]))


def buang_kotak_ngawur(boxes, lebar_img, tinggi_img):
    """
    Discards boxes that are too wide or flat. 
    These are usually false positives from SFX, panels, or lines~ ♪
    """
    hasil = []
    luas_gambar = max(1, lebar_img * tinggi_img)

    for box in boxes:
        x1, y1, x2, y2 = box

        w = max(1, x2 - x1)
        h = max(1, y2 - y1)

        rasio = w / float(h)
        luas_ratio = (w * h) / float(luas_gambar)

        terlalu_lebar = rasio >= 3.2 and w >= lebar_img * 0.35
        terlalu_gepeng_besar = w >= lebar_img * 0.50 and h <= tinggi_img * 0.16
        terlalu_besar_tipis = luas_ratio >= 0.035 and rasio >= 2.8

        if terlalu_lebar or terlalu_gepeng_besar or terlalu_besar_tipis:
            continue

        hasil.append(box)

    return hasil


def simpan_debug_crop_filter(image_name, crop, box, alasan):
    """Saves discarded crops so you can inspect them manually if you wish~ ♪"""
    if not config.SIMPAN_DEBUG_FILTER_SFX:
        return

    debug_dir = os.path.join(config.ROOT_DIR, "cypy_cache", "debug_filter_sfx")
    os.makedirs(debug_dir, exist_ok=True)

    safe_name = os.path.basename(image_name).replace(".", "_")
    x1, y1, x2, y2 = box

    filename = f"{safe_name}_{alasan}_{x1}_{y1}_{x2}_{y2}.png"
    path = os.path.join(debug_dir, filename)

    try:
        cv2.imwrite(path, crop)
    except Exception:
        pass


def buang_kotak_sfx_dan_gambar(img, boxes, image_name="image"):
    """
    A safe filter to discard boxes that are likely SFX or background art. 
    Conservative approach:
    - Small boxes are kept.
    - Dominant white boxes are kept.
    - Discards large boxes with dense edges and black lines~
    """
    if not config.FILTER_SFX_AKTIF:
        return boxes

    hasil = []

    tinggi_img, lebar_img = img.shape[:2]
    luas_img = max(1, tinggi_img * lebar_img)

    if config.FILTER_SFX_MODE == "longgar":
        black_thr = 0.20
        edge_thr = 0.14
        white_safe = 0.58
    elif config.FILTER_SFX_MODE == "ketat":
        black_thr = 0.13
        edge_thr = 0.09
        white_safe = 0.68
    else:
        black_thr = 0.16
        edge_thr = 0.11
        white_safe = 0.62

    for box in boxes:
        x1, y1, x2, y2 = map(int, box)

        w = max(1, x2 - x1)
        h = max(1, y2 - y1)
        luas_ratio = (w * h) / float(luas_img)
        rasio = w / float(h)

        crop = img[y1:y2, x1:x2]

        if crop.size == 0:
            continue

        # Main safeguard: keep small boxes safe, as tiny speech bubbles can be small~
        box_kecil = (
            w < lebar_img * 0.18
            and h < tinggi_img * 0.18
            and luas_ratio < 0.020
        )

        if box_kecil:
            hasil.append(box)
            continue

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        black_ratio = float(np.mean(gray < 80))
        white_ratio = float(np.mean(gray > 220))

        edges = cv2.Canny(gray, 80, 160)
        edge_ratio = float(np.mean(edges > 0))

        # If mostly white, it's likely a speech bubble! We'll keep it~
        if white_ratio >= white_safe:
            hasil.append(box)
            continue

        # SFX/background patterns usually have lots of black lines and dense edges~
        sfx_atau_gambar = (
            luas_ratio > 0.018
            and black_ratio > black_thr
            and edge_ratio > edge_thr
        )

        # Wide/flat boxes with dense edges are likely panel borders or SFX~
        gepeng_mencurigakan = (
            rasio > 2.2
            and w > lebar_img * 0.30
            and edge_ratio > max(0.07, edge_thr - 0.03)
            and white_ratio < white_safe
        )

        # Large non-white boxes with dense edges are usually drawings or characters~
        gambar_besar_mencurigakan = (
            luas_ratio > 0.045
            and white_ratio < 0.55
            and edge_ratio > 0.075
        )

        if sfx_atau_gambar or gepeng_mencurigakan or gambar_besar_mencurigakan:
            simpan_debug_crop_filter(
                image_name=image_name,
                crop=crop,
                box=box,
                alasan="sfx"
            )
            continue

        hasil.append(box)

    return hasil


def _overlap_1d(a1, a2, b1, b2):
    return max(0, min(a2, b2) - max(a1, b1))


def buat_crop_lega_tapi_tidak_nyamber(box, semua_box, lebar_img, tinggi_img, pad_x, pad_y):
    """
    Expands crop area slightly so it doesn't get clipped. 
    Limits crop at midpoint if neighbors are aligned~
    """
    x1, y1, x2, y2 = box

    crop_x1 = max(0, x1 - pad_x)
    crop_y1 = max(0, y1 - pad_y)
    crop_x2 = min(lebar_img, x2 + pad_x)
    crop_y2 = min(tinggi_img, y2 + pad_y)

    box_w = max(1, x2 - x1)
    box_h = max(1, y2 - y1)

    for other in semua_box:
        if other == box:
            continue

        ox1, oy1, ox2, oy2 = other

        other_w = max(1, ox2 - ox1)
        other_h = max(1, oy2 - oy1)

        overlap_x = _overlap_1d(x1, x2, ox1, ox2) / float(min(box_w, other_w))
        overlap_y = _overlap_1d(y1, y2, oy1, oy2) / float(min(box_h, other_h))

        if overlap_x >= config.OVERLAP_BATAS_CROP:
            if oy1 >= y2:
                batas = (y2 + oy1) // 2
                crop_y2 = min(crop_y2, max(y2, batas))

            elif oy2 <= y1:
                batas = (oy2 + y1) // 2
                crop_y1 = max(crop_y1, min(y1, batas))

        if overlap_y >= config.OVERLAP_BATAS_CROP:
            if ox1 >= x2:
                batas = (x2 + ox1) // 2
                crop_x2 = min(crop_x2, max(x2, batas))

            elif ox2 <= x1:
                batas = (ox2 + x1) // 2
                crop_x1 = max(crop_x1, min(x1, batas))

    return int(crop_x1), int(crop_y1), int(crop_x2), int(crop_y2)


def mask_luar_box_utama(potongan, crop_x1, crop_y1, x1, y1, x2, y2):
    """
    Masks the area outside the YOLO box with white. 
    Keeps external text from confusing Gemini~ ♪
    """
    if not config.MASK_AREA_LUAR_BOX:
        return potongan

    local_x1 = x1 - crop_x1
    local_y1 = y1 - crop_y1
    local_x2 = x2 - crop_x1
    local_y2 = y2 - crop_y1

    mask_x1 = max(0, local_x1 - config.MASK_MARGIN)
    mask_y1 = max(0, local_y1 - config.MASK_MARGIN)
    mask_x2 = min(potongan.shape[1], local_x2 + config.MASK_MARGIN)
    mask_y2 = min(potongan.shape[0], local_y2 + config.MASK_MARGIN)

    potongan_masked = 255 * np.ones_like(potongan)
    potongan_masked[mask_y1:mask_y2, mask_x1:mask_x2] = potongan[mask_y1:mask_y2, mask_x1:mask_x2]

    return potongan_masked


def create_shortcut_if_first_run():
    """
    Automatically creates a Windows desktop shortcut on the first run of the application.
    Does nothing on non-Windows platforms or in development mode.
    """
    import sys
    import os
    import subprocess

    if sys.platform != "win32":
        return

    if not getattr(sys, 'frozen', False):
        return

    base_path = os.path.dirname(sys.executable)
    cache_dir = os.path.join(base_path, "cypy_cache")
    os.makedirs(cache_dir, exist_ok=True)
    
    flag_file = os.path.join(cache_dir, ".shortcut_created")
    if os.path.exists(flag_file):
        return
        
    try:
        exe_path = sys.executable
        working_dir = base_path
        
        # PowerShell script to create shortcut pointing to the exe and setting its icon
        ps_cmd = (
            f"$WshShell = New-Object -ComObject WScript.Shell; "
            f"$Shortcut = $WshShell.CreateShortcut(([Environment]::GetFolderPath('Desktop') + '\\cypy.lnk')); "
            f"$Shortcut.TargetPath = '{exe_path}'; "
            f"$Shortcut.WorkingDirectory = '{working_dir}'; "
            f"$Shortcut.IconLocation = '{exe_path}'; "
            f"$Shortcut.Save()"
        )
        
        creation_flags = 0x08000000 # CREATE_NO_WINDOW
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            creationflags=creation_flags,
            check=True
        )
        
        with open(flag_file, "w") as f:
            f.write("created")
            
        print("[Utils] Desktop shortcut successfully created.")
    except Exception as e:
        print(f"[Utils] Failed to create desktop shortcut: {e}")
