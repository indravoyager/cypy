import os
import time
from ultralytics import YOLO
from cypy.core.config import (
    MODEL_YOLO, FONT_MANGA, LANG_CODES, SUPPORTED_IMAGE_EXTENSIONS,
    LLM_PROVIDER, CUSTOM_BASE_URL, ROOT_DIR, TARGET_LANGUAGE,
    get_provider_config
)
from cypy.core.translator import proses_satu_gambar, mulai_ritual_pdf, proses_folder
from cypy.core.providers import create_provider
from cypy.core.utils import create_shortcut_if_first_run
from cypy import __version__


# ==========================================
# ✦ PROVIDER SETUP - Choose your translation engine~ ♪ ✦
# ==========================================
PROVIDER_INFO = {
    "gemini": {
        "name": "Google Gemini",
        "env_key": "GEMINI_API_KEY",
        "url": "https://aistudio.google.com/",
        "desc": "Free tier available",
    },
    "openai": {
        "name": "OpenAI",
        "env_key": "OPENAI_API_KEY",
        "url": "https://platform.openai.com/api-keys",
        "desc": "GPT-5.4, GPT-5.4-mini",
    },
    "zen": {
        "name": "Zen (opencode.ai)",
        "env_key": "ZEN_API_KEY",
        "url": "https://opencode.ai/auth",
        "desc": "Free models, optional API key for more quota",
    },
    "openrouter": {
        "name": "OpenRouter",
        "env_key": "OPENROUTER_API_KEY",
        "url": "https://openrouter.ai/keys",
        "desc": "Access 100+ models (Claude, Llama, Mistral, etc.)",
    },
    "custom": {
        "name": "Custom",
        "env_key": "CUSTOM_API_KEY",
        "url": "",
        "desc": "OpenAI-compatible API, custom base URL",
    },
}


def pilih_bahasa():
    print("\n┌─────────────────────────────────────────┐")
    print("│  Target Language / Bahasa Target:       │")
    print("│                                         │")
    print("│  [1] English                            │")
    print("│  [2] Indonesian                         │")
    print("│  [3] Japanese (日本語)                  │")
    print("│  [4] Mandarin (简体中文)                │")
    print("│  [5] Spanish (Español)                  │")
    print("│  [6] Portuguese (Português)             │")
    print("│  [7] Javanese (Basa Jawa)               │")
    print("│  [8] Custom (type your own)             │")
    print("└─────────────────────────────────────────┘")

    lang_choice = input("Select choice / Pilih (1-8) [Default: 2]: ").strip()
    if lang_choice == "1":
        target_language = "English"
    elif lang_choice == "2":
        target_language = "Indonesian"
    elif lang_choice == "3":
        target_language = "Japanese"
    elif lang_choice == "4":
        target_language = "Mandarin"
    elif lang_choice == "5":
        target_language = "Spanish"
    elif lang_choice == "6":
        target_language = "Portuguese"
    elif lang_choice == "7":
        target_language = "Javanese"
    elif lang_choice == "8":
        custom = input("Type your target language (e.g. Korean, Thai, Arabic): ").strip()
        if custom:
            target_language = custom.title()
        else:
            target_language = "Indonesian"
    else:
        target_language = "Indonesian"

    print(f"\n[+] Target language set to: {target_language}")
    return target_language


def pilih_provider():
    print("\n┌─────────────────────────────────────────┐")
    print("│  API Provider:                          │")
    print("│                                         │")
    print("│  [1] Google Gemini (Default, free tier) │")
    print("│  [2] OpenAI (GPT-5.4)                    │")
    print("│  [3] Zen opencode.ai (no key needed)    │")
    print("│  [4] OpenRouter (100+ models)           │")
    print("│  [5] Custom (OpenAI-compatible, own URL)│")
    print("└─────────────────────────────────────────┘")

    choice = input("Select provider (1-5) [Default: 1]: ").strip()
    if choice == "2":
        return "openai"
    elif choice == "3":
        return "zen"
    elif choice == "4":
        return "openrouter"
    elif choice == "5":
        return "custom"
    else:
        return "gemini"


def _save_to_env(env_path, env_key, api_key, provider_name):
    """Write/update a key in .env file."""
    existing_lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            existing_lines = f.readlines()

    key_found = False
    new_lines = []
    for line in existing_lines:
        if line.strip().startswith(f"{env_key}="):
            new_lines.append(f"{env_key}={api_key}\n")
            key_found = True
        else:
            new_lines.append(line)
    if not key_found:
        new_lines.append(f"{env_key}={api_key}\n")

    provider_found = any(l.strip().startswith("LLM_PROVIDER=") for l in new_lines)
    if not provider_found:
        new_lines.insert(0, f"LLM_PROVIDER={provider_name}\n")

    # Ensure default model written once
    model_defaults = {
        "gemini": "MODEL_GEMINI=gemini-3.1-flash-lite\n",
        "openai": "MODEL_OPENAI=gpt-5.4-mini\n",
        "openrouter": "MODEL_OPENROUTER=qwen/qwen2.5-vl-72b-instruct:free\n",
        "zen": "MODEL_ZEN=minimax-m3-free\n",
        "custom": "MODEL_CUSTOM=gpt-5.4-mini\n",
    }
    if provider_name in model_defaults:
        prefix = model_defaults[provider_name].split("=")[0] + "="
        if not any(l.strip().startswith(prefix) for l in new_lines):
            new_lines.append(model_defaults[provider_name])

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def _save_to_env_simple(env_path, key, value):
    """Write/update a single key=value line in .env file."""
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


