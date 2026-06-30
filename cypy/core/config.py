import os
import sys
from dotenv import load_dotenv

# ✦ Path Helper - Let's find where everything is~ ✦
CORE_DIR = os.path.dirname(os.path.abspath(__file__))
# CORE_DIR is where our core essence lies
# ROOT_DIR is our magical home

if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
    ASSETS_DIR = os.path.join(getattr(sys, '_MEIPASS', ROOT_DIR), "assets")
else:
    ROOT_DIR = os.path.abspath(os.path.join(CORE_DIR, "..", ".."))
    ASSETS_DIR = os.path.join(ROOT_DIR, "assets")

load_dotenv(os.path.join(ROOT_DIR, ".env"))


# ==========================================
# ✦ LLM PROVIDER SETTINGS - Choose your translation engine~ ♪ ✦
# ==========================================
# Supported providers: gemini, openai, zen, openrouter, custom
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()

# Google Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_GEMINI = os.getenv("MODEL_GEMINI", "gemini-3.1-flash-lite")

# OpenRouter (https://openrouter.ai)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
MODEL_OPENROUTER = os.getenv("MODEL_OPENROUTER", "qwen/qwen2.5-vl-72b-instruct:free")

# OpenAI (https://platform.openai.com)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL_OPENAI = os.getenv("MODEL_OPENAI", "gpt-5.4-mini")

# Zen (https://opencode.ai) — no API key required
ZEN_API_KEY = os.getenv("ZEN_API_KEY", "")
MODEL_ZEN = os.getenv("MODEL_ZEN", "minimax-m3-free")

# Custom OpenAI-compatible provider
CUSTOM_API_KEY = os.getenv("CUSTOM_API_KEY", "")
CUSTOM_BASE_URL = os.getenv("CUSTOM_BASE_URL", "")
MODEL_CUSTOM = os.getenv("MODEL_CUSTOM", "gpt-5.4-mini")


# ✦ Assets Path - YOLO model and font files go here~ ✦
MODEL_YOLO = os.path.join(ASSETS_DIR, "eyecyre.pt")
FONT_MANGA = os.path.join(ASSETS_DIR, "Komika Axis.ttf")


# ==========================================
# ✦ LANGUAGE SETTINGS - Supported target languages~ ♪ ✦
# ==========================================
LANG_CODES = {
    "english": "en",
    "indonesian": "id",
    "spanish": "es",
    "portuguese": "pt",
    "javanese": "jv",
    "japanese": "jp",
    "jepang": "jp",
    "korean": "kr",
    "korea": "kr",
    "chinese": "cn",
    "chinese (simplified)": "cn",
    "chinese (traditional)": "tw",
    "mandarin": "cn",
    "thai": "th",
    "vietnamese": "vi",
    "russian": "ru",
    "arabic": "ar",
    "hindi": "hi",
    "malay": "ms",
    "tagalog": "tl"
}

# Supported image file extensions
SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


# ==========================================
# ✦ MOSAIC & CROP SETTINGS - Arranging page panels beautifully~ ✦
# ==========================================
MAX_TINGGI_MOSAIK = 6000

PAD_X_RATIO = 0.40
PAD_Y_RATIO = 0.25
MIN_PAD = 35

SKALA_POTONGAN_MOSAIK = 2.0

OVERLAP_BATAS_CROP = 0.35

MASK_AREA_LUAR_BOX = True
MASK_MARGIN = 18

MARGIN_KIRI_NOMOR = 55
MARGIN_KANAN = 10
JARAK_ANTAR_POTONGAN = 10
LEBAR_MOSAIK_MIN = 360


# ==========================================
# ✦ SFX & IMAGE FILTER - Sweeping away unwanted noises~ ✦
# ==========================================
# If True, boxes resembling SFX/background drawings will be removed~
# Set to False if some speech bubbles get mistakenly filtered out ♪
FILTER_SFX_AKTIF = True

# Modes:
# "longgar"   = safest mode, very low chance of filtering actual bubbles
# "seimbang"  = highly recommended balance ♪
# "ketat"     = aggressive filtering, might remove some actual bubbles too
FILTER_SFX_MODE = "seimbang"

# If True, filtered out SFX boxes will be saved for your manual inspection~
SIMPAN_DEBUG_FILTER_SFX = True


# ==========================================
# ✦ FLAT BOX PATCH SETTINGS - Keeping our beautiful drawings safe from being covered~ ✦
# ==========================================
PAKAI_PATCH_UNTUK_BOX_GEPENG = True

RASIO_BOX_GEPENG = 2.4
LEBAR_BOX_GEPENG_RATIO = 0.45
TINGGI_BOX_GEPENG_RATIO = 0.22


# ==========================================
# ✦ MANUAL TRANSLATION OVERRIDE - For correcting specific bubble IDs manually ♪ ✦
# ==========================================
MANUAL_TRANSLATION_OVERRIDE = {}


# ==========================================
# ✦ PROVIDER HELPERS - Utility functions for provider management~ ♪ ✦
# ==========================================
def get_provider_config(provider_name=None):
    """
    Returns (api_key, model_name) for the given provider.
    Defaults to the currently configured LLM_PROVIDER.
    """
    provider = (provider_name or LLM_PROVIDER).lower()

    if provider == "gemini":
        return GEMINI_API_KEY, MODEL_GEMINI
    elif provider == "openrouter":
        return OPENROUTER_API_KEY, MODEL_OPENROUTER
    elif provider == "openai":
        return OPENAI_API_KEY, MODEL_OPENAI
    elif provider == "zen":
        return ZEN_API_KEY, MODEL_ZEN
    elif provider == "custom":
        return CUSTOM_API_KEY, MODEL_CUSTOM
    else:
        return "", ""
