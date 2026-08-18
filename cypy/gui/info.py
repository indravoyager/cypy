import os
import sys
import webbrowser
import customtkinter as ctk
from cypy.core.version import APP_VER
from cypy.gui.theme import (
    COLOR_BG, COLOR_CARD, COLOR_WIDGET, COLOR_BORDER,
    COLOR_PINK, COLOR_WHITE,
)

class InfoDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        
        self.withdraw()
        
        self.title("CYPY - Info & Support")
        self.geometry("300x240")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)
        
        # Modal Window
        self.transient(parent)
        self.grab_set()
        
        # Center the dialog
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        x = parent_x + (parent_width // 2) - 150
        y = parent_y + (parent_height // 2) - 120
        self.geometry(f"+{x}+{y}")
        
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
        
        # Title (Matching main window header style)
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(pady=(12, 2))

        lbl_logo = ctk.CTkLabel(
            title_frame, text="◇ cypy ◇",
            font=("Fixedsys", 16), text_color=COLOR_PINK
        )
        lbl_logo.pack(side="left")

        lbl_desc = ctk.CTkLabel(
            title_frame, text="Manga Translator",
            font=("Terminal", 10), text_color="#aaaaaa"
        )
        lbl_desc.pack(side="left", padx=(6, 0))
        
        # Version and contributors (separated with spacing for better readability)
        lbl_version = ctk.CTkLabel(
            self, text=f"Version {APP_VER}", 
            font=("Terminal", 10), text_color="#aaaaaa",
            height=14
        )
        lbl_version.pack(pady=(2, 6))

        lbl_contrib_title = ctk.CTkLabel(
            self, text="Developed by:", 
            font=("Terminal", 10), text_color="#aaaaaa",
            height=14
        )
        lbl_contrib_title.pack(pady=(4, 3))

        lbl_contrib_list1 = ctk.CTkLabel(
            self, text="indravoyager, cyrene, SayMaven,", 
            font=("Terminal", 10), text_color="#aaaaaa",
            height=14
        )
        lbl_contrib_list1.pack(pady=2)

        lbl_contrib_list2 = ctk.CTkLabel(
            self, text="mitsuki31, Alisa-Mikhailovna, mbayue", 
            font=("Terminal", 10), text_color="#aaaaaa",
            height=14
        )
        lbl_contrib_list2.pack(pady=2)
        
        # Buttons Container (GitHub & Support side-by-side in one row)
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=25, pady=(12, 4))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        
        # GitHub Button
        btn_github = ctk.CTkButton(
            btn_frame, text="GitHub Repo",
            font=("Consolas", 10, "bold"), text_color="#00ff00",
            fg_color=COLOR_CARD, hover_color=COLOR_WIDGET, border_width=0,
            corner_radius=6, height=28,
            command=lambda: webbrowser.open("https://github.com/indravoyager/cypy")
        )
        btn_github.grid(row=0, column=0, padx=(0, 4), sticky="ew")
        
        # Trakteer Button
        btn_trakteer = ctk.CTkButton(
            btn_frame, text="Support Dev",
            font=("Consolas", 10, "bold"), text_color="#e69933",
            fg_color=COLOR_CARD, hover_color=COLOR_WIDGET, border_width=0,
            corner_radius=6, height=28,
            command=lambda: webbrowser.open("https://trakteer.id/indravoyager")
        )
        btn_trakteer.grid(row=0, column=1, padx=(4, 0), sticky="ew")
        
        # Close Button
        btn_close = ctk.CTkButton(
            self, text="CLOSE",
            font=("Consolas", 10, "bold"), text_color=COLOR_WHITE,
            fg_color="#2b2b2b", hover_color="#3a3a3a", border_width=0,
            corner_radius=6, height=28,
            command=self.destroy
        )
        btn_close.pack(pady=(12, 8))
        
        self.after(100, self.deiconify)