def _env_has_key(env_path, key):
    """Check if a key exists in the .env file."""
    if not os.path.exists(env_path):
        return False
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith(f"{key}="):
                return True
    return False


def setup_provider(provider_name=None):
    """Sets up the LLM provider, requesting API key if missing~ ♪"""
    import cypy.core.config as config

    if provider_name is None:
        provider_name = config.LLM_PROVIDER

    api_key, model_name = get_provider_config(provider_name)
    info = PROVIDER_INFO.get(provider_name, PROVIDER_INFO["gemini"])
    env_path = os.path.join(config.ROOT_DIR, ".env")

    if provider_name == "zen":
        # Key is optional — prompt only if not already set
        if not api_key:
            print(f"\n[i] Zen (opencode.ai) works without an API key~ ♪")
            print(f"    Optional: get a key at {info['url']} for more quota.")
            entered = input("Paste your Zen API Key (or press Enter to skip): ").strip()
            if entered:
                api_key = entered
                try:
                    _save_to_env(env_path, info["env_key"], api_key, provider_name)
                    config.ZEN_API_KEY = api_key
                    os.environ[info["env_key"]] = api_key
                    print(f"[+] Zen API Key saved to: {env_path} (✿◠‿◠)")
                except Exception as e:
                    print(f"[!] Warning: Failed to save API Key to .env: {e}")
            else:
                print("[+] Proceeding without API key~ ♪")

    elif provider_name == "custom":
        # Custom provider: base URL is required, API key is optional
        base_url = CUSTOM_BASE_URL
        if not base_url:
            print(f"\n[i] Enter the base URL for your OpenAI-compatible API.")
            print(f"    Example: https://api.example.com/v1")
            entered = input("Base URL: ").strip()
            while not entered:
                entered = input("Base URL cannot be empty: ").strip()
            base_url = entered
            # Save base URL to .env
            try:
                _save_to_env_simple(env_path, "CUSTOM_BASE_URL", base_url)
                config.CUSTOM_BASE_URL = base_url
                os.environ["CUSTOM_BASE_URL"] = base_url
                print(f"[+] Base URL saved to: {env_path}")
            except Exception as e:
                print(f"[!] Warning: Failed to save Base URL: {e}")

        if not api_key:
            print(f"\n[i] API key is optional (some providers don't require one).")
            entered = input("Paste your API Key (or press Enter to skip): ").strip()
            if entered:
                api_key = entered
                try:
                    _save_to_env(env_path, info["env_key"], api_key, provider_name)
                    config.CUSTOM_API_KEY = api_key
                    os.environ[info["env_key"]] = api_key
                    print(f"[+] API Key saved to: {env_path} (✿◠‿◠)")
                except Exception as e:
                    print(f"[!] Warning: Failed to save API Key to .env: {e}")
            else:
                print("[+] Proceeding without API key~ ♪")

    elif not api_key:
        print(f"\n[!] {info['name']} API Key is missing!")
        print(f"Get your API key from: {info['url']}")
        api_key = input(f"Please paste your {info['name']} API Key here: ").strip()

        while not api_key:
            api_key = input("API Key cannot be empty. Please paste your API Key: ").strip()

        try:
            _save_to_env(env_path, info["env_key"], api_key, provider_name)
            print(f"[+] API Key saved to: {env_path} (✿◠‿◠)")

            if provider_name == "gemini":
                config.GEMINI_API_KEY = api_key
            elif provider_name == "openrouter":
                config.OPENROUTER_API_KEY = api_key
            elif provider_name == "openai":
                config.OPENAI_API_KEY = api_key

            os.environ[info["env_key"]] = api_key

        except Exception as e:
            print(f"[!] Warning: Failed to save API Key to .env: {e}")

    extra = {}
    if provider_name == "custom":
        extra["base_url"] = config.CUSTOM_BASE_URL

    provider = create_provider(provider_name, api_key=api_key, model_name=model_name, **extra)
    return provider


