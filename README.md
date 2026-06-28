# cypy

<p align="center">
  <img src="assets/favicon.png" width="128" alt="cypy Logo" />
</p>

**cypy** is a CLI manga translator using YOLOv8 to detect speech bubbles and the Google Gemini API to translate foreign text, keeping artwork clean and typography well-fitted.

---

## Preview

| Before (Original Page) | After (Translated Page) |
| :---: | :---: |
| ![Original Manga Page](assets/before.jpg) | ![Translated Indonesian Manga Page](assets/after.png) |

---

## Features

- **Multi-Language Support:** Translate to English, Indonesian, Japanese (with native vertical *Tategaki* text!), Spanish, Portuguese, Javanese, and **Custom Languages** (supports Thai, Arabic, Cyrillic, etc. with automatic full variable font downloading!).
- **Multi-Provider AI:** Choose between **Google Gemini**, **OpenRouter** (100+ models like Claude 3.5 Sonnet), or **OpenAI** (GPT-4o) directly from the CLI.
- **Interactive Commands:** Change the target language (`lang`), switch API providers (`provider`), change models (`model`), or check current settings (`status`) on the fly inside the loop.
- **Zero-Setup Startup:** Prompts for the API key in the CLI and generates the `.env` file automatically if missing.
- **Auto Desktop Shortcut:** Creates a rounded Windows desktop shortcut automatically on the first run.

---

## Installation & Setup

### Option 1: Standalone Release (Recommended)
Download the pre-compiled package for your OS from the [Releases](https://github.com/indravoyager/cypy/releases) page.
1. Download and extract the `.zip` file.
2. Run the application:
   - **Windows:** Double-click `cypy.exe` inside the extracted folder. A desktop shortcut with the custom cypy icon will be automatically created on the first run!
   - **Linux:** Open a terminal in the extracted folder, make it executable, and run:
     ```bash
     chmod +x cypy
     ./cypy
     ```
   - **macOS:** Run `./cypy` inside the extracted folder.
3. Paste your Gemini API key when prompted on the first run.

### Option 2: Run from Source (For Developers)
1. **Clone the repo:**
   ```bash
   git clone https://github.com/indravoyager/cypy.git
   cd cypy
   ```
2. **Set up virtual environment:**
   ```bash
   python -m venv venv
   # Activate:
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate     # Windows (CMD)
   ```
3. **Install in editable mode:**
   ```bash
   pip install -e .
   ```
4. **Run the application:**
   Once installed, you can launch the app from any directory:
   ```bash
   cypy
   ```
   Or run it directly as a module from the project root:
   ```bash
   python -m cypy
   ```

---

## Configuration

Customise settings inside the `.env` file:

```env
# Gemini Config (Default)
GEMINI_API_KEY=your_gemini_api_key_here
MODEL_GEMINI=gemini-3.1-flash-lite-preview

# OpenAI Config (Optional)
OPENAI_API_KEY=your_openai_api_key_here
MODEL_OPENAI=gpt-4o

# OpenRouter Config (Optional)
OPENROUTER_API_KEY=your_openrouter_api_key_here
MODEL_OPENROUTER=anthropic/claude-3.5-sonnet
```

> [!NOTE]
> Advanced layout settings (margins, font scales, etc.) can be adjusted in [cypy/core/config.py](cypy/core/config.py).

---

## Project Structure

```text
cypy/
├── assets/              # YOLO model weights, font, and icons
├── cypy/                # Main Python package
│   ├── app.py           # Entrypoint loop & CLI logic
│   └── core/            # Engine modules (translator, configs, utilities)
├── pyproject.toml       # Python package configuration
└── README.md
```

---

## License

Distributed under the [MIT License](LICENSE).
