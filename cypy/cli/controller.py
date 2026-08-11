"""
cypy/cli/controller.py
✦ Interactive CLI Controller ✦

Encapsulates all CLI-mode interactive logic: provider setup, language
selection, tweak menu, and the main input loop. Delegates translation
work to the core pipeline (translator.py).
"""
import os
import sys
import time
import traceback

import cypy.core.config as config
from cypy.core.config import config_manager, PROVIDER_REGISTRY, LANGUAGE_CHOICES, ROOT_DIR
from cypy.core.yolo_onnx import YOLOONNX as YOLO
from cypy.core.providers import create_provider
from cypy.core.translator import process_single_image, process_pdf, process_folder, process_archive
from cypy.core.services.platform_utils import create_shortcut_if_first_run
from cypy.core.version import APP_VER
from cypy.cli import ui


# ==========================================
# ✦ LANGUAGE SELECTION ✦
# ==========================================

def pilih_bahasa():
    """Interactive language selection menu."""
    options = [f"[{i+1}] {lang}" for i, lang in enumerate(LANGUAGE_CHOICES)]
    options.append(f"[{len(LANGUAGE_CHOICES)+1}] Custom (type your own)")
    ui.print_box("Target Language / Bahasa Target:", options, col_width=28)

    max_choice = len(LANGUAGE_CHOICES) + 1
    lang_choice = input(f"Select choice / Pilih (1-{max_choice}) [Default: 2]: ").strip()

    try:
        idx = int(lang_choice) - 1
        if 0 <= idx < len(LANGUAGE_CHOICES):
            target_language = LANGUAGE_CHOICES[idx]
        elif idx == len(LANGUAGE_CHOICES):
            custom = input("Type your target language (e.g. Korean, Thai, Arabic): ").strip()
            target_language = custom.title() if custom else "Indonesian"
        else:
            target_language = "Indonesian"
    except ValueError:
        target_language = "Indonesian"

    print(f"\n[+] Target language set to: {target_language}")
    return target_language


# ==========================================
# ✦ PROVIDER SELECTION ✦
# ==========================================

