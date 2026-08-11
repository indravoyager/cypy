import os
import sys
import math
import queue
import threading
import time
import traceback
import webbrowser
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES
from PIL import Image

import cypy.core.config as config
from cypy.core.config import config_manager, PROVIDER_REGISTRY, LANGUAGE_CHOICES
from cypy.core.yolo_onnx import YOLOONNX
from cypy.core.providers import create_provider
from cypy.core.translator import process_single_image, process_pdf, process_folder, process_archive
from cypy.core.version import APP_VER
from cypy.gui.info import InfoDialog
from cypy.gui.widgets import QueueWriteDescriptor, RetroOptionMenu
from cypy.gui.theme import (
    COLOR_BG, COLOR_CARD, COLOR_WIDGET, COLOR_BORDER,
    COLOR_PINK, COLOR_WHITE, COLOR_GRAY, COLOR_DARK_BTN, COLOR_DARK_BTN_HOVER,
    COLOR_GREEN, COLOR_ORANGE, COLOR_RED,
)


class CYPYWindow(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        ctk.CTk.__init__(self)
        TkinterDnD.DnDWrapper.__init__(self)

        try:
            self.TkdndVersion = TkinterDnD._require(self)
        except Exception as e:
            self.append_log(f"[!] Failed to initialize drag and drop: {e}")

        self.ic_folder = None
        self.ic_settings = None
        try:
            assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets')
            icon_file = os.path.join(assets_dir, 'icons', 'folder.png')
            if os.path.exists(icon_file):
                pil_img = Image.open(icon_file)
                self.ic_folder = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(20, 20))

            icon_settings_file = os.path.join(assets_dir, 'icons', 'settings.png')
            if os.path.exists(icon_settings_file):
                pil_img_settings = Image.open(icon_settings_file)
                self.ic_settings = ctk.CTkImage(light_image=pil_img_settings, dark_image=pil_img_settings, size=(14, 14))
        except Exception as e:
            self.append_log(f"[!] Failed to load icons: {e}")
            traceback.print_exc()

        try:
            self.withdraw()
            self.attributes("-alpha", 0.0)
        except Exception as e:
            self.append_log(f"[!] Failed to set window transparency early: {e}")

        self.title(f"cypy {APP_VER}")
        w_awal, h_awal = 750, 460
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (w_awal // 2)
        y = (screen_height // 2) - (h_awal // 2)
        self.geometry(f"{w_awal}x{h_awal}+{x}+{y}")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)

        self.yolo_model = None
        self.yolo_loading_done = False
        self.translating = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self.create_header()
        self.create_main_panel()

        self.log_queue = queue.Queue()
        sys.stdout = QueueWriteDescriptor(self.log_queue.put, sys.__stdout__)
        sys.stderr = QueueWriteDescriptor(self.log_queue.put, sys.__stderr__)

        self.after(100, self.process_log_queue)
        self.load_settings_into_ui()

        threading.Thread(target=self.load_yolo_model, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.show_loading_screen()

    def show_loading_screen(self):
        splash = ctk.CTkToplevel(self)
        w_splash, h_splash = 250, 280

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x_pos = (screen_width // 2) - (w_splash // 2)
        y_pos = (screen_height // 2) - (h_splash // 2)

        splash.geometry(f"{w_splash}x{h_splash}+{x_pos}+{y_pos}")
        splash.overrideredirect(True)
        try:
            splash.attributes("-topmost", True)
        except Exception:
            pass

        transparent_color = "#000001"
        splash.configure(fg_color=transparent_color)
        if sys.platform == 'win32':
            try:
                splash.attributes("-transparentcolor", transparent_color)
            except Exception:
                pass

        card_frame = ctk.CTkFrame(splash, fg_color=COLOR_BG, corner_radius=0, border_width=1, border_color="#333333")
        card_frame.pack(fill="both", expand=True, padx=2, pady=2)

        frame_pusat = ctk.CTkFrame(card_frame, fg_color="transparent")
        frame_pusat.pack(expand=True, fill="both", padx=15, pady=20)

        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'favicon.ico')
        try:
            if os.path.exists(icon_path):
                img_asli = Image.open(icon_path)
                img_logo = ctk.CTkImage(light_image=img_asli, dark_image=img_asli, size=(90, 90))
                lbl_logo = ctk.CTkLabel(frame_pusat, text="", image=img_logo)
                lbl_logo.pack(pady=(5, 10))
            else:
                ctk.CTkLabel(frame_pusat, text="◇", font=("Terminal", 60), text_color=COLOR_PINK).pack(pady=(5, 10))
        except Exception as e:
            self.append_log(f"[!] Error loading splash logo: {e}")
            ctk.CTkLabel(frame_pusat, text="◇", font=("Terminal", 60), text_color=COLOR_PINK).pack(pady=(5, 10))

        ctk.CTkLabel(frame_pusat, text="cypy", font=("Terminal", 22, "bold"), text_color=COLOR_PINK).pack(pady=(0, 2))
        lbl_status = ctk.CTkLabel(frame_pusat, text="Initializing...", font=("Terminal", 10, "italic"), text_color="#888888")
        lbl_status.pack(pady=(0, 15))

        progress_loading = ctk.CTkProgressBar(frame_pusat, width=180, height=4, corner_radius=0, progress_color=COLOR_PINK, fg_color=COLOR_DARK_BTN)
        progress_loading.pack()
        progress_loading.set(0)

        def run_loading(value=0):
            if value < 0.9:
                progress_loading.set(value)
                lbl_status.configure(text="Loading neural engine...")
                splash.after(15, lambda: run_loading(value + 0.02))
            else:
                base_model_path, _ = os.path.splitext(config.MODEL_YOLO)
                model_missing = not os.path.exists(config.MODEL_YOLO) and not os.path.exists(base_model_path + ".dat")

                if getattr(self, 'yolo_loading_done', False) or model_missing:
                    if value <= 1.0:
                        progress_loading.set(value)
                        lbl_status.configure(text="Engine Ready!" if self.yolo_model else "Engine Failed!")
                        splash.after(15, lambda: run_loading(value + 0.05))
                    else:
                        try:
                            self.deiconify()
                            self.lift()
                            self.focus_force()
                            self.attributes("-topmost", True)
                            self.after(50, lambda: self.attributes("-topmost", False))
                            self.update()
                        except Exception:
                            pass
                        splash.destroy()
                        try:
                            self.attributes("-alpha", 1.0)
                        except Exception:
                            pass

                        try:
                            if os.path.exists(icon_path):
                                self.iconbitmap(icon_path)
                        except Exception:
                            pass
                else:
                    progress_loading.set(0.9)
                    lbl_status.configure(text="Initializing YOLO model...")
                    splash.after(50, lambda: run_loading(0.9))

        splash.after(200, lambda: run_loading(0))

    def create_header(self):
        header_frame = ctk.CTkFrame(self, fg_color=COLOR_BG, height=38, corner_radius=0, border_width=1, border_color=COLOR_BORDER)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        header_frame.grid_propagate(False)
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0)
        header_frame.grid_columnconfigure(2, weight=0)

        title_container = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_container.grid(row=0, column=0, padx=12, pady=6, sticky="w")

        lbl_logo = ctk.CTkLabel(
            title_container, text="◇ cypy ◇",
            font=("Fixedsys", 16), text_color=COLOR_PINK
        )
        lbl_logo.pack(side="left")

        lbl_desc = ctk.CTkLabel(
            title_container, text="Manga Translator",
            font=("Terminal", 10), text_color=COLOR_GRAY
        )
        lbl_desc.pack(side="left", padx=(8, 0))

        self.lbl_status = ctk.CTkLabel(
            header_frame, text="Initializing...",
            font=("Terminal", 10, "bold"), text_color=COLOR_ORANGE
        )
        self.lbl_status.grid(row=0, column=1, padx=(0, 8), pady=6, sticky="e")

        btn_info = ctk.CTkButton(
            header_frame, text="", image=self.ic_settings, width=22, height=22,
            fg_color="transparent", hover_color="#333333", border_width=0,
            corner_radius=0, command=self.show_info_popup
        )
        btn_info.grid(row=0, column=2, padx=(0, 12), pady=6, sticky="e")

    def create_main_panel(self):
        left_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        left_container.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(8, 12))
        left_container.grid_columnconfigure(0, weight=1)
        left_container.grid_rowconfigure(0, weight=0)
        left_container.grid_rowconfigure(1, weight=0)
        left_container.grid_rowconfigure(2, weight=1)
        left_container.grid_rowconfigure(3, weight=0)

        card1 = ctk.CTkFrame(left_container, fg_color=COLOR_CARD, border_width=0, corner_radius=8)
        card1.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        card1.grid_columnconfigure(0, weight=1)
        card1.grid_columnconfigure(1, weight=0)
        card1.grid_columnconfigure(2, weight=0)

        lbl_card1 = ctk.CTkLabel(
            card1, text="SOURCE SELECTOR",
            font=("Terminal", 10, "bold"), text_color=COLOR_WHITE
        )
        lbl_card1.grid(row=0, column=0, columnspan=3, padx=10, pady=(6, 3), sticky="w")

        self.path_entry = ctk.CTkEntry(
            card1, placeholder_text="Select file/folder to translate...",
            font=("Consolas", 10), fg_color=COLOR_WIDGET, text_color=COLOR_WHITE,
            border_width=0, corner_radius=6, height=26
        )
        self.path_entry.configure(state="disabled")
        self.path_entry.grid(row=1, column=0, padx=(10, 6), pady=(0, 8), sticky="ew")

        btn_file = ctk.CTkButton(
            card1, text="FILE", width=55, height=26,
            font=("Consolas", 10, "bold"), text_color=COLOR_WHITE,
            fg_color=COLOR_DARK_BTN, hover_color=COLOR_DARK_BTN_HOVER, border_width=0,
            corner_radius=6, command=lambda: self.open_file_selector("file")
        )
        btn_file.grid(row=1, column=1, padx=3, pady=(0, 8), sticky="e")

        btn_folder = ctk.CTkButton(
            card1, text="FOLDER", width=55, height=26,
            font=("Consolas", 10, "bold"), text_color=COLOR_WHITE,
            fg_color=COLOR_DARK_BTN, hover_color=COLOR_DARK_BTN_HOVER, border_width=0,
            corner_radius=6, command=lambda: self.open_file_selector("folder")
        )
        btn_folder.grid(row=1, column=2, padx=(3, 10), pady=(0, 8), sticky="e")

        try:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self.handle_file_drop)
            self.path_entry._entry.drop_target_register(DND_FILES)
            self.path_entry._entry.dnd_bind('<<Drop>>', self.handle_file_drop)
        except Exception:
            pass

        card2 = ctk.CTkFrame(left_container, fg_color=COLOR_CARD, border_width=0, corner_radius=8)
        card2.grid(row=1, column=0, sticky="ew", pady=0)
        card2.grid_columnconfigure(0, weight=1)
        card2.grid_columnconfigure(1, weight=1)

        lbl_card2 = ctk.CTkLabel(
            card2, text="TRANSLATION SETTINGS",
            font=("Terminal", 10, "bold"), text_color=COLOR_WHITE
        )
        lbl_card2.grid(row=0, column=0, columnspan=2, padx=10, pady=(6, 4), sticky="w")

        def create_field(parent, label_text, row, col, widget_class, **kwargs):
            frame = ctk.CTkFrame(parent, fg_color="transparent")
            frame.grid(row=row, column=col, padx=10, pady=3, sticky="ew")
            frame.grid_columnconfigure(0, weight=1)

            lbl = ctk.CTkLabel(frame, text=label_text, font=("Terminal", 9, "bold"), text_color=COLOR_GRAY, anchor="w")
            lbl.grid(row=0, column=0, sticky="w", pady=(0, 2))

            widget = widget_class(frame, **kwargs)
            widget.grid(row=1, column=0, sticky="ew")
            return widget

        provider_display_names = [p.display_name for p in PROVIDER_REGISTRY.values()]

        self.lang_spinner = create_field(
            card2, "TARGET LANGUAGE", 1, 0, RetroOptionMenu,
            values=LANGUAGE_CHOICES,
            font=("Consolas", 10), height=26, command=self.on_lang_changed
        )

        self.provider_spinner = create_field(
            card2, "AI PROVIDER", 1, 1, RetroOptionMenu,
            values=provider_display_names,
            font=("Consolas", 10), height=26, command=self.on_provider_changed
        )

        self.api_key_entry = create_field(
            card2, "API KEY", 2, 0, ctk.CTkEntry,
            show="•", placeholder_text="Enter provider API key...",
            font=("Consolas", 10), fg_color=COLOR_WIDGET, text_color=COLOR_WHITE,
            border_width=0, corner_radius=6, height=26
        )
        self.api_key_entry.bind("<KeyRelease>", lambda e: self.on_api_key_changed(self.api_key_entry.get()))

        self.model_entry = create_field(
            card2, "MODEL NAME", 2, 1, ctk.CTkEntry,
            placeholder_text="e.g. gemini-3.1-flash-lite",
            font=("Consolas", 10), fg_color=COLOR_WIDGET, text_color=COLOR_WHITE,
            border_width=0, corner_radius=6, height=26
        )
        self.model_entry.bind("<KeyRelease>", lambda e: self.on_model_changed(self.model_entry.get()))

        self.sfx_spinner = create_field(
            card2, "SFX FILTER MODE", 3, 0, RetroOptionMenu,
            values=['balanced', 'relaxed', 'strict'],
            font=("Consolas", 10), height=26, command=self.on_sfx_changed
        )

        self.base_url_entry = create_field(
            card2, "BASE URL (CUSTOM PROVIDER)", 3, 1, ctk.CTkEntry,
            placeholder_text="https://api.yourprovider.com/v1",
            font=("Consolas", 10), fg_color=COLOR_WIDGET, text_color=COLOR_WHITE,
            border_width=0, corner_radius=6, height=26
        )
        self.base_url_entry.bind("<KeyRelease>", lambda e: self.on_base_url_changed(self.base_url_entry.get()))

        ctk.CTkButton(
            card2, text="ADVANCED SETTINGS", height=24,
            font=("Consolas", 9, "bold"), text_color=COLOR_WHITE,
            fg_color=COLOR_DARK_BTN, hover_color=COLOR_DARK_BTN_HOVER,
            corner_radius=6, command=self.open_advanced_settings,
        ).grid(row=4, column=0, columnspan=2, padx=10, pady=(6, 4), sticky="ew")

        ctk.CTkLabel(card2, text="", height=4).grid(row=5, column=0, columnspan=2)

        action_frame = ctk.CTkFrame(left_container, fg_color="transparent")
        action_frame.grid(row=3, column=0, sticky="ew")
        action_frame.grid_columnconfigure(0, weight=1)
        action_frame.grid_columnconfigure(1, weight=0)

        self.translate_btn = ctk.CTkButton(
            action_frame, text="Translate Now", font=("Consolas", 11, "bold"), text_color=COLOR_WHITE,
            fg_color=COLOR_PINK, hover_color="#be185d", corner_radius=6, height=32,
            command=self.start_translation
        )
        self.translate_btn.grid(row=0, column=0, sticky="ew", padx=(0, 3))

        self.open_folder_btn = ctk.CTkButton(
            action_frame, text="" if self.ic_folder else "Folder", image=self.ic_folder,
            fg_color=COLOR_DARK_BTN, hover_color=COLOR_DARK_BTN_HOVER, border_width=0,
            corner_radius=6, height=32, width=32,
            command=self.open_output_folder
        )
        self.open_folder_btn.grid(row=0, column=1, sticky="ew", padx=(3, 0))

        right_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        right_container.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(8, 12))
        right_container.grid_columnconfigure(0, weight=1)
        right_container.grid_rowconfigure(0, weight=1)

        card3 = ctk.CTkFrame(right_container, fg_color=COLOR_CARD, border_width=0, corner_radius=8)
        card3.grid(row=0, column=0, sticky="nsew")
        card3.grid_columnconfigure(0, weight=1)
        card3.grid_rowconfigure(0, weight=0)
        card3.grid_rowconfigure(1, weight=1)

        lbl_log = ctk.CTkLabel(card3, text="LOG CONSOLE", font=("Terminal", 10, "bold"), text_color=COLOR_WHITE, anchor="w")
        lbl_log.grid(row=0, column=0, padx=10, pady=(8, 4), sticky="w")

        self.log_textbox = ctk.CTkTextbox(
            card3, font=("Consolas", 10), fg_color=COLOR_WIDGET, text_color=COLOR_GREEN,
            border_width=0, corner_radius=6,
            scrollbar_button_color="#383838",
            scrollbar_button_hover_color="#555555"
        )
        try:
            self.log_textbox._y_scrollbar.configure(width=4)
        except Exception:
            pass
        self.log_textbox.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.log_textbox.insert("end", "CYPY Ready.\n")
        self.log_textbox.configure(state="disabled")

    def process_log_queue(self):
        """Process log messages in batches to prevent UI thread freezing."""
        count = 0
        try:
            self.log_textbox.configure(state="normal")
            while count < 50:  # Max 50 messages per tick to prevent UI lag
                msg = self.log_queue.get_nowait()
                self.log_textbox.insert("end", msg)
                count += 1
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")
        except queue.Empty:
            try:
                self.log_textbox.configure(state="disabled")
            except Exception:
                pass
        self.after(100, self.process_log_queue)

    def load_settings_into_ui(self):
        cfg = config_manager.config
        lang = cfg.target_language or "Indonesian"
        self.lang_spinner.set(lang)

        provider_name = cfg.llm_provider.lower()
        meta = PROVIDER_REGISTRY.get(provider_name, PROVIDER_REGISTRY["gemini"])
        self.provider_spinner.set(meta.display_name)

        self.sfx_spinner.set(cfg.filter_sfx_mode)
        self.update_provider_fields(provider_name)

    def update_provider_fields(self, provider_code):
        api_key, model_name = config_manager.config.get_provider_config(provider_code)

        self.api_key_entry.configure(state="normal")
        self.api_key_entry.delete(0, "end")
        self.api_key_entry.insert(0, api_key)

        self.model_entry.configure(state="normal")
        self.model_entry.delete(0, "end")
        self.model_entry.insert(0, model_name)

        if provider_code == 'custom':
            self.base_url_entry.configure(state="normal")
            self.base_url_entry.delete(0, "end")
            self.base_url_entry.insert(0, config_manager.config.custom_base_url)
        else:
            self.base_url_entry.delete(0, "end")
            self.base_url_entry.configure(state="disabled")

    def on_lang_changed(self, value):
        config_manager.config.target_language = value
        config_manager.save_settings()
        self.append_log(f"Language: {value}\n")

    def on_provider_changed(self, value):
        provider_code = "gemini"
        for k, meta in PROVIDER_REGISTRY.items():
            if meta.display_name == value:
                provider_code = k
                break

        config_manager.config.llm_provider = provider_code
        config_manager.save_settings()

        self.update_provider_fields(provider_code)
        self.append_log(f"Provider: {value}\n")

    def on_api_key_changed(self, value):
        provider_code = config_manager.config.llm_provider
        config_manager.config.set_provider_api_key(provider_code, value)
        config_manager.save_settings()

    def on_model_changed(self, value):
        provider_code = config_manager.config.llm_provider
        config_manager.config.set_provider_model(provider_code, value)
        config_manager.save_settings()

    def on_base_url_changed(self, value):
        if config_manager.config.llm_provider == "custom":
            config_manager.config.custom_base_url = value
            config_manager.save_settings()

    def on_sfx_changed(self, value):
        config_manager.config.filter_sfx_mode = value
        config_manager.save_settings()
        self.append_log(f"SFX Mode: {value}\n")

    def open_advanced_settings(self):
        cfg = config_manager.config
        dialog = ctk.CTkToplevel(self)
        dialog.title("Advanced Settings")
        dialog_width, dialog_height = 480, 550
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dialog_width) // 2
        y = self.winfo_y() + (self.winfo_height() - dialog_height) // 2
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "assets", "favicon.ico",
        )
        if os.path.exists(icon_path):
            try:
                dialog.iconbitmap(icon_path)
            except Exception:
                pass
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_columnconfigure(1, weight=1)

        entries = {}

        def field(label, value, row, column, allow_decimal=True):
            frame = ctk.CTkFrame(dialog, fg_color="transparent")
            frame.grid(row=row, column=column, padx=12, pady=4, sticky="ew")
            frame.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                frame, text=label, font=("Terminal", 9, "bold"),
                text_color=COLOR_GRAY, anchor="w",
            ).grid(row=0, column=0, sticky="w", pady=(0, 2))
            entry = ctk.CTkEntry(
                frame, font=("Consolas", 10), fg_color=COLOR_WIDGET,
                text_color=COLOR_WHITE, border_width=0, corner_radius=6, height=26,
            )
            entry.insert(0, str(value))
            validate = dialog.register(
                lambda proposed: not proposed
                or (proposed.count(".") <= 1 and proposed.replace(".", "", 1).isdigit())
                if allow_decimal else (not proposed or proposed.isdigit())
            )
            entry._entry.configure(validate="key", validatecommand=(validate, "%P"))
            entry.grid(row=1, column=0, sticky="ew")
            return entry

        ctk.CTkLabel(dialog, text="OUTPUT", font=("Terminal", 10, "bold"), text_color=COLOR_WHITE).grid(
            row=0, column=0, columnspan=2, padx=12, pady=(12, 2), sticky="w"
        )
        ctk.CTkLabel(dialog, text="EXPORT FORMAT", font=("Terminal", 9, "bold"), text_color=COLOR_GRAY).grid(
            row=1, column=0, padx=12, pady=(2, 2), sticky="w"
        )
        export_format = RetroOptionMenu(
            dialog, values=config.TWEAKABLE_PARAMS["export_format"]["options"],
            font=("Consolas", 10), height=26,
        )
        export_format.set(cfg.export_format)
        export_format.grid(row=2, column=0, columnspan=2, padx=12, pady=(0, 8), sticky="ew")
        ctk.CTkLabel(
            dialog,
            text="pdf: PDF output. auto: CBZ for CBZ, ZIP, CBR, or RAR input. "
                 "cbz: always CBZ. none: keep individual PNG pages.",
            font=("Terminal", 8), text_color=COLOR_GRAY, justify="left",
            wraplength=440, anchor="w",
        ).grid(row=3, column=0, columnspan=2, padx=12, pady=(0, 6), sticky="w")

        ctk.CTkLabel(dialog, text="REQUESTS", font=("Terminal", 10, "bold"), text_color=COLOR_WHITE).grid(
            row=4, column=0, columnspan=2, padx=12, pady=(4, 2), sticky="w"
        )
        entries["min_request_delay"] = field("MINIMUM REQUEST DELAY (SECONDS)", cfg.min_request_delay, 5, 0)

        ctk.CTkLabel(dialog, text="MOSAIC CROP", font=("Terminal", 10, "bold"), text_color=COLOR_WHITE).grid(
            row=6, column=0, columnspan=2, padx=12, pady=(4, 2), sticky="w"
        )
        entries["pad_x_ratio"] = field("HORIZONTAL PADDING", cfg.pad_x_ratio, 7, 0)
        entries["pad_y_ratio"] = field("VERTICAL PADDING", cfg.pad_y_ratio, 7, 1)
        entries["min_pad"] = field("MINIMUM PADDING (PX)", cfg.min_pad, 8, 0, allow_decimal=False)
        entries["skala_potongan_mosaik"] = field("CROP SCALE", cfg.skala_potongan_mosaik, 8, 1)

        ctk.CTkLabel(dialog, text="RENDERING", font=("Terminal", 10, "bold"), text_color=COLOR_WHITE).grid(
            row=9, column=0, columnspan=2, padx=12, pady=(4, 2), sticky="w"
        )
        entries["mask_margin_ratio"] = field("MASK MARGIN RATIO", cfg.mask_margin_ratio, 10, 0)
        patch_flat_boxes = tk.BooleanVar(value=cfg.pakai_patch_untuk_box_gepeng)
        ctk.CTkCheckBox(
            dialog, text="Patch flat boxes", variable=patch_flat_boxes,
            font=("Terminal", 10), text_color=COLOR_WHITE,
        ).grid(row=10, column=1, padx=12, pady=(20, 0), sticky="w")
        validation_error = ctk.CTkLabel(
            dialog, text="", font=("Terminal", 9), text_color=COLOR_RED,
            wraplength=440, justify="left", anchor="w",
        )
        validation_error.grid(row=11, column=0, columnspan=2, padx=12, pady=(8, 0), sticky="ew")
        validation_error.grid_remove()

        def show_validation_error(message):
            validation_error.configure(text=message)
            validation_error.grid()
            dialog.geometry(f"{dialog_width}x580+{x}+{y - 15}")

        def save_and_close():
            numeric_fields = {
                "min_request_delay": float,
                "pad_x_ratio": float,
                "pad_y_ratio": float,
                "min_pad": int,
                "skala_potongan_mosaik": float,
                "mask_margin_ratio": float,
            }
            values = {}
            for attr, convert in numeric_fields.items():
                meta = next(item for item in config.TWEAKABLE_PARAMS.values() if item["attr"] == attr)
                try:
                    value = convert(entries[attr].get().strip())
                except ValueError:
                    show_validation_error(f"{attr.replace('_', ' ').title()} must be a number.")
                    return
                if convert is float and not math.isfinite(value):
                    show_validation_error(f"{attr.replace('_', ' ').title()} must be a finite number.")
                    return
                if "min" in meta and value < meta["min"]:
                    show_validation_error(f"{attr.replace('_', ' ').title()} must be at least {meta['min']}.")
                    return
                if "max" in meta and value > meta["max"]:
                    show_validation_error(f"{attr.replace('_', ' ').title()} must be at most {meta['max']}.")
                    return
                values[attr] = value

            original_values = {attr: getattr(cfg, attr) for attr in values}
            original_export_format = cfg.export_format
            original_patch_flat_boxes = cfg.pakai_patch_untuk_box_gepeng
            for attr, value in values.items():
                setattr(cfg, attr, value)
            cfg.export_format = export_format.get()
            cfg.pakai_patch_untuk_box_gepeng = patch_flat_boxes.get()
            if not config_manager.save_settings():
                for attr, value in original_values.items():
                    setattr(cfg, attr, value)
                cfg.export_format = original_export_format
                cfg.pakai_patch_untuk_box_gepeng = original_patch_flat_boxes
                show_validation_error("Could not save settings. Check the application data folder.")
                return
            self.append_log("Advanced settings saved.\n")
            dialog.destroy()

        ctk.CTkButton(
            dialog, text="SAVE SETTINGS", width=140, height=28, font=("Consolas", 10, "bold"),
            fg_color=COLOR_PINK, hover_color="#be185d",
            command=save_and_close,
        ).grid(row=12, column=0, columnspan=2, pady=(8, 12))
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

    def load_yolo_model(self):
        try:
            base_model_path, _ = os.path.splitext(config.MODEL_YOLO)
            if not os.path.exists(config.MODEL_YOLO) and not os.path.exists(base_model_path + ".dat"):
                self.set_status('YOLO Missing!', COLOR_RED)
                self.append_log("[!] YOLO model file not found in assets!\n")
                return

            self.yolo_model = YOLOONNX(config.MODEL_YOLO)
            self.set_status('Ready', COLOR_GREEN)
        except Exception as e:
            self.set_status('Error loading YOLO', COLOR_RED)
            self.append_log(f"[!] Error loading YOLO model: {e}\n")
        finally:
            self.yolo_loading_done = True

    def _get_initial_dir(self):
        last_dir = config_manager.config.last_opened_dir
        if last_dir and os.path.exists(last_dir):
            return last_dir
        downloads_dir = os.path.expanduser('~/Downloads')
        if os.path.exists(downloads_dir):
            return downloads_dir
        return os.path.expanduser('~')

    def open_file_selector(self, select_mode):
        initial_dir = self._get_initial_dir()
        if select_mode == 'folder':
            selected_path = filedialog.askdirectory(
                title="Select Source Folder",
                initialdir=initial_dir
            )
        else:
            exts = ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.pdf", "*.zip", "*.cbz", "*.rar", "*.cbr")
            filetypes = [
                ("Manga Images/Archives/PDF", " ".join(exts)),
                ("All Files", "*.*")
            ]
            selected_path = filedialog.askopenfilename(
                title="Select Source File",
                initialdir=initial_dir,
                filetypes=filetypes
            )

        if selected_path:
            selected_path = selected_path.replace('\\', '/')
            parent_dir = os.path.dirname(selected_path) if os.path.isfile(selected_path) else selected_path
            config_manager.config.last_opened_dir = parent_dir
            config_manager.save_settings()

            self.path_entry.configure(state="normal")
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, selected_path)
            self.path_entry.configure(state="readonly")

            self.append_log(f"Selected source: {selected_path}\n")

    def handle_file_drop(self, event):
        if not event.data:
            return

        try:
            paths = self.tk.splitlist(event.data)
            if not paths:
                return
            path = paths[0]
        except Exception:
            path = event.data
            if path.startswith('{') and path.endswith('}'):
                path = path[1:-1]
            if ' {' in path or '} {' in path:
                import re
                matches = re.findall(r'\{([^}]+)\}|(\S+)', path)
                paths = [m[0] if m[0] else m[1] for m in matches]
                if paths:
                    path = paths[0]

        path = path.replace('\\', '/').strip()

        if os.path.exists(path):
            self.path_entry.configure(state="normal")
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, path)
            self.path_entry.configure(state="readonly")

            self.append_log(f"Dropped source: {path}\n")

    def open_output_folder(self):
        path = self.path_entry.get().strip()
        if not path:
            self.append_log("[!] Please select a source path first.\n")
            return

        if os.path.isfile(path):
            parent = os.path.dirname(path)
        else:
            parent = path

        lang = config_manager.config.target_language or "Indonesian"
        lang_code = config.LANG_CODES.get(lang.lower(), lang[:2].lower()).upper()

        target_dir = os.path.join(parent, lang_code)
        if os.path.exists(target_dir):
            dir_to_open = target_dir
        else:
            dir_to_open = parent

        if os.path.exists(dir_to_open):
            self.append_log(f"Opening folder: {dir_to_open}\n")
            try:
                os.startfile(os.path.abspath(dir_to_open))
            except Exception as e:
                webbrowser.open(dir_to_open)
        else:
            self.append_log(f"[!] Folder does not exist: {dir_to_open}\n")

    def show_info_popup(self):
        InfoDialog(self)

    def append_log(self, text):
        self.log_queue.put(text)

    def set_status(self, text, color):
        self.after(0, lambda: self._set_status_raw(text, color))

    def _set_status_raw(self, text, color):
        if hasattr(self, 'lbl_status'):
            self.lbl_status.configure(text=text, text_color=color)

    def start_translation(self):
        if self.translating:
            self.cancel_translation()
            return

        input_path = self.path_entry.get().strip()
        if not input_path:
            self.append_log("[!] Please select a file or folder first.\n")
            return

        if self.yolo_model is None:
            self.append_log("[!] Please wait for the YOLO model to finish loading.\n")
            return

        self.translating = True
        config_manager.config.cancel_translation = False
        self.translate_btn.configure(text="Cancel", fg_color="#dc2626", hover_color="#b91c1c")

        threading.Thread(target=self.run_translation_task, args=(input_path,), daemon=True).start()

    def cancel_translation(self):
        if not self.translating:
            return
        self.append_log("\n[!] Cancelling translation, please wait...\n")
        config_manager.config.cancel_translation = True
        self.translate_btn.configure(text="Cancelling...", fg_color="#555555", state="disabled")

    def run_translation_task(self, input_path):
        try:
            self.set_status('Translating...', COLOR_ORANGE)

            provider_code = config_manager.config.llm_provider
            api_key, model_name = config_manager.config.get_provider_config(provider_code)

            extra = {}
            if provider_code == 'custom':
                extra['base_url'] = config_manager.config.custom_base_url

            provider = create_provider(provider_code, api_key=api_key, model_name=model_name, **extra)
            target_lang = config_manager.config.target_language or "Indonesian"

            start_time = time.time()

            if os.path.isdir(input_path):
                process_folder(input_path, self.yolo_model, provider=provider, target_language=target_lang)
            elif os.path.exists(input_path):
                if input_path.lower().endswith(".pdf"):
                    process_pdf(input_path, self.yolo_model, provider=provider, target_language=target_lang)
                elif input_path.lower().endswith(('.zip', '.cbz', '.rar', '.cbr')):
                    process_archive(input_path, self.yolo_model, provider=provider, target_language=target_lang)
                elif input_path.lower().endswith(config.SUPPORTED_IMAGE_EXTENSIONS):
                    process_single_image(input_path, self.yolo_model, provider=provider, target_language=target_lang)
                else:
                    self.append_log("[!] Unsupported file format.\n")
            else:
                self.append_log("[!] Selected path does not exist.\n")

            elapsed = time.time() - start_time
            if config_manager.config.cancel_translation:
                self.append_log(f"\n[Timer] Translation cancelled after {elapsed:.1f}s.\n")
            else:
                self.append_log(f"\n[Timer] Translation completed in {elapsed:.1f}s!\n")

        except Exception as e:
            self.append_log(f"[!] Error during translation: {e}\n")

        finally:
            self.translating = False
            self.after(0, self.reset_translate_button)

    def reset_translate_button(self):
        self.translate_btn.configure(text="Translate Now", fg_color=COLOR_PINK, hover_color="#be185d", state="normal")
        self.set_status('Ready', COLOR_GREEN)

    def on_closing(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        self.destroy()


def main():
    ctk.set_appearance_mode("dark")
    app = CYPYWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
