"""
cypy/core/config.py
✦ Centralized Configuration Management ✦

All application settings, provider definitions, and tweakable parameters
are managed through a single `ConfigManager` instance. Provider metadata
is defined once here and consumed by both CLI and GUI — adding a new
provider only requires adding one entry to PROVIDER_REGISTRY.
"""
import json
import os
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv

from cypy.core.types import APIKey


# ==========================================
# ✦ PATH RESOLUTION ✦
# ==========================================
CORE_DIR = os.path.dirname(os.path.abspath(__file__))

if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
    ASSETS_DIR = os.path.join(getattr(sys, '_MEIPASS', ROOT_DIR), "assets")
else:
    ROOT_DIR = os.path.abspath(os.path.join(CORE_DIR, "..", ".."))
    ASSETS_DIR = os.path.join(ROOT_DIR, "assets")

load_dotenv(os.path.join(ROOT_DIR, ".env"))


# ==========================================
# ✦ PROVIDER REGISTRY — Single Source of Truth ✦
# ==========================================
@dataclass(frozen=True)
class ProviderMeta:
    """Immutable metadata descriptor for a single LLM provider."""
    key: str                # Internal identifier (e.g. "gemini")
    display_name: str       # Human-readable name (e.g. "Google Gemini")
    env_key: str            # Environment variable for API key
    model_env_key: str      # Environment variable for model name
    default_model: str      # Default model name
    url: str = ""           # URL to get API key
    desc: str = ""          # Short description
    requires_key: bool = True   # Whether API key is required


PROVIDER_REGISTRY: Dict[str, ProviderMeta] = {}

def _register_providers():
    """Register all built-in providers."""
    defs = [
        ProviderMeta(
            key="gemini", display_name="Google Gemini",
            env_key="GEMINI_API_KEY", model_env_key="MODEL_GEMINI",
            default_model="gemini-3.1-flash-lite",
            url="https://aistudio.google.com/",
            desc="Free tier available",
        ),
        ProviderMeta(
            key="openai", display_name="OpenAI",
            env_key="OPENAI_API_KEY", model_env_key="MODEL_OPENAI",
            default_model="gpt-5.4-mini",
            url="https://platform.openai.com/api-keys",
            desc="GPT-5.4, GPT-5.4-mini",
        ),
        ProviderMeta(
            key="zen", display_name="Zen (opencode.ai)",
            env_key="ZEN_API_KEY", model_env_key="MODEL_ZEN",
            default_model="minimax-m3-free",
            url="https://opencode.ai/auth",
            desc="Free models, optional API key for more quota",
            requires_key=False,
        ),
        ProviderMeta(
            key="opencodego", display_name="OpenCode Go",
            env_key="OPENCODEGO_API_KEY", model_env_key="MODEL_OPENCODEGO",
            default_model="mimo-v2.5",
            url="https://opencode.ai/auth",
            desc="API key required, high-performance models",
        ),
        ProviderMeta(
            key="openrouter", display_name="OpenRouter",
            env_key="OPENROUTER_API_KEY", model_env_key="MODEL_OPENROUTER",
            default_model="qwen/qwen2.5-vl-72b-instruct:free",
            url="https://openrouter.ai/keys",
            desc="Access 100+ models (Claude, Llama, Mistral, etc.)",
        ),
        ProviderMeta(
            key="custom", display_name="Custom",
            env_key="CUSTOM_API_KEY", model_env_key="MODEL_CUSTOM",
            default_model="gpt-5.4-mini",
            url="",
            desc="OpenAI-compatible API, custom base URL",
            requires_key=False,
        ),
    ]
    for p in defs:
        PROVIDER_REGISTRY[p.key] = p

_register_providers()


# ==========================================
# ✦ LANGUAGE DEFINITIONS ✦
# ==========================================
LANG_CODES = {
    "english": "en", "indonesian": "id", "spanish": "es",
    "portuguese": "pt", "javanese": "jv", "japanese": "jp",
    "jepang": "jp", "korean": "kr", "korea": "kr",
    "chinese": "cn", "chinese (simplified)": "cn",
    "chinese (traditional)": "tw", "mandarin": "cn",
    "thai": "th", "vietnamese": "vi", "russian": "ru",
    "arabic": "ar", "hindi": "hi", "malay": "ms", "tagalog": "tl",
}

