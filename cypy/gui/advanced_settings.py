import os
import sys
import math
import tkinter as tk
import customtkinter as ctk

import cypy.core.config as config
from cypy.core.config import config_manager
from cypy.core.services.font_service import get_system_font_map
from cypy.gui.widgets import RetroOptionMenu
from cypy.gui.theme import (
    COLOR_BG, COLOR_CARD, COLOR_WIDGET, COLOR_BORDER,
    COLOR_PINK, COLOR_WHITE, COLOR_GRAY, COLOR_DARK_BTN,
    COLOR_DARK_BTN_HOVER, COLOR_RED,
)


class AdvancedSettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)

        self.withdraw()

        self.title("Advanced Settings")
        self.configure(fg_color=COLOR_BG)
        self.resizable(False, False)

        # Modal Window setup
        self.transient(parent)
        self.grab_set()

        # Geometry & centering
        dialog_width, dialog_height = 490, 580
        parent.update_idletasks()
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # --- Icon Setup ---
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets')
        self.icon_path = os.path.join(assets_dir, 'favicon.ico')

        def force_icon():
            try:
                if self.icon_path and os.path.exists(self.icon_path):
                    self.iconbitmap(self.icon_path)
            except Exception:
                pass

        force_icon()
        self.after(200, force_icon)

        cfg = config_manager.config
        entries = {}

        # Main Frame Container
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=12, pady=12)

        def create_field(parent_card, label, value, row, column, allow_decimal=True):
            frame = ctk.CTkFrame(parent_card, fg_color="transparent")
            frame.grid(row=row, column=column, padx=8, pady=4, sticky="ew")
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
            validate = self.register(
                lambda proposed: not proposed
                or (proposed.count(".") <= 1 and proposed.replace(".", "", 1).isdigit())
                if allow_decimal else (not proposed or proposed.isdigit())
            )
            entry._entry.configure(validate="key", validatecommand=(validate, "%P"))
            entry.grid(row=1, column=0, sticky="ew")
            return entry

        # --- SECTION 0: TOP ROW (MANGA FONT & OUTPUT FORMAT SIDE-BY-SIDE) ---
        top_row = ctk.CTkFrame(main_frame, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 8))
        top_row.grid_columnconfigure(0, weight=1)
        top_row.grid_columnconfigure(1, weight=1)

        # LEFT PANEL: MANGA FONT
        card_font = ctk.CTkFrame(top_row, fg_color=COLOR_CARD, corner_radius=8)
        card_font.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        card_font.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card_font, text="MANGA FONT", font=("Terminal", 10, "bold"), text_color=COLOR_WHITE
        ).grid(row=0, column=0, padx=10, pady=(8, 2), sticky="w")

        # System Font Auto-Detection
        system_font_map = get_system_font_map()
        font_display_names = ["[Default] Komika Axis.ttf"] + sorted(system_font_map.keys())

        current_display = "[Default] Komika Axis.ttf"
        if cfg.custom_font_path:
            for name, path in system_font_map.items():
                if os.path.abspath(path).lower() == os.path.abspath(cfg.custom_font_path).lower():
                    current_display = name
                    break

        font_row = ctk.CTkFrame(card_font, fg_color="transparent")
        font_row.grid(row=1, column=0, padx=10, pady=(0, 4), sticky="ew")
        font_row.grid_columnconfigure(0, weight=1)
        font_row.grid_columnconfigure(1, weight=0)

        font_spinner = RetroOptionMenu(
            font_row, values=font_display_names,
            font=("Consolas", 10), height=26,
        )
        font_spinner.set(current_display)
        font_spinner.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        def reset_font():
            font_spinner.set("[Default] Komika Axis.ttf")

        ctk.CTkButton(
            font_row, text="RESET", width=48, height=26,
            font=("Consolas", 8, "bold"), fg_color=COLOR_DARK_BTN,
            hover_color=COLOR_DARK_BTN_HOVER, corner_radius=6,
            command=reset_font
        ).grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            card_font,
            text="Font for Latin text. Default = Komika Axis.ttf.",
            font=("Terminal", 8), text_color=COLOR_GRAY, justify="left", wraplength=210, anchor="w",
        ).grid(row=2, column=0, padx=10, pady=(0, 8), sticky="w")

        # RIGHT PANEL: OUTPUT FORMAT
        card_output = ctk.CTkFrame(top_row, fg_color=COLOR_CARD, corner_radius=8)
        card_output.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        card_output.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card_output, text="OUTPUT FORMAT", font=("Terminal", 10, "bold"), text_color=COLOR_WHITE
        ).grid(row=0, column=0, padx=10, pady=(8, 2), sticky="w")

        export_format = RetroOptionMenu(
            card_output, values=config.TWEAKABLE_PARAMS["export_format"]["options"],
            font=("Consolas", 10), height=26,
        )
        export_format.set(cfg.export_format)
        export_format.grid(row=1, column=0, padx=10, pady=(0, 4), sticky="ew")

        ctk.CTkLabel(
            card_output,
            text="pdf: PDF output. auto: match format. cbz: CBZ. none: PNGs.",
            font=("Terminal", 8), text_color=COLOR_GRAY, justify="left", wraplength=210, anchor="w",
        ).grid(row=2, column=0, padx=10, pady=(0, 8), sticky="w")

        # --- SECTION 2: REQUESTS CARD ---
        card_requests = ctk.CTkFrame(main_frame, fg_color=COLOR_CARD, corner_radius=8)
        card_requests.pack(fill="x", pady=(0, 8))
        card_requests.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card_requests, text="REQUESTS", font=("Terminal", 10, "bold"), text_color=COLOR_WHITE
        ).grid(row=0, column=0, padx=10, pady=(8, 2), sticky="w")

        entries["min_request_delay"] = create_field(
            card_requests, "MINIMUM REQUEST DELAY (SECONDS)", cfg.min_request_delay, 1, 0
        )

        # --- SECTION 3: MOSAIC CROP CARD ---
        card_crop = ctk.CTkFrame(main_frame, fg_color=COLOR_CARD, corner_radius=8)
        card_crop.pack(fill="x", pady=(0, 8))
        card_crop.grid_columnconfigure(0, weight=1)
        card_crop.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card_crop, text="MOSAIC CROP", font=("Terminal", 10, "bold"), text_color=COLOR_WHITE
        ).grid(row=0, column=0, columnspan=2, padx=10, pady=(8, 2), sticky="w")

        entries["pad_x_ratio"] = create_field(card_crop, "HORIZONTAL PADDING", cfg.pad_x_ratio, 1, 0)
        entries["pad_y_ratio"] = create_field(card_crop, "VERTICAL PADDING", cfg.pad_y_ratio, 1, 1)
        entries["min_pad"] = create_field(card_crop, "MINIMUM PADDING (PX)", cfg.min_pad, 2, 0, allow_decimal=False)
        entries["skala_potongan_mosaik"] = create_field(card_crop, "CROP SCALE", cfg.skala_potongan_mosaik, 2, 1)

        # --- SECTION 4: RENDERING CARD ---
        card_rendering = ctk.CTkFrame(main_frame, fg_color=COLOR_CARD, corner_radius=8)
        card_rendering.pack(fill="x", pady=(0, 8))
        card_rendering.grid_columnconfigure(0, weight=1)
        card_rendering.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card_rendering, text="RENDERING", font=("Terminal", 10, "bold"), text_color=COLOR_WHITE
        ).grid(row=0, column=0, columnspan=2, padx=10, pady=(8, 2), sticky="w")

        entries["mask_margin_ratio"] = create_field(card_rendering, "MASK MARGIN RATIO", cfg.mask_margin_ratio, 1, 0)
        
        cb_frame = ctk.CTkFrame(card_rendering, fg_color="transparent")
        cb_frame.grid(row=1, column=1, padx=8, pady=4, sticky="ew")
        cb_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            cb_frame, text=" ", font=("Terminal", 9, "bold")
        ).grid(row=0, column=0, sticky="w", pady=(0, 2))

        patch_flat_boxes = tk.BooleanVar(value=cfg.pakai_patch_untuk_box_gepeng)
        chk = ctk.CTkCheckBox(
            cb_frame, text="Patch flat boxes", variable=patch_flat_boxes,
            font=("Consolas", 10), text_color=COLOR_WHITE,
            fg_color=COLOR_PINK, hover_color="#be185d",
            checkbox_width=18, checkbox_height=18, corner_radius=4, height=26
        )
        chk.grid(row=1, column=0, sticky="w")

        # Validation error message label
        validation_error = ctk.CTkLabel(
            main_frame, text="", font=("Terminal", 9), text_color=COLOR_RED,
            wraplength=440, justify="left", anchor="w",
        )
        validation_error.pack(fill="x", pady=(2, 4))
        validation_error.pack_forget()

        def show_validation_error(message):
            validation_error.configure(text=message)
            validation_error.pack(fill="x", pady=(2, 4))

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
            original_custom_font_path = cfg.custom_font_path
            for attr, value in values.items():
                setattr(cfg, attr, value)
            cfg.export_format = export_format.get()
            sel_font = font_spinner.get()
            if sel_font == "[Default] Komika Axis.ttf" or sel_font not in system_font_map:
                cfg.custom_font_path = ""
            else:
                cfg.custom_font_path = system_font_map[sel_font]
            if not config_manager.save_settings():
                for attr, value in original_values.items():
                    setattr(cfg, attr, value)
                cfg.export_format = original_export_format
                cfg.pakai_patch_untuk_box_gepeng = original_patch_flat_boxes
                cfg.custom_font_path = original_custom_font_path
                show_validation_error("Could not save settings. Check the application data folder.")
                return

            if hasattr(parent, "append_log"):
                parent.append_log("Advanced settings saved.\n")
            self.destroy()

        ctk.CTkButton(
            main_frame, text="SAVE SETTINGS", width=220, height=34,
            font=("Consolas", 11, "bold"), text_color=COLOR_WHITE,
            fg_color=COLOR_PINK, hover_color="#be185d", corner_radius=6,
            command=save_and_close,
        ).pack(pady=(6, 8))

        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self.after(100, self.deiconify)
