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

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_GEMINI = "gemini-3.1-flash-lite-preview"

# ✦ Assets Path - YOLO model and font files go here~ ✦
MODEL_YOLO = os.path.join(ASSETS_DIR, "eyecyre.pt")
FONT_MANGA = os.path.join(ASSETS_DIR, "Komika Axis.ttf")

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