LANGUAGE_CHOICES = [
    "English", "Indonesian", "Japanese", "Mandarin",
    "Spanish", "Portuguese", "Javanese", "Korean", "Russian", "Thai",
]


# ==========================================
# ✦ STATIC CONSTANTS ✦
# ==========================================
MODEL_YOLO = os.path.join(ASSETS_DIR, "eyecypy.onnx")
FONT_MANGA = os.path.join(ASSETS_DIR, "Komika Axis.ttf")
REQUEST_TIMEOUT = 60 * 2  # 120s
SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


# ==========================================
# ✦ TWEAKABLE PARAMETERS DEFINITION ✦
# ==========================================
TWEAKABLE_PARAMS = {
    "max_bubbles": {
        "attr": "max_bubbles_per_request", "type": "int", "default": 20,
        "min": 1, "max": 50,
        "desc": "Maximum speech bubbles per AI mosaic request (prevents API limits/skipped IDs).",
        "effect": "If a page contains > 20 bubbles, the mosaic image is automatically chunked per 20 bubbles."
    },
    "request_delay": {
        "attr": "min_request_delay", "type": "float", "default": 2.0,
        "min": 0.0, "max": 10.0,
        "desc": "Minimum delay (seconds) between API requests to provider.",
        "effect": "Prevents HTTP 429 Too Many Requests errors from AI providers."
    },
    "sfx_mode": {
        "attr": "filter_sfx_mode", "type": "str", "default": "balanced",
        "options": ["balanced", "relaxed", "strict"],
        "desc": "Aggressiveness level for removing SFX / background noise text.",
        "effect": "'strict' = removes more boxes (may affect real text), 'relaxed' = safer but preserves noise."
    },
    "pad_x": {
        "attr": "pad_x_ratio", "type": "float", "default": 0.40,
        "min": 0.0, "max": 1.5,
        "desc": "Horizontal padding ratio for bubble crops sent to AI.",
        "effect": "LARGER = prevents text clipping for AI OCR, but may overlap adjacent text."
    },
    "pad_y": {
        "attr": "pad_y_ratio", "type": "float", "default": 0.25,
        "min": 0.0, "max": 1.5,
        "desc": "Vertical padding ratio for bubble crops sent to AI.",
        "effect": "LARGER = prevents text clipping for AI OCR, but may overlap vertical text."
    },
    "skala_potongan": {
        "attr": "skala_potongan_mosaik", "type": "float", "default": 2.0,
        "min": 1.0, "max": 5.0,
        "desc": "Image magnification factor before sending to AI.",
        "effect": "LARGER = small text is clearer to AI, but slightly slower upload/processing."
    },
    "patch_gepeng": {
        "attr": "pakai_patch_untuk_box_gepeng", "type": "bool", "default": True,
        "desc": "Cover extremely flat/wide text boxes with a thick white patch.",
        "effect": "Disable (False) if comic panel borders are accidentally covered."
    },
    "min_pad": {
        "attr": "min_pad", "type": "int", "default": 35,
        "min": 0, "max": 150,
        "desc": "Minimum padding (in pixels) for crops sent to AI.",
        "effect": "LARGER = prevents crop bounds from being too tight on small text."
    },
    "mask_margin": {
        "attr": "mask_margin_ratio", "type": "float", "default": 0.12,
        "min": 0.0, "max": 0.45,
        "desc": "Margin ratio for white background masking inside speech bubbles.",
        "effect": "LARGER = tighter mask inside bubble border."
    },
}