def pilih_provider():
    """Interactive provider selection menu."""
    provider_keys = list(PROVIDER_REGISTRY.keys())
    options = [f"[{i+1}] {PROVIDER_REGISTRY[k].display_name}" for i, k in enumerate(provider_keys)]
    ui.print_box("API Provider Selection:", options, col_width=28)

    choice = input(f"Select provider (1-{len(provider_keys)}) [Default: 1]: ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(provider_keys):
            return provider_keys[idx]
    except ValueError:
        pass
    return "gemini"


# ==========================================
# ✦ PROVIDER SETUP ✦
# ==========================================

def _commit_key(meta, api_key, env_path, provider_name):
    """Persist an API key to .env and config, also recording LLM_PROVIDER + model."""
    try:
        config_manager.save_to_env(env_path, meta.env_key, api_key)
        if not config_manager.env_has_key(env_path, "LLM_PROVIDER"):
            config_manager.save_to_env(env_path, "LLM_PROVIDER", provider_name)
        if not config_manager.env_has_key(env_path, meta.model_env_key):
            config_manager.save_to_env(env_path, meta.model_env_key, meta.default_model)
        config_manager.config.set_provider_api_key(provider_name, api_key)
        os.environ[meta.env_key] = api_key
        print(f"[+] API Key saved to: {env_path} (✿◠‿◠)")
    except Exception as e:
        print(f"[!] Warning: Failed to save API Key to .env: {e}")
    return api_key


def _prompt_and_save_key(meta, api_key, env_path, provider_name, skip_prompt=False):
    """Ensure an API key is available, prompting (and persisting) only if missing."""
    if api_key:
        return api_key
    if skip_prompt:
        print("[+] Proceeding without API key~ ♪")
        return api_key
    print(f"\n[!] {meta.display_name} API Key is missing!")
    if meta.url:
        print(f"Get your API key from: {meta.url}")
    api_key = input(f"Please paste your {meta.display_name} API Key here: ").strip()
    while not api_key:
        api_key = input("API Key cannot be empty. Please paste your API Key: ").strip()
    return _commit_key(meta, api_key, env_path, provider_name)


def setup_provider(provider_name=None):
    """Sets up the LLM provider, requesting API key if missing~ ♪"""
    cfg = config_manager.config

    if provider_name is None:
        provider_name = cfg.llm_provider

    api_key, model_name = cfg.get_provider_config(provider_name)
    meta = PROVIDER_REGISTRY.get(provider_name, PROVIDER_REGISTRY["gemini"])
    env_path = os.path.join(ROOT_DIR, ".env")

    if not meta.requires_key:
        # Key is optional — prompt only if not already set
        if not api_key:
            print(f"\n[i] {meta.display_name} works without an API key~ ♪")
            if meta.url:
                print(f"    Optional: get a key at {meta.url} for more quota.")
            entered = input(f"Paste your {meta.display_name} API Key (or press Enter to skip): ").strip()
            if entered:
                api_key = _commit_key(meta, entered, env_path, provider_name)
            else:
                print("[+] Proceeding without API key~ ♪")
    elif provider_name == "custom":
        # Custom provider: base URL is required, API key is optional
        base_url = cfg.custom_base_url
        if not base_url:
            print(f"\n[i] Enter the base URL for your OpenAI-compatible API.")
            print(f"    Example: https://api.example.com/v1")
            entered = input("Base URL: ").strip()
            while not entered:
                entered = input("Base URL cannot be empty: ").strip()
            base_url = entered
            try:
                config_manager.save_to_env(env_path, "CUSTOM_BASE_URL", base_url)
                cfg.custom_base_url = base_url
                os.environ["CUSTOM_BASE_URL"] = base_url
                print(f"[+] Base URL saved to: {env_path}")
            except Exception as e:
                print(f"[!] Warning: Failed to save Base URL to .env: {e}")

        api_key = _prompt_and_save_key(meta, api_key, env_path, provider_name, skip_prompt=True)
    else:
        api_key = _prompt_and_save_key(meta, api_key, env_path, provider_name)

    extra = {}
    if provider_name == "custom":
        extra["base_url"] = cfg.custom_base_url

    config_manager.save_settings()

    provider = create_provider(provider_name, api_key=api_key, model_name=model_name, **extra)
    return provider


# ==========================================
# ✦ TWEAK MENU ✦
# ==========================================

def menu_tweak():
    """Interactive parameter tweak menu."""
    cfg = config_manager.config

    print("\n" + "=" * 60)
    print("TWEAK MENU - Adjust Settings on the fly~ ♪")
    print("=" * 60 + "\n")

    for key, meta_info in config.TWEAKABLE_PARAMS.items():
        curr_val = getattr(cfg, meta_info["attr"], meta_info["default"])
        print(f"  [{key}]")
        print(f"    Current : {curr_val} (Default: {meta_info['default']})")

        if "min" in meta_info and "max" in meta_info:
            print(f"    Range   : {meta_info['min']} - {meta_info['max']}")
        elif "options" in meta_info:
            opts = ", ".join(meta_info['options'])
            print(f"    Options : {opts}")

        print(f"    Info    : {meta_info['desc']}")
        if "effect" in meta_info:
            print(f"    Efek    : {meta_info['effect']}")
        print("")

    print("=" * 60)
    print("  Type 'set <param> <value>' to change (e.g. set pad_x 0.5)")
    print("  Type 'back' or 'done' to return to main menu.")
    print("=" * 60)

    while True:
        cmd = input("tweak> ").strip().lower()
        if cmd in ("back", "done", "exit", "stop", "quit"):
            break

        if cmd.startswith("set "):
            parts = cmd.split(" ", 2)
            if len(parts) < 3:
                print("  [!] Format salah. Contoh: set pad_x 0.5")
                continue

            _, param, val_str = parts
            if param not in config.TWEAKABLE_PARAMS:
                print(f"  [!] Parameter '{param}' tidak ditemukan.")
                continue

            meta_info = config.TWEAKABLE_PARAMS[param]
            val = None
            try:
                if meta_info["type"] == "int":
                    val = int(val_str)
                elif meta_info["type"] == "float":
                    val = float(val_str)
                elif meta_info["type"] == "bool":
                    val = val_str.lower() in ("true", "1", "yes", "y", "on")
                else:
                    val = val_str

                if "options" in meta_info and val not in meta_info["options"]:
                    opts = ", ".join(meta_info['options'])
                    print(f"  [!] Nilai harus salah satu dari: {opts}")
                    continue
                if "min" in meta_info and val < meta_info["min"]:
                    print(f"  [!] Nilai minimal adalah {meta_info['min']}")
                    continue
                if "max" in meta_info and val > meta_info["max"]:
                    print(f"  [!] Nilai maksimal adalah {meta_info['max']}")
                    continue

                setattr(cfg, meta_info["attr"], val)
                print(f"  [+] {param} diubah menjadi {val}")

                if config_manager.save_local_profile():
                    print("  [+] Profil tersimpan ke cypy_profile.json")

            except ValueError:
                print(f"  [!] Nilai harus berupa tipe {meta_info['type']}")


# ==========================================
# ✦ MAIN CLI LOOP ✦
# ==========================================

def run_cli():
    """Main interactive CLI entry point."""
    cfg = config_manager.config

    # Automatically create desktop shortcut on first run (Windows only)
    create_shortcut_if_first_run()

    if config_manager.load_local_profile():
        print("\n[+] Loaded local profile (cypy_profile.json)")

    ui.print_logo(APP_VER.lstrip('v'))

    # Load LLM provider from settings
    if cfg.llm_provider:
        provider_name = cfg.llm_provider
    else:
        provider_name = pilih_provider()
        cfg.llm_provider = provider_name
        config_manager.save_settings()

    provider = setup_provider(provider_name)

    # Verify YOLO model assets
    base_model_path, _ = os.path.splitext(config.MODEL_YOLO)
    if not os.path.exists(config.MODEL_YOLO) and not os.path.exists(base_model_path + ".dat"):
        print("[!] YOLO model file not found.")
        raise SystemExit

    if not os.path.exists(config.FONT_MANGA):
        print("[!] Font file not found (will fallback to default).")

    yolo_model = YOLO(config.MODEL_YOLO)

    # Load Target Language
    if cfg.target_language:
        target_language = cfg.target_language
    else:
        target_language = pilih_bahasa()
        cfg.target_language = target_language
        config_manager.save_settings()

    ui.tampilkan_status(provider, target_language)

    while True:
        try:
            raw_input_str = input("\nDrag-and-drop image/PDF/CBZ/folder here (or 'help' 'stop'): ")
            input_file = raw_input_str.strip("\"'& ")

            cmd = input_file.lower()

            if cmd in ("stop", "exit", "quit"):
                print("Goodbye~ ♪")
                break

            if cmd in ("lang", "switch", "change"):
                target_language = pilih_bahasa()
                cfg.target_language = target_language
                config_manager.save_settings()
                continue

            if cmd in ("provider", "api"):
                provider_name = pilih_provider()
                provider = setup_provider(provider_name)
                cfg.llm_provider = provider_name
                config_manager.save_settings()
                ui.tampilkan_status(provider, target_language)
                continue

            if cmd == "model":
                new_model = input("Enter model name: ").strip()
                if new_model:
                    provider.model_name = new_model
                    cfg.set_provider_model(cfg.llm_provider, new_model)
                    config_manager.save_settings()
                    # Also update .env file
                    meta = PROVIDER_REGISTRY.get(cfg.llm_provider)
                    if meta:
                        env_path = os.path.join(ROOT_DIR, ".env")
                        config_manager.save_to_env(env_path, meta.model_env_key, new_model)
                    print(f"[+] Model changed to: {new_model}")
                continue

            if cmd == "status":
                ui.tampilkan_status(provider, target_language)
                continue

            if cmd == "tweak":
                menu_tweak()
                continue

            if cmd == "help":
                ui.tampilkan_help()
                continue

            if not input_file:
                continue

            # Folder batch processing
            if os.path.isdir(input_file):
                start_time = time.time()
                process_folder(input_file, yolo_model, provider=provider, target_language=target_language)
                elapsed = time.time() - start_time
                print(f"\n[Timer] Total time: {elapsed:.1f}s")
                continue

            if os.path.exists(input_file):
                start_time = time.time()

                if input_file.lower().endswith(".pdf"):
                    process_pdf(input_file, yolo_model, provider=provider, target_language=target_language)
                elif input_file.lower().endswith(('.zip', '.cbz', '.rar', '.cbr')):
                    process_archive(input_file, yolo_model, provider=provider, target_language=target_language)
                elif input_file.lower().endswith(config.SUPPORTED_IMAGE_EXTENSIONS):
                    hasil = process_single_image(input_file, yolo_model, provider=provider, target_language=target_language)
                    if hasil:
                        print(f"Done! Saved at: {hasil}")
                else:
                    print("[!] Unsupported format. Please give me PNG, JPG, JPEG, WEBP, PDF, CBZ, ZIP, CBR, or RAR~ ♪")
                    continue

                elapsed = time.time() - start_time
                print(f"[Timer] Completed in {elapsed:.1f}s")
            else:
                print("[!] File not found.")

        except KeyboardInterrupt:
            print("\n\nGoodbye.")
            break
        except Exception as e:
            traceback.print_exc()
            print(f"[!] An error occurred: {e}")
