import os
import time
from ultralytics import YOLO
from cypy.core.config import (
    MODEL_YOLO, FONT_MANGA, LANG_CODES, SUPPORTED_IMAGE_EXTENSIONS,
    LLM_PROVIDER, get_provider_config
)
from cypy.core.translator import proses_satu_gambar, mulai_ritual_pdf, proses_folder, mulai_ritual_archive
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
    "openrouter": {
        "name": "OpenRouter",
        "env_key": "OPENROUTER_API_KEY",
        "url": "https://openrouter.ai/keys",
        "desc": "Access 100+ models (Claude, Llama, Mistral, etc.)",
    },
    "openai": {
        "name": "OpenAI",
        "env_key": "OPENAI_API_KEY",
        "url": "https://platform.openai.com/api-keys",
        "desc": "GPT-4o, GPT-4o-mini",
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
    print("│  [2] OpenRouter (100+ models)           │")
    print("│  [3] OpenAI (GPT-4o)                    │")
    print("└─────────────────────────────────────────┘")

    choice = input("Select provider (1-3) [Default: 1]: ").strip()
    if choice == "2":
        return "openrouter"
    elif choice == "3":
        return "openai"
    else:
        return "gemini"


def setup_provider(provider_name=None):
    """Sets up the LLM provider, requesting API key if missing~ ♪"""
    import cypy.core.config as config

    if provider_name is None:
        provider_name = config.LLM_PROVIDER

    api_key, model_name = get_provider_config(provider_name)
    info = PROVIDER_INFO.get(provider_name, PROVIDER_INFO["gemini"])

    if not api_key:
        print(f"\n[!] {info['name']} API Key is missing!")
        print(f"Get your API key from: {info['url']}")
        api_key = input(f"Please paste your {info['name']} API Key here: ").strip()

        while not api_key:
            api_key = input("API Key cannot be empty. Please paste your API Key: ").strip()

        # Save to .env file
        env_path = os.path.join(config.ROOT_DIR, ".env")
        try:
            # Read existing .env content
            existing_lines = []
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    existing_lines = f.readlines()

            # Update or add the key
            env_key = info["env_key"]
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

            # Ensure LLM_PROVIDER is set
            provider_found = any(l.strip().startswith("LLM_PROVIDER=") for l in new_lines)
            if not provider_found:
                new_lines.insert(0, f"LLM_PROVIDER={provider_name}\n")

            # Ensure model name is set in .env for clarity
            if provider_name == "gemini":
                model_found = any(l.strip().startswith("MODEL_GEMINI=") for l in new_lines)
                if not model_found:
                    new_lines.append("MODEL_GEMINI=gemini-3.1-flash-lite\n")
            elif provider_name == "openai":
                model_found = any(l.strip().startswith("MODEL_OPENAI=") for l in new_lines)
                if not model_found:
                    new_lines.append("MODEL_OPENAI=gpt-4o-mini\n")
            elif provider_name == "openrouter":
                model_found = any(l.strip().startswith("MODEL_OPENROUTER=") for l in new_lines)
                if not model_found:
                    new_lines.append("MODEL_OPENROUTER=google/gemini-2.0-flash-exp:free\n")

            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

            print(f"[+] API Key saved to: {env_path} (✿◠‿◠)")

            # Update running config in memory
            if provider_name == "gemini":
                config.GEMINI_API_KEY = api_key
            elif provider_name == "openrouter":
                config.OPENROUTER_API_KEY = api_key
            elif provider_name == "openai":
                config.OPENAI_API_KEY = api_key

            os.environ[env_key] = api_key

        except Exception as e:
            print(f"[!] Warning: Failed to save API Key to .env: {e}")

    provider = create_provider(provider_name, api_key=api_key, model_name=model_name)
    return provider


def tampilkan_help():
    print("\n┌─────────────────────────────────────────────────────┐")
    print("│  Available Commands:                                │")
    print("│                                                     │")
    print("│  [drag file]    Translate a single image, PDF, or CBZ │")
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
    print("└─────────────────────────────────────────────────────┘")


def tampilkan_status(provider, target_language):
    print(f"\n  Provider : {provider.provider_name}")
    print(f"  Model    : {provider.model_name}")
    print(f"  Language : {target_language}")


def main():
    # Automatically create desktop shortcut on first run (Windows only)
    create_shortcut_if_first_run()

    print(f"CYPY v{__version__} - Manga Translator")
    print("Ready to translate~ (◠‿●) ~♪")

    # Always let user choose provider
    provider_name = pilih_provider()
    provider = setup_provider(provider_name)

    if not os.path.exists(MODEL_YOLO):
        print("[!] YOLO model file not found.")
        raise SystemExit

    if not os.path.exists(FONT_MANGA):
        print("[!] Font file not found (will fallback to default).")

    yolo_model = YOLO(MODEL_YOLO)

    target_language = pilih_bahasa()

    # Show current config
    tampilkan_status(provider, target_language)

    print("\nReady! Drag-and-drop files or folders to translate. Type 'help' for commands.")

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

                elif input_file.lower().endswith(('.zip', '.cbz', '.rar', '.cbr')):
                    mulai_ritual_archive(input_file, yolo_model, provider=provider, target_language=target_language)

                elif input_file.lower().endswith(SUPPORTED_IMAGE_EXTENSIONS):
                    hasil = proses_satu_gambar(input_file, yolo_model, provider=provider, target_language=target_language)

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
            print(f"[!] An error occurred: {e}")


if __name__ == "__main__":
    main()