# ==========================================
# ✦ APP CONFIG DATACLASS ✦
# ==========================================
@dataclass
class AppConfig:
    """Holds all mutable application state. Single source of truth."""

    llm_provider: str = "gemini"
    target_language: str = ""

    gemini_api_key: APIKey = ""
    openai_api_key: APIKey = ""
    openrouter_api_key: APIKey = ""
    zen_api_key: APIKey = ""
    opencodego_api_key: APIKey = ""
    custom_api_key: APIKey = ""

    model_gemini: str = "gemini-3.1-flash-lite"
    model_openai: str = "gpt-5.4-mini"
    model_openrouter: str = "qwen/qwen2.5-vl-72b-instruct:free"
    model_zen: str = "minimax-m3-free"
    model_opencodego: str = "mimo-v2.5"
    model_custom: str = "gpt-5.4-mini"

    custom_base_url: str = ""

    # --- Batching & Rate Limiting ---
    max_bubbles_per_request: int = 20
    min_request_delay: float = 2.0

    max_tinggi_mosaik: int = 6000
    pad_x_ratio: float = 0.40
    pad_y_ratio: float = 0.25
    min_pad: int = 35
    skala_potongan_mosaik: float = 2.0
    overlap_batas_crop: float = 0.35

    mask_area_luar_box: bool = True
    mask_margin: int = 18
    mask_margin_ratio: float = 0.12

    margin_kiri_nomor: int = 55
    margin_kanan: int = 10
    jarak_antar_potongan: int = 10
    lebar_mosaik_min: int = 360

    filter_sfx_aktif: bool = True
    filter_sfx_mode: str = "balanced"
    simpan_debug_filter_sfx: bool = True

    pakai_patch_untuk_box_gepeng: bool = True
    rasio_box_gepeng: float = 2.4
    lebar_box_gepeng_ratio: float = 0.45
    tinggi_box_gepeng_ratio: float = 0.22

    manual_translation_override: Dict[str, str] = field(default_factory=dict)
    cancel_translation: bool = False
    last_opened_dir: str = ""

    def get_provider_config(self, provider_name: str = "") -> Tuple[APIKey, str]:
        provider = (provider_name or self.llm_provider).lower()
        meta = PROVIDER_REGISTRY.get(provider)
        if meta is None:
            return "", ""
        key_attr = meta.env_key.lower()
        model_attr = meta.model_env_key.lower()
        api_key = getattr(self, key_attr, "")
        model_name = getattr(self, model_attr, meta.default_model)
        return api_key, model_name

    def set_provider_api_key(self, provider_name: str, value: str):
        meta = PROVIDER_REGISTRY.get(provider_name.lower())
        if meta:
            setattr(self, meta.env_key.lower(), value)

    def set_provider_model(self, provider_name: str, value: str):
        meta = PROVIDER_REGISTRY.get(provider_name.lower())
        if meta:
            setattr(self, meta.model_env_key.lower(), value)


_SETTINGS_FIELDS = [
    "llm_provider", "target_language",
    "gemini_api_key", "model_gemini",
    "openai_api_key", "model_openai",
    "openrouter_api_key", "model_openrouter",
    "zen_api_key", "model_zen",
    "opencodego_api_key", "model_opencodego",
    "custom_api_key", "custom_base_url", "model_custom",
    "min_request_delay", "max_bubbles_per_request", "last_opened_dir",
]