def tampilkan_help():
    print("\n┌─────────────────────────────────────────────────────┐")
    print("│  Available Commands:                                │")
    print("│                                                     │")
    print("│  [drag file]    Translate a single image or PDF     │")
    print("│  [drag folder]  Batch translate all images in folder │")
    print("│  lang / switch  Change target language              │")
    print("│  provider / api Switch API provider                 │")
    print("│  model          Change the LLM model                │")
    print("│  status         Show current settings               │")
    print("│  help           Show this help menu                 │")
    print("│  stop / exit    Exit cypy                           │")
    print("├─────────────────────────────────────────────────────┤")
    print("│  API Providers Info:                                │")
    print("│  To use OpenRouter or OpenAI, add these to .env:    │")
    print("│  OPENROUTER_API_KEY=\"your_key_here\"                 │")
    print("│  OPENAI_API_KEY=\"your_key_here\"                     │")
    print("│  Zen: free without key, or get one at:             │")
    print("│  https://opencode.ai/auth  (ZEN_API_KEY)           │")
    print("│  Custom: set CUSTOM_BASE_URL in .env               │")
    print("│  CUSTOM_BASE_URL=https://your-api/v1               │")
    print("└─────────────────────────────────────────────────────┘")


def tampilkan_status(provider, target_language):
    print(f"\n  Provider : {provider.provider_name}")
    print(f"  Model    : {provider.model_name}")
    if hasattr(provider, "base_url"):
        print(f"  Base URL : {provider.base_url}")
    print(f"  Language : {target_language}")


def main():
    # Automatically create desktop shortcut on first run (Windows only)
    create_shortcut_if_first_run()

    print(f"CYPY v{__version__} - Manga Translator")
    print("Ready to translate~ (◠‿●) ~♪")

    env_path = os.path.join(ROOT_DIR, ".env")
    has_provider = _env_has_key(env_path, "LLM_PROVIDER")
    has_language = _env_has_key(env_path, "TARGET_LANGUAGE")

    if has_provider:
        provider_name = LLM_PROVIDER
    else:
        provider_name = pilih_provider()
        _save_to_env_simple(env_path, "LLM_PROVIDER", provider_name)

    provider = setup_provider(provider_name)

    if not os.path.exists(MODEL_YOLO):
        print("[!] YOLO model file not found.")
        raise SystemExit

    if not os.path.exists(FONT_MANGA):
        print("[!] Font file not found (will fallback to default).")

    yolo_model = YOLO(MODEL_YOLO)

    if has_language:
        target_language = TARGET_LANGUAGE or "Indonesian"
    else:
        target_language = pilih_bahasa()
        _save_to_env_simple(env_path, "TARGET_LANGUAGE", target_language)

    # Show current config
    tampilkan_status(provider, target_language)

    print("\nReady! Drag-and-drop files or folders to translate. Type 'help' for commands.")

    while True:
        try:
            raw_input_str = input("\nDrag-and-drop image/PDF/folder here (or 'help' 'stop'): ")
            input_file = raw_input_str.strip("\"'& ")

            cmd = input_file.lower()

            if cmd in ("stop", "exit", "quit"):
                print("Goodbye~ ♪")
                break

            if cmd in ("lang", "switch", "change"):
                target_language = pilih_bahasa()
                continue

            if cmd in ("provider", "api"):
                provider_name = pilih_provider()
                provider = setup_provider(provider_name)
                tampilkan_status(provider, target_language)
                continue

            if cmd == "model":
                new_model = input("Enter model name: ").strip()
                if new_model:
                    provider.model_name = new_model
                    print(f"[+] Model changed to: {new_model}")
                continue

            if cmd == "status":
                tampilkan_status(provider, target_language)
                continue

            if cmd == "help":
                tampilkan_help()
                continue

            if not input_file:
                continue

            # Folder batch processing
            if os.path.isdir(input_file):
                start_time = time.time()
                proses_folder(input_file, yolo_model, provider=provider, target_language=target_language)
                elapsed = time.time() - start_time
                print(f"\n[Timer] Total time: {elapsed:.1f}s")
                continue

            if os.path.exists(input_file):
                start_time = time.time()

                if input_file.lower().endswith(".pdf"):
                    mulai_ritual_pdf(input_file, yolo_model, provider=provider, target_language=target_language)

                elif input_file.lower().endswith(SUPPORTED_IMAGE_EXTENSIONS):
                    hasil = proses_satu_gambar(input_file, yolo_model, provider=provider, target_language=target_language)

                    if hasil:
                        print(f"Done! Saved at: {hasil}")

                else:
                    print("[!] Unsupported format. Please give me PNG, JPG, JPEG, WEBP, or PDF~")
                    continue

                elapsed = time.time() - start_time
                print(f"[Timer] Completed in {elapsed:.1f}s")

            else:
                print("[!] File not found.")

        except KeyboardInterrupt:
            print("\n\nGoodbye~ ♪")
            break
        except Exception as e:
            print(f"[!] An error occurred: {e}")


if __name__ == "__main__":
    main()