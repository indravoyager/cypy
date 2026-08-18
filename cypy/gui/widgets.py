import sys
import customtkinter as ctk

from cypy.gui.theme import (
    COLOR_BG, COLOR_CARD, COLOR_WIDGET, COLOR_BORDER,
    COLOR_PINK, COLOR_WHITE, COLOR_GRAY, COLOR_DARK_BTN, COLOR_DARK_BTN_HOVER,
)

class QueueWriteDescriptor:
    def __init__(self, queue_put, original_stream=None):
        self.queue_put = queue_put
        self.original_stream = original_stream
    def write(self, string):
        self.queue_put(string)
        if self.original_stream:
            try:
                self.original_stream.write(string)
                self.original_stream.flush()
            except Exception:
                pass
    def flush(self):
        if self.original_stream:
            try:
                self.original_stream.flush()
            except Exception:
                pass

class RetroOptionMenu(ctk.CTkFrame):
    def __init__(self, master, values, command=None, height=26, font=("Consolas", 10), max_visible=6, **kwargs):
        # Frame container with border to align perfectly with CTkEntry
        super().__init__(master, fg_color=COLOR_WIDGET, border_width=0, corner_radius=6, height=height)
        self.grid_propagate(False) # Keep fixed height of 26
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)
        
        self.values = values
        self.command = command
        self.current_value = values[0] if values else ""
        self.font = font
        self.max_visible = max_visible
        self.popup = None
        self._click_bind = None
        
        # Selected Value Label (Left aligned, vertically offset by 1px to prevent covering borders)
        self.lbl_val = ctk.CTkLabel(
            self, text=self.current_value, font=self.font, text_color=COLOR_WHITE, fg_color="transparent", anchor="w"
        )
        self.lbl_val.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=1)
        
        # Arrow Label (Right aligned, vertically offset by 1px to prevent covering borders)
        self.lbl_arrow = ctk.CTkLabel(
            self, text="▼", font=("Consolas", 9), text_color=COLOR_WHITE, fg_color="transparent"
        )
        self.lbl_arrow.grid(row=0, column=1, sticky="ns", padx=(0, 10), pady=1)
        
        # Bind hover and click events to frame and its children
        for widget in (self, self.lbl_val, self.lbl_arrow):
            widget.bind("<Enter>", self.on_enter)
            widget.bind("<Leave>", self.on_leave)
            widget.bind("<Button-1>", self.on_click)

    def on_enter(self, event=None):
        self.configure(fg_color=COLOR_DARK_BTN_HOVER)

    def on_leave(self, event=None):
        if not self.popup:
            self.configure(fg_color=COLOR_WIDGET)

    def on_click(self, event=None):
        self.toggle_popup()

    def set(self, value):
        self.current_value = value
        self.lbl_val.configure(text=value)

    def get(self):
        return self.current_value

    def toggle_popup(self):
        if self.popup and self.popup.winfo_exists():
            self.close_popup()
        else:
            self.open_popup()

    def open_popup(self):
        # Flip arrow up
        self.lbl_arrow.configure(text="▲")
        self.configure(fg_color=COLOR_DARK_BTN_HOVER)
        
        # Create custom borderless dropdown window
        self.popup = ctk.CTkToplevel(self)
        self.popup.withdraw()
        self.popup.overrideredirect(True)
        self.popup.configure(fg_color=COLOR_BORDER)
        
        self.popup.transient(self.winfo_toplevel())

        num_visible = min(len(self.values), self.max_visible)

        if len(self.values) > self.max_visible:
            container = ctk.CTkScrollableFrame(
                self.popup, fg_color=COLOR_WIDGET, corner_radius=0,
                scrollbar_button_color=COLOR_DARK_BTN,
                scrollbar_button_hover_color=COLOR_DARK_BTN_HOVER,
            )
            container.pack(padx=1, pady=1, fill="both", expand=True)
        else:
            container = ctk.CTkFrame(self.popup, fg_color=COLOR_WIDGET, corner_radius=0)
            container.pack(padx=1, pady=1, fill="both", expand=True)

        for val in self.values:
            btn_opt = ctk.CTkButton(
                container, text=f"  {val}", font=self.font, text_color=COLOR_WHITE,
                fg_color=COLOR_WIDGET, hover_color=COLOR_PINK, corner_radius=0, height=24,
                anchor="w", command=lambda v=val: self.select_value(v)
            )
            btn_opt.pack(fill="x", padx=1, pady=1)

        # Place popup exactly below the main dropdown field
        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        w = self.winfo_width()
        h = num_visible * 26 + 6
        
        self.popup.geometry(f"{w}x{h}+{x}+{y}")
        self.popup.deiconify()
        
        # Bind global mouse click outside popup to close it
        self._click_bind = self.winfo_toplevel().bind("<Button-1>", self.check_click_outside, add="+")
        self.popup.bind("<Escape>", lambda e: self.close_popup())

    def check_click_outside(self, event):
        if self.popup and self.popup.winfo_exists():
            x = event.x_root
            y = event.y_root
            
            px = self.popup.winfo_rootx()
            py = self.popup.winfo_rooty()
            pw = self.popup.winfo_width()
            ph = self.popup.winfo_height()
            
            # Close only if the click is outside popup boundaries
            if not (px <= x <= px + pw and py <= y <= py + ph):
                # If clicking on the dropdown frame itself, let on_click handle it
                bx = self.winfo_rootx()
                by = self.winfo_rooty()
                bw = self.winfo_width()
                bh = self.winfo_height()
                if bx <= x <= bx + bw and by <= y <= by + bh:
                    return
                self.close_popup()

    def select_value(self, value):
        self.set(value)
        self.close_popup()
        if self.command:
            self.command(value)

    def close_popup(self):
        if self.popup:
            try:
                self.popup.destroy()
            except Exception:
                pass
            self.popup = None
            
        if self._click_bind:
            try:
                self.winfo_toplevel().unbind("<Button-1>", self._click_bind)
            except Exception:
                pass
            self._click_bind = None
            
        self.lbl_arrow.configure(text="▼")
        self.configure(fg_color=COLOR_WIDGET)