class ConfigManager:
    """Thread-safe centralized configuration manager."""

    def __init__(self):
        self._lock = threading.Lock()
        self._config = AppConfig()
        self._data_dir: str = ""
        self._settings_file: str = ""

        self._resolve_data_dir()
        self._load_from_env()
        self._load_settings()

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def data_dir(self) -> str:
        return self._data_dir

    @property
    def settings_file(self) -> str:
        return self._settings_file

    def _resolve_data_dir(self):
        local_data_dir = os.path.join(ROOT_DIR, "data")
        local_settings_file = os.path.join(local_data_dir, "settings.json")

        appdata_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "cypy"
        )
        appdata_settings_file = os.path.join(appdata_dir, "settings.json")

        in_program_files = "program files" in ROOT_DIR.lower()

        if os.path.exists(appdata_settings_file) or in_program_files:
            self._data_dir = appdata_dir
            self._settings_file = appdata_settings_file
        else:
            is_writable = True
            try:
                os.makedirs(local_data_dir, exist_ok=True)
                test_file = os.path.join(local_data_dir, ".write_test")
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
            except Exception:
                is_writable = False

            if is_writable:
                self._data_dir = local_data_dir
                self._settings_file = local_settings_file
            else:
                self._data_dir = appdata_dir
                self._settings_file = appdata_settings_file

        os.makedirs(self._data_dir, exist_ok=True)

    def _load_from_env(self):
        c = self._config
        c.llm_provider = os.getenv("LLM_PROVIDER", "gemini").lower()
        c.target_language = os.getenv("TARGET_LANGUAGE", "")

        for meta in PROVIDER_REGISTRY.values():
            env_val = os.getenv(meta.env_key, "")
            if env_val:
                setattr(c, meta.env_key.lower(), env_val)
            model_val = os.getenv(meta.model_env_key, "")
            if model_val:
                setattr(c, meta.model_env_key.lower(), model_val)

        c.custom_base_url = os.getenv("CUSTOM_BASE_URL", "")

    def _load_settings(self):
        with self._lock:
            if not os.path.exists(self._settings_file):
                return
            try:
                with open(self._settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                c = self._config
                for key in _SETTINGS_FIELDS:
                    if key in data:
                        setattr(c, key, data[key])

                for meta in PROVIDER_REGISTRY.values():
                    val = getattr(c, meta.env_key.lower(), "")
                    if val:
                        os.environ[meta.env_key] = val
                if c.custom_base_url:
                    os.environ["CUSTOM_BASE_URL"] = c.custom_base_url

            except Exception as e:
                print(f"[!] Error loading settings: {e}")

    def save_settings(self):
        with self._lock:
            data = {}
            c = self._config
            for key in _SETTINGS_FIELDS:
                data[key] = getattr(c, key, "")
            try:
                with open(self._settings_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
            except Exception as e:
                print(f"[!] Error saving settings: {e}")

    def load_local_profile(self) -> bool:
        profile_path = os.path.join(os.getcwd(), "cypy_profile.json")
        if not os.path.exists(profile_path):
            return False
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            c = self._config
            for key, val in data.items():
                if key in TWEAKABLE_PARAMS:
                    attr = TWEAKABLE_PARAMS[key]["attr"]
                    setattr(c, attr, val)
            return True
        except Exception as e:
            print(f"[!] Error loading local profile: {e}")
            return False

    def save_local_profile(self) -> bool:
        profile_path = os.path.join(os.getcwd(), "cypy_profile.json")
        data = {}
        c = self._config
        for key, meta in TWEAKABLE_PARAMS.items():
            data[key] = getattr(c, meta["attr"], meta["default"])
        try:
            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            print(f"[!] Error saving local profile: {e}")
            return False

    @staticmethod
    def save_to_env(env_path: str, key: str, value: str):
        existing_lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                existing_lines = f.readlines()

        key_found = False
        new_lines = []
        for line in existing_lines:
            if line.strip().startswith(f"{key}="):
                new_lines.append(f"{key}={value}\n")
                key_found = True
            else:
                new_lines.append(line)
        if not key_found:
            new_lines.append(f"{key}={value}\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    @staticmethod
    def env_has_key(env_path: str, key: str) -> bool:
        if not os.path.exists(env_path):
            return False
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith(f"{key}="):
                    return True
        return False


config_manager = ConfigManager()


class _ConfigProxy:
    """
    A module-level proxy that redirects attribute access to the AppConfig instance.
    Provides backwards compatibility with the old `config.ATTR_NAME` pattern.
    """

    _MODULE_ATTRS = (
        "ROOT_DIR", "ASSETS_DIR", "CORE_DIR", "MODEL_YOLO", "FONT_MANGA",
        "REQUEST_TIMEOUT", "SUPPORTED_IMAGE_EXTENSIONS", "LANG_CODES",
        "LANGUAGE_CHOICES", "PROVIDER_REGISTRY", "TWEAKABLE_PARAMS",
    )

    ROOT_DIR = ROOT_DIR
    ASSETS_DIR = ASSETS_DIR
    CORE_DIR = CORE_DIR
    MODEL_YOLO = MODEL_YOLO
    FONT_MANGA = FONT_MANGA
    REQUEST_TIMEOUT = REQUEST_TIMEOUT
    SUPPORTED_IMAGE_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS
    LANG_CODES = LANG_CODES
    LANGUAGE_CHOICES = LANGUAGE_CHOICES
    PROVIDER_REGISTRY = PROVIDER_REGISTRY
    TWEAKABLE_PARAMS = TWEAKABLE_PARAMS
    config_manager = config_manager

    _UPPER_TO_LOWER = {
        "MAX_BUBBLES_PER_REQUEST": "max_bubbles_per_request",
        "MIN_REQUEST_DELAY": "min_request_delay",
        "LLM_PROVIDER": "llm_provider",
        "TARGET_LANGUAGE": "target_language",
        "GEMINI_API_KEY": "gemini_api_key",
        "MODEL_GEMINI": "model_gemini",
        "OPENAI_API_KEY": "openai_api_key",
        "MODEL_OPENAI": "model_openai",
        "OPENROUTER_API_KEY": "openrouter_api_key",
        "MODEL_OPENROUTER": "model_openrouter",
        "ZEN_API_KEY": "zen_api_key",
        "MODEL_ZEN": "model_zen",
        "OPENCODEGO_API_KEY": "opencodego_api_key",
        "MODEL_OPENCODEGO": "model_opencodego",
        "CUSTOM_API_KEY": "custom_api_key",
        "CUSTOM_BASE_URL": "custom_base_url",
        "MODEL_CUSTOM": "model_custom",
        "MAX_TINGGI_MOSAIK": "max_tinggi_mosaik",
        "PAD_X_RATIO": "pad_x_ratio",
        "PAD_Y_RATIO": "pad_y_ratio",
        "MIN_PAD": "min_pad",
        "SKALA_POTONGAN_MOSAIK": "skala_potongan_mosaik",
        "OVERLAP_BATAS_CROP": "overlap_batas_crop",
        "MASK_AREA_LUAR_BOX": "mask_area_luar_box",
        "MASK_MARGIN": "mask_margin",
        "MASK_MARGIN_RATIO": "mask_margin_ratio",
        "MARGIN_KIRI_NOMOR": "margin_kiri_nomor",
        "MARGIN_KANAN": "margin_kanan",
        "JARAK_ANTAR_POTONGAN": "jarak_antar_potongan",
        "LEBAR_MOSAIK_MIN": "lebar_mosaik_min",
        "FILTER_SFX_AKTIF": "filter_sfx_aktif",
        "FILTER_SFX_MODE": "filter_sfx_mode",
        "SIMPAN_DEBUG_FILTER_SFX": "simpan_debug_filter_sfx",
        "PAKAI_PATCH_UNTUK_BOX_GEPENG": "pakai_patch_untuk_box_gepeng",
        "RASIO_BOX_GEPENG": "rasio_box_gepeng",
        "LEBAR_BOX_GEPENG_RATIO": "lebar_box_gepeng_ratio",
        "TINGGI_BOX_GEPENG_RATIO": "tinggi_box_gepeng_ratio",
        "MANUAL_TRANSLATION_OVERRIDE": "manual_translation_override",
        "CANCEL_TRANSLATION": "cancel_translation",
        "DATA_DIR": None,
        "SETTINGS_FILE": None,
    }

    def __getattr__(self, name: str) -> Any:
        if name in self._UPPER_TO_LOWER:
            lower = self._UPPER_TO_LOWER[name]
            if lower is None:
                if name == "DATA_DIR":
                    return config_manager.data_dir
                if name == "SETTINGS_FILE":
                    return config_manager.settings_file
            return getattr(config_manager.config, lower)

        try:
            return getattr(config_manager.config, name)
        except AttributeError:
            pass

        raise AttributeError(f"module 'cypy.core.config' has no attribute {name!r}")

    def __setattr__(self, name: str, value: Any):
        if name.startswith("_") or name == "config_manager" or name in self._MODULE_ATTRS:
            super().__setattr__(name, value)
            return
        lower = self._UPPER_TO_LOWER.get(name)
        if lower:
            setattr(config_manager.config, lower, value)
            return
        if hasattr(config_manager.config, name):
            setattr(config_manager.config, name, value)
            return
        super().__setattr__(name, value)

    def get_provider_config(self, provider_name: str = ""):
        return config_manager.config.get_provider_config(provider_name)

    def save_settings(self):
        return config_manager.save_settings()

    def load_settings(self):
        return config_manager._load_settings()

    def save_local_profile(self):
        return config_manager.save_local_profile()

    def load_local_profile(self):
        return config_manager.load_local_profile()


_proxy = _ConfigProxy()
_proxy.__name__ = __name__
_proxy.__package__ = __package__
_proxy.__file__ = __file__
_proxy.__spec__ = globals().get("__spec__")
_proxy.__loader__ = globals().get("__loader__")
_proxy.__path__ = globals().get("__path__", [])
sys.modules[__name__] = _proxy
