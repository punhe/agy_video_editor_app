#!/usr/bin/env python3
"""
app.py
AGY Short-Drama Studio v2.6 - Professional Desktop Video Suite
Features:
- Single & Batch Multi-Clip Processing
- Smart RAM & Concurrency Resource Allocation
- Auto X/Twitter Spicy Caption Generator (x-shortdrama-caption standard)
- AGY CLI Google Account Authentication Bridge
- Cross-platform for Windows & macOS (packages in requirements.txt, auto-installed by run_app.*)

UI: sidebar navigation, shared settings column, collapsible log drawer.
"""

import os
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

_missing = []
for _mod, _pkg in (("cv2", "opencv-python"), ("numpy", "numpy"), ("PIL", "Pillow")):
    try:
        __import__(_mod)
    except ImportError:
        _missing.append(_pkg)
if _missing:
    _launcher = "run_app.bat" if sys.platform == "win32" else "bash run_app.sh"
    print("Thiếu thư viện Python: " + ", ".join(_missing))
    print(f"Cách sửa: chạy app bằng '{_launcher}' (tự cài thư viện),")
    print("hoặc cài thủ công:  python3 -m pip install -r requirements.txt")
    sys.exit(1)

from core.agy_connector import find_agy_executable, test_agy_connection, launch_login_terminal
from core.notifier import send_notification, reveal_in_file_manager, open_media_file
from core.engine import VideoEditorEngine
from core.batch_manager import BatchManager, get_system_ram_info, calculate_smart_workers
from core.caption_generator import generate_captions_with_agy, save_captions_to_file

# -----------------------------------------------------------------
# Palette: neutral editing-suite dark + one "recording light" accent
# -----------------------------------------------------------------
C_SIDEBAR = "#0c0d0f"
C_BG = "#121315"
C_SURFACE = "#18191c"
C_SURFACE_2 = "#202125"
C_SURFACE_3 = "#2a2b30"
C_BORDER = "#2a2b30"
C_BORDER_STRONG = "#3a3b42"
C_TEXT = "#ececee"
C_TEXT_MUTED = "#a1a2aa"
C_TEXT_FAINT = "#74757d"
C_ACCENT = "#ff6a3d"
C_ACCENT_HOVER = "#ff8259"
C_ACCENT_PRESS = "#e85a2f"
C_ON_ACCENT = "#170a05"
C_ACCENT_SOFT = "#2e1c16"
C_SUCCESS = "#3ecf8e"
C_SUCCESS_SOFT = "#13281f"
C_WARNING = "#f5b544"
C_DANGER = "#ff6b6b"
C_DANGER_SOFT = "#2c1719"
C_CONSOLE_BG = "#0a0b0c"
C_CONSOLE_TEXT = "#b9c2cc"

VIDEO_TYPES = [("Video Files", "*.mp4;*.mov;*.mkv;*.avi;*.webm"), ("All Files", "*.*")]

MODES = [
    ("hook-and-polish", "Trọn gói tự động",
     "Hook 30s cao trào, nhịp zoom, sub tiếng Anh."),
    ("polish-existing", "Video đã cắt sẵn",
     "Giữ thời lượng, thêm nhịp, âm thanh, sub."),
    ("hook-only", "Chỉ cắt hook 30s",
     "Trích cao trào nhanh, giữ nguyên âm thanh."),
]
MODE_SHORT = {"hook-and-polish": "Trọn gói", "polish-existing": "Cắt sẵn", "hook-only": "Chỉ hook"}

STATUS_TAGS = {
    "Hoàn thành": "st_done",
    "Đang xử lý": "st_run",
    "Thất bại": "st_fail",
    "Lỗi": "st_fail",
    "Đã hủy": "st_cancel",
}


def _pick_family(candidates, fallback):
    try:
        available = set(tkfont.families())
    except Exception:
        return fallback
    for c in candidates:
        if c in available:
            return c
    return fallback


# -----------------------------------------------------------------
# Small custom widgets (pure Tk, no extra dependencies)
# -----------------------------------------------------------------
class FlatButton(tk.Label):
    """Label-based button with hover, press, disabled and keyboard focus."""

    VARIANTS = {
        "primary": dict(bg=C_ACCENT, fg=C_ON_ACCENT, hover=C_ACCENT_HOVER, press=C_ACCENT_PRESS, border=C_ACCENT),
        "secondary": dict(bg=C_SURFACE_2, fg=C_TEXT, hover=C_SURFACE_3, press=C_BORDER_STRONG, border=C_BORDER_STRONG),
        "ghost": dict(bg=None, fg=C_TEXT_MUTED, hover=C_SURFACE_2, press=C_SURFACE_3, border=None),
        "danger": dict(bg=C_DANGER_SOFT, fg=C_DANGER, hover="#3a1d20", press="#472226", border="#4a2427"),
        "success": dict(bg=C_SUCCESS_SOFT, fg=C_SUCCESS, hover="#183426", press="#1d3f2e", border="#1f4433"),
    }

    def __init__(self, parent, text, command=None, variant="secondary", font=None, padx=14, pady=7, **kw):
        self.v = dict(self.VARIANTS[variant])
        parent_bg = parent.cget("bg")
        if self.v["bg"] is None:
            self.v["bg"] = parent_bg
        if self.v["border"] is None:
            self.v["border"] = parent_bg
        self.command = command
        self.enabled = True
        self._hover = False
        super().__init__(parent, text=text, bg=self.v["bg"], fg=self.v["fg"], font=font,
                         padx=padx, pady=pady, cursor="hand2", takefocus=1,
                         highlightthickness=1, highlightbackground=self.v["border"],
                         highlightcolor=C_ACCENT, **kw)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<KeyPress-Return>", lambda e: self.invoke())
        self.bind("<KeyPress-space>", lambda e: self.invoke())

    def _paint(self, bg):
        self.config(bg=bg)

    def _on_enter(self, _):
        self._hover = True
        if self.enabled:
            self._paint(self.v["hover"])

    def _on_leave(self, _):
        self._hover = False
        if self.enabled:
            self._paint(self.v["bg"])

    def _on_press(self, _):
        if self.enabled:
            self._paint(self.v["press"])

    def _on_release(self, e):
        if not self.enabled:
            return
        inside = 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height()
        self._paint(self.v["hover"] if inside else self.v["bg"])
        if inside:
            self.invoke()

    def invoke(self):
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, enabled):
        self.enabled = enabled
        if enabled:
            self.config(fg=self.v["fg"], bg=self.v["hover"] if self._hover else self.v["bg"],
                        cursor="hand2", highlightbackground=self.v["border"])
        else:
            ghost = self.v["border"] == self.v["bg"] and self.v["fg"] == C_TEXT_MUTED
            dbg = self.v["bg"] if ghost else C_SURFACE_2
            self.config(fg=C_TEXT_FAINT, bg=dbg, cursor="arrow",
                        highlightbackground=dbg if ghost else C_BORDER)


class ChoiceCard(tk.Frame):
    """Radio choice rendered as a selectable card with a drawn indicator."""

    def __init__(self, parent, variable, value, title, desc, fonts):
        super().__init__(parent, bg=C_SURFACE, highlightthickness=1, highlightbackground=C_BORDER,
                         cursor="hand2", padx=12, pady=8, takefocus=1, highlightcolor=C_ACCENT)
        self.var, self.value = variable, value
        self.dot = tk.Canvas(self, width=16, height=16, bg=C_SURFACE, highlightthickness=0)
        self.dot.grid(row=0, column=0, sticky="n", pady=(2, 0), padx=(0, 10))
        self.lbl_title = tk.Label(self, text=title, font=fonts["bold"], bg=C_SURFACE, fg=C_TEXT, anchor="w")
        self.lbl_title.grid(row=0, column=1, sticky="w")
        self.lbl_desc = tk.Label(self, text=desc, font=fonts["small"], bg=C_SURFACE, fg=C_TEXT_MUTED,
                                 anchor="w", justify="left", wraplength=270)
        self.lbl_desc.grid(row=1, column=1, sticky="w", pady=(2, 0))
        self.columnconfigure(1, weight=1)
        for w in (self, self.dot, self.lbl_title, self.lbl_desc):
            w.bind("<Button-1>", lambda e: self.var.set(self.value))
            w.bind("<Enter>", lambda e: self._hover(True))
            w.bind("<Leave>", lambda e: self._hover(False))
        self.bind("<KeyPress-space>", lambda e: self.var.set(self.value))
        self.bind("<KeyPress-Return>", lambda e: self.var.set(self.value))
        self.var.trace_add("write", lambda *a: self.refresh())
        self.refresh()

    def _hover(self, on):
        if self.var.get() != self.value:
            self.config(highlightbackground=C_BORDER_STRONG if on else C_BORDER)

    def refresh(self):
        sel = self.var.get() == self.value
        bg = C_ACCENT_SOFT if sel else C_SURFACE
        for w in (self, self.dot, self.lbl_title, self.lbl_desc):
            w.config(bg=bg)
        self.config(highlightbackground=C_ACCENT if sel else C_BORDER)
        self.dot.delete("all")
        if sel:
            self.dot.create_oval(1, 1, 15, 15, outline=C_ACCENT, width=2)
            self.dot.create_oval(5, 5, 11, 11, fill=C_ACCENT, outline=C_ACCENT)
        else:
            self.dot.create_oval(1, 1, 15, 15, outline=C_BORDER_STRONG, width=2)


class CheckRow(tk.Frame):
    """Checkbox with a drawn box and a two-line label."""

    def __init__(self, parent, variable, title, desc, fonts, bg=C_SURFACE):
        super().__init__(parent, bg=bg, cursor="hand2", takefocus=1, highlightthickness=1,
                         highlightbackground=bg, highlightcolor=C_ACCENT)
        self.var = variable
        self.box = tk.Canvas(self, width=18, height=18, bg=bg, highlightthickness=0)
        self.box.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 10), pady=(1, 0))
        t = tk.Label(self, text=title, font=fonts["bold"], bg=bg, fg=C_TEXT, anchor="w")
        t.grid(row=0, column=1, sticky="w")
        d = tk.Label(self, text=desc, font=fonts["small"], bg=bg, fg=C_TEXT_MUTED, anchor="w",
                     justify="left", wraplength=240)
        d.grid(row=1, column=1, sticky="w")
        for w in (self, self.box, t, d):
            w.bind("<Button-1>", lambda e: self.toggle())
        self.bind("<KeyPress-space>", lambda e: self.toggle())
        self.var.trace_add("write", lambda *a: self.refresh())
        self.refresh()

    def toggle(self):
        self.var.set(not self.var.get())

    def refresh(self):
        self.box.delete("all")
        if self.var.get():
            self.box.create_rectangle(1, 1, 17, 17, fill=C_ACCENT, outline=C_ACCENT)
            self.box.create_line(5, 9, 8, 12, 13, 5, fill=C_ON_ACCENT, width=2, capstyle="round",
                                 joinstyle="round")
        else:
            self.box.create_rectangle(1, 1, 17, 17, outline=C_BORDER_STRONG, width=2)


class Segmented(tk.Frame):
    """Segmented control bound to a StringVar."""

    def __init__(self, parent, variable, options, fonts):
        super().__init__(parent, bg=C_SURFACE_2, highlightthickness=1, highlightbackground=C_BORDER)
        self.var = variable
        self.items = []
        for i, (value, text) in enumerate(options):
            lbl = tk.Label(self, text=text, font=fonts["bold"], padx=10, pady=6, cursor="hand2",
                           takefocus=1, highlightthickness=1, highlightcolor=C_ACCENT,
                           highlightbackground=C_SURFACE_2)
            lbl.grid(row=0, column=i, sticky="nsew", padx=2, pady=2)
            self.columnconfigure(i, weight=1, uniform="seg")
            lbl.bind("<Button-1>", lambda e, v=value: self.var.set(v))
            lbl.bind("<KeyPress-space>", lambda e, v=value: self.var.set(v))
            self.items.append((value, lbl))
        self.var.trace_add("write", lambda *a: self.refresh())
        self.refresh()

    def refresh(self):
        for value, lbl in self.items:
            sel = self.var.get() == value
            bg = C_SURFACE_3 if sel else C_SURFACE_2
            lbl.config(bg=bg, fg=C_TEXT if sel else C_TEXT_MUTED, highlightbackground=bg)


class ThinProgress(tk.Canvas):
    def __init__(self, parent, variable, height=4):
        super().__init__(parent, height=height, bg=C_SURFACE_3, highlightthickness=0)
        self.var = variable
        self.bind("<Configure>", lambda e: self.redraw())
        self.var.trace_add("write", lambda *a: self.redraw())

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        try:
            pct = max(0, min(100, int(self.var.get())))
        except Exception:
            pct = 0
        if pct > 0:
            self.create_rectangle(0, 0, w * pct / 100, int(self.cget("height")),
                                  fill=C_SUCCESS if pct >= 100 else C_ACCENT, width=0)


# -----------------------------------------------------------------
# Main application
# -----------------------------------------------------------------
class AGYShortDramaStudio(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("AGY Short-Drama Studio")
        self.geometry("1200x800")
        self.minsize(1060, 700)
        self.configure(bg=C_BG)
        if sys.platform == "win32":
            try:
                self.state("zoomed")
            except Exception:
                pass

        self.setup_fonts()

        # Single Job Variables
        self.input_file_var = tk.StringVar(value="")
        self.output_dir_var = tk.StringVar(value="")
        self.mode_var = tk.StringVar(value="hook-and-polish")
        self.sub_mode_var = tk.StringVar(value="en")
        self.auto_caption_var = tk.BooleanVar(value=True)

        # Batch Variables
        self.concurrency_mode_var = tk.StringVar(value="auto")
        self.manual_workers_var = tk.IntVar(value=2)
        self.batch_manager = None
        self.is_batch_running = False
        self.is_single_running = False

        # Status & AGY Variables
        self.agy_status_var = tk.StringVar(value="Đang kiểm tra...")
        self.progress_var = tk.IntVar(value=0)
        self.status_msg_var = tk.StringVar(value="Sẵn sàng.")

        self.last_output_file = ""
        self.current_captions = []
        self.current_page = None
        self.log_visible = False
        self._spec_job = None
        self._toast_job = None

        self.setup_ttk_styles()
        self.build_ui()

        # Initialize Batch Manager
        self.batch_manager = BatchManager(
            on_job_update=self.on_batch_job_update,
            on_batch_complete=self.on_batch_complete_handler,
            log_callback=self.log
        )

        self.show_page("batch")
        self.refresh_queue_ui()

        # Background AGY test & RAM load
        threading.Thread(target=self.init_system_diagnostics_async, daemon=True).start()

    # -------------------------------------------------------------
    # THEME
    # -------------------------------------------------------------
    def setup_fonts(self):
        if sys.platform == "win32":
            display = _pick_family(["Segoe UI Variable Display", "Segoe UI"], "Segoe UI")
            text = _pick_family(["Segoe UI Variable Text", "Segoe UI"], "Segoe UI")
            mono = _pick_family(["Cascadia Mono", "Cascadia Code", "Consolas"], "Consolas")
        elif sys.platform == "darwin":
            display = _pick_family(["SF Pro Display", "Helvetica Neue"], "Helvetica")
            text = _pick_family(["SF Pro Text", "Helvetica Neue"], "Helvetica")
            mono = _pick_family(["SF Mono", "Menlo"], "Menlo")
        else:
            display = text = _pick_family(["Inter", "Cantarell", "DejaVu Sans"], "TkDefaultFont")
            mono = _pick_family(["JetBrains Mono", "DejaVu Sans Mono"], "TkFixedFont")
        self.F = {
            "brand": (display, 13, "bold"),
            "h1": (display, 19, "bold"),
            "h2": (text, 11, "bold"),
            "body": (text, 10),
            "bold": (text, 10, "bold"),
            "small": (text, 9),
            "label": (text, 9, "bold"),
            "nav": (text, 10),
            "nav_sel": (text, 10, "bold"),
            "cta": (text, 11, "bold"),
            "pct": (display, 11, "bold"),
            "mono": (mono, 9),
        }

    def setup_ttk_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass

        style.configure(".", background=C_BG, foreground=C_TEXT, font=self.F["body"])

        style.configure("Treeview", background=C_SURFACE, foreground=C_TEXT, fieldbackground=C_SURFACE,
                        borderwidth=0, font=self.F["body"], rowheight=34)
        style.configure("Treeview.Heading", background=C_SURFACE, foreground=C_TEXT_FAINT,
                        font=self.F["label"], borderwidth=0, relief="flat", padding=(10, 8))
        style.map("Treeview.Heading", background=[('active', C_SURFACE)])
        style.map("Treeview", background=[('selected', C_SURFACE_3)], foreground=[('selected', C_TEXT)])
        style.layout("Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])

        for orient in ("Vertical", "Horizontal"):
            style.configure(f"Dark.{orient}.TScrollbar", background=C_SURFACE_3, troughcolor=C_SURFACE,
                            bordercolor=C_SURFACE, arrowcolor=C_TEXT_FAINT, lightcolor=C_SURFACE_3,
                            darkcolor=C_SURFACE_3, gripcount=0, arrowsize=10)
            style.map(f"Dark.{orient}.TScrollbar", background=[('active', C_BORDER_STRONG)])

    def entry(self, parent, var):
        return tk.Entry(parent, textvariable=var, font=self.F["body"], bg=C_BG, fg=C_TEXT,
                        insertbackground=C_ACCENT, relief=tk.FLAT, highlightthickness=1,
                        highlightbackground=C_BORDER_STRONG, highlightcolor=C_ACCENT,
                        selectbackground=C_ACCENT, selectforeground=C_ON_ACCENT,
                        disabledbackground=C_SURFACE_2)

    def section_label(self, parent, text, bg=C_SURFACE):
        return tk.Label(parent, text=text, font=self.F["label"], fg=C_TEXT_FAINT, bg=bg, anchor="w")

    # -------------------------------------------------------------
    # LAYOUT
    # -------------------------------------------------------------
    def build_ui(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.build_sidebar()

        main = tk.Frame(self, bg=C_BG)
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)
        self.main = main

        # Workspace: page column + settings column
        work = tk.Frame(main, bg=C_BG)
        work.grid(row=0, column=0, sticky="nsew", padx=24, pady=(20, 16))
        work.columnconfigure(0, weight=1)
        work.rowconfigure(1, weight=1)

        head = tk.Frame(work, bg=C_BG)
        head.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        self.lbl_page_title = tk.Label(head, text="", font=self.F["h1"], fg=C_TEXT, bg=C_BG, anchor="w")
        self.lbl_page_title.pack(anchor="w")
        self.lbl_page_desc = tk.Label(head, text="", font=self.F["body"], fg=C_TEXT_MUTED, bg=C_BG, anchor="w")
        self.lbl_page_desc.pack(anchor="w", pady=(2, 0))

        self.page_host = tk.Frame(work, bg=C_BG)
        self.page_host.grid(row=1, column=0, sticky="nsew")
        self.page_host.columnconfigure(0, weight=1)
        self.page_host.rowconfigure(0, weight=1)

        self.settings_col = tk.Frame(work, bg=C_BG, width=340)
        self.settings_col.grid(row=1, column=1, sticky="ns", padx=(16, 0))
        self.settings_col.grid_propagate(False)
        self.settings_col.pack_propagate(False)

        self.tab_batch = tk.Frame(self.page_host, bg=C_BG)
        self.tab_single = tk.Frame(self.page_host, bg=C_BG)
        self.tab_captions = tk.Frame(self.page_host, bg=C_BG)
        for p in (self.tab_batch, self.tab_single, self.tab_captions):
            p.grid(row=0, column=0, sticky="nsew")

        self.build_tab_batch()
        self.build_tab_single()
        self.build_tab_captions()
        self.build_settings_panel()

        # Log drawer (hidden by default) + status bar
        self.build_log_drawer(main)
        self.build_status_bar(main)

        # Toast
        self.toast = tk.Label(self, text="", font=self.F["bold"], bg=C_SURFACE_3, fg=C_TEXT,
                              padx=16, pady=9, highlightthickness=1, highlightbackground=C_BORDER_STRONG)

        self.bind_all("<Control-l>", lambda e: self.toggle_log())

    def build_sidebar(self):
        sb = tk.Frame(self, bg=C_SIDEBAR, width=232)
        sb.grid(row=0, column=0, sticky="ns")
        sb.grid_propagate(False)
        sb.pack_propagate(False)

        brand = tk.Frame(sb, bg=C_SIDEBAR)
        brand.pack(fill=tk.X, padx=20, pady=(22, 26))
        mark = tk.Canvas(brand, width=22, height=22, bg=C_SIDEBAR, highlightthickness=0)
        mark.create_rectangle(1, 3, 21, 19, outline=C_TEXT_MUTED, width=2)
        mark.create_oval(7, 7, 15, 15, fill=C_ACCENT, outline=C_ACCENT)
        mark.pack(side=tk.LEFT, padx=(0, 10))
        bt = tk.Frame(brand, bg=C_SIDEBAR)
        bt.pack(side=tk.LEFT)
        tk.Label(bt, text="AGY Studio", font=self.F["brand"], fg=C_TEXT, bg=C_SIDEBAR).pack(anchor="w")
        tk.Label(bt, text="Short-drama editor", font=self.F["small"], fg=C_TEXT_FAINT,
                 bg=C_SIDEBAR).pack(anchor="w")

        self.section_label(sb, "BIÊN TẬP", bg=C_SIDEBAR).pack(fill=tk.X, padx=22, pady=(0, 6))
        self.nav_items = {}
        self.nav_item(sb, "batch", "Hàng loạt", show_count=True)
        self.nav_item(sb, "single", "Một video")
        tk.Frame(sb, bg=C_SIDEBAR, height=14).pack()
        self.section_label(sb, "ĐĂNG BÀI", bg=C_SIDEBAR).pack(fill=tk.X, padx=22, pady=(0, 6))
        self.nav_item(sb, "captions", "Caption X/Twitter")

        # Bottom: system & AGY connection
        bottom = tk.Frame(sb, bg=C_SIDEBAR)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=14, pady=16)

        sysbox = tk.Frame(bottom, bg=C_SURFACE, highlightthickness=1, highlightbackground=C_BORDER,
                          padx=12, pady=12)
        sysbox.pack(fill=tk.X)

        row = tk.Frame(sysbox, bg=C_SURFACE)
        row.pack(fill=tk.X)
        self.agy_dot = tk.Canvas(row, width=8, height=8, bg=C_SURFACE, highlightthickness=0)
        self.agy_dot.pack(side=tk.LEFT, padx=(0, 8))
        self._paint_dot(C_WARNING)
        tk.Label(row, textvariable=self.agy_status_var, font=self.F["bold"], fg=C_TEXT,
                 bg=C_SURFACE, anchor="w").pack(side=tk.LEFT)

        self.lbl_ram_status = tk.Label(sysbox, text="Đang đọc RAM...", font=self.F["small"],
                                       fg=C_TEXT_MUTED, bg=C_SURFACE, anchor="w", justify="left")
        self.lbl_ram_status.pack(fill=tk.X, pady=(8, 10))

        FlatButton(sysbox, "Đăng nhập Google", self.on_login_agy_click, font=self.F["small"],
                   padx=6, pady=5).pack(fill=tk.X, pady=(0, 4))
        FlatButton(sysbox, "Kiểm tra kết nối", self.on_test_agy_click, variant="ghost",
                   font=self.F["small"], padx=6, pady=4).pack(fill=tk.X)

    def nav_item(self, parent, key, text, show_count=False):
        f = tk.Frame(parent, bg=C_SIDEBAR, cursor="hand2", takefocus=1, highlightthickness=1,
                     highlightbackground=C_SIDEBAR, highlightcolor=C_ACCENT)
        f.pack(fill=tk.X, padx=10, pady=1)
        lbl = tk.Label(f, text=text, font=self.F["nav"], fg=C_TEXT_MUTED, bg=C_SIDEBAR,
                       anchor="w", padx=12, pady=8)
        lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        cnt = None
        if show_count:
            cnt = tk.Label(f, text="", font=self.F["small"], fg=C_TEXT_FAINT, bg=C_SIDEBAR, padx=10)
            cnt.pack(side=tk.RIGHT)
        widgets = [w for w in (f, lbl, cnt) if w is not None]
        for w in widgets:
            w.bind("<Button-1>", lambda e, k=key: self.show_page(k))
            w.bind("<Enter>", lambda e, k=key: self._nav_hover(k, True))
            w.bind("<Leave>", lambda e, k=key: self._nav_hover(k, False))
        f.bind("<KeyPress-Return>", lambda e, k=key: self.show_page(k))
        f.bind("<KeyPress-space>", lambda e, k=key: self.show_page(k))
        self.nav_items[key] = (widgets, lbl, cnt)

    def _nav_hover(self, key, on):
        if key == self.current_page:
            return
        widgets, lbl, _ = self.nav_items[key]
        bg = C_SURFACE if on else C_SIDEBAR
        for w in widgets:
            w.config(bg=bg)
        widgets[0].config(highlightbackground=bg)
        lbl.config(fg=C_TEXT if on else C_TEXT_MUTED)

    PAGES = {
        "batch": ("Hàng loạt", "Thêm nhiều video, chọn chế độ ở cột bên phải rồi chạy cả hàng đợi."),
        "single": ("Một video", "Chọn một video, kiểm tra thông số và xuất ngay."),
        "captions": ("Caption X/Twitter", "Ba phương án caption an toàn shadowban cho video vừa xuất. Sửa trực tiếp rồi copy."),
    }

    def show_page(self, key):
        self.current_page = key
        page = {"batch": self.tab_batch, "single": self.tab_single, "captions": self.tab_captions}[key]
        page.tkraise()
        title, desc = self.PAGES[key]
        self.lbl_page_title.config(text=title)
        self.lbl_page_desc.config(text=desc)
        for k, (widgets, lbl, cnt) in self.nav_items.items():
            sel = k == key
            bg = C_SURFACE_2 if sel else C_SIDEBAR
            for w in widgets:
                w.config(bg=bg)
            widgets[0].config(highlightbackground=bg)
            lbl.config(fg=C_TEXT if sel else C_TEXT_MUTED, font=self.F["nav_sel"] if sel else self.F["nav"])
            if cnt is not None:
                cnt.config(fg=C_ACCENT if sel else C_TEXT_FAINT)
        if key == "captions":
            self.settings_col.grid_remove()
        else:
            self.settings_col.grid()
            if key == "batch":
                self.threads_block.pack(fill=tk.X, pady=(0, 16), before=self.caption_block)
            else:
                self.threads_block.pack_forget()
            self.refresh_run_button()

    # Backwards-compatible alias used by the completion button
    @property
    def notebook(self):
        app = self

        class _NB:
            def select(self, tab):
                app.show_page({app.tab_batch: "batch", app.tab_single: "single",
                               app.tab_captions: "captions"}.get(tab, "captions"))
        return _NB()

    # -------------------------------------------------------------
    # SETTINGS COLUMN (shared by batch & single)
    # -------------------------------------------------------------
    def build_settings_panel(self):
        card = tk.Frame(self.settings_col, bg=C_SURFACE, highlightthickness=1, highlightbackground=C_BORDER)
        card.pack(fill=tk.BOTH, expand=True)

        # Run area pinned at the bottom of the panel (packed first so it never gets clipped)
        run = tk.Frame(card, bg=C_SURFACE, padx=16, pady=16)
        run.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Frame(card, bg=C_BORDER, height=1).pack(side=tk.BOTTOM, fill=tk.X)

        self.btn_run = FlatButton(run, "Chạy", self.on_run_click, variant="primary",
                                  font=self.F["cta"], pady=10)
        self.btn_run.pack(fill=tk.X)
        self.btn_batch_cancel = FlatButton(run, "Hủy hàng đợi", self.on_cancel_batch_click,
                                           variant="danger", font=self.F["bold"], pady=7)

        # Scrollable settings body
        canvas = tk.Canvas(card, bg=C_SURFACE, highlightthickness=0, bd=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        body = tk.Frame(canvas, bg=C_SURFACE, padx=16, pady=16)
        win = canvas.create_window(0, 0, window=body, anchor="nw")
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))

        def _wheel(e):
            if body.winfo_height() > canvas.winfo_height():
                canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        self.section_label(body, "CHẾ ĐỘ BIÊN TẬP").pack(fill=tk.X, pady=(0, 8))
        for value, title, desc in MODES:
            ChoiceCard(body, self.mode_var, value, title, desc, self.F).pack(fill=tk.X, pady=(0, 4))

        tk.Frame(body, bg=C_SURFACE, height=14).pack()

        self.threads_block = tk.Frame(body, bg=C_SURFACE)
        self.section_label(self.threads_block, "SỐ LUỒNG CHẠY SONG SONG").pack(fill=tk.X, pady=(0, 8))
        Segmented(self.threads_block, self.concurrency_mode_var,
                  [("auto", "Tự động"), ("1", "1 luồng"), ("2", "2 luồng")], self.F).pack(fill=tk.X)
        self.lbl_threads_hint = tk.Label(self.threads_block, text="Tự động chọn theo RAM và GPU.",
                                         font=self.F["small"], fg=C_TEXT_FAINT, bg=C_SURFACE, anchor="w")
        self.lbl_threads_hint.pack(fill=tk.X, pady=(6, 0))

        self.caption_block = tk.Frame(body, bg=C_SURFACE)
        self.caption_block.pack(fill=tk.X, pady=(0, 16))
        CheckRow(self.caption_block, self.auto_caption_var, "Tạo caption X sau khi xuất",
                 "3 phương án, xem ở mục Caption.", self.F).pack(fill=tk.X)

        out = tk.Frame(body, bg=C_SURFACE)
        out.pack(fill=tk.X)
        self.section_label(out, "LƯU VÀO THƯ MỤC").pack(fill=tk.X, pady=(0, 8))
        orow = tk.Frame(out, bg=C_SURFACE)
        orow.pack(fill=tk.X)
        self.ent_single_out = self.entry(orow, self.output_dir_var)
        self.ent_single_out.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 6))
        FlatButton(orow, "Chọn", self.browse_single_output, padx=10, pady=6,
                   font=self.F["bold"]).pack(side=tk.LEFT)
        tk.Label(out, text="Để trống: lưu cạnh video gốc.", font=self.F["small"], fg=C_TEXT_FAINT,
                 bg=C_SURFACE, anchor="w").pack(fill=tk.X, pady=(6, 0))

    def refresh_run_button(self):
        if not hasattr(self, "btn_run"):
            return
        if self.current_page == "batch":
            n = len(self.batch_manager.jobs) if self.batch_manager else 0
            if self.is_batch_running:
                self.btn_run.config(text="Đang chạy hàng đợi...")
                self.btn_run.set_enabled(False)
                self.btn_batch_cancel.pack(fill=tk.X, pady=(8, 0))
            else:
                self.btn_run.config(text=f"Chạy hàng đợi ({n} video)" if n else "Chạy hàng đợi")
                self.btn_run.set_enabled(n > 0 and not self.is_single_running)
                self.btn_batch_cancel.pack_forget()
        else:
            self.btn_batch_cancel.pack_forget()
            if self.is_single_running:
                self.btn_run.config(text="Đang xử lý...")
                self.btn_run.set_enabled(False)
            else:
                self.btn_run.config(text="Xuất video này")
                self.btn_run.set_enabled(bool(self.input_file_var.get().strip()) and not self.is_batch_running)

    def on_run_click(self):
        if self.current_page == "batch":
            self.on_start_batch_click()
        else:
            self.on_start_single_click()

    # -------------------------------------------------------------
    # PAGE: BATCH QUEUE
    # -------------------------------------------------------------
    def build_tab_batch(self):
        card = tk.Frame(self.tab_batch, bg=C_SURFACE, highlightthickness=1, highlightbackground=C_BORDER)
        card.pack(fill=tk.BOTH, expand=True)

        bar = tk.Frame(card, bg=C_SURFACE, padx=14, pady=12)
        bar.pack(fill=tk.X)
        FlatButton(bar, "Thêm video", self.batch_add_files, variant="primary",
                   font=self.F["bold"]).pack(side=tk.LEFT, padx=(0, 6))
        FlatButton(bar, "Thêm cả thư mục", self.batch_add_folder,
                   font=self.F["bold"]).pack(side=tk.LEFT)
        FlatButton(bar, "Xóa hết", self.batch_clear_all, variant="ghost",
                   font=self.F["bold"], padx=10).pack(side=tk.RIGHT)
        self.btn_remove_sel = FlatButton(bar, "Xóa mục đã chọn", self.batch_remove_selected,
                                         variant="ghost", font=self.F["bold"], padx=10)
        self.btn_remove_sel.pack(side=tk.RIGHT, padx=(0, 2))
        self.lbl_queue_summary = tk.Label(bar, text="", font=self.F["small"], fg=C_TEXT_FAINT,
                                          bg=C_SURFACE)
        self.lbl_queue_summary.pack(side=tk.RIGHT, padx=(0, 12))

        tk.Frame(card, bg=C_BORDER, height=1).pack(fill=tk.X)

        table = tk.Frame(card, bg=C_SURFACE)
        table.pack(fill=tk.BOTH, expand=True)
        self.table_frame = table

        cols = ("id", "name", "mode", "progress", "status", "stage")
        self.tree = ttk.Treeview(table, columns=cols, show="headings", selectmode="extended",
                                 displaycolumns=("name", "mode", "progress", "status", "stage"))
        heads = {"id": "#", "name": "VIDEO", "mode": "CHẾ ĐỘ", "progress": "TIẾN ĐỘ",
                 "status": "TRẠNG THÁI", "stage": "GIAI ĐOẠN"}
        for c, t in heads.items():
            self.tree.heading(c, text=t, anchor="w" if c in ("name", "stage") else "center")
        self.tree.column("id", width=44, minwidth=40, anchor="center", stretch=False)
        self.tree.column("name", width=190, minwidth=120, anchor="w")
        self.tree.column("mode", width=80, minwidth=70, anchor="center", stretch=False)
        self.tree.column("progress", width=82, minwidth=76, anchor="center", stretch=False)
        self.tree.column("status", width=112, minwidth=104, anchor="center", stretch=False)
        self.tree.column("stage", width=150, minwidth=100, anchor="w")

        self.tree.tag_configure("odd", background=C_SURFACE)
        self.tree.tag_configure("even", background="#1b1c1f")
        self.tree.tag_configure("st_done", foreground=C_SUCCESS)
        self.tree.tag_configure("st_run", foreground=C_ACCENT)
        self.tree.tag_configure("st_fail", foreground=C_DANGER)
        self.tree.tag_configure("st_cancel", foreground=C_TEXT_FAINT)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0), pady=(0, 4))
        sb_tree = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview,
                                style="Dark.Vertical.TScrollbar")
        sb_tree.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.config(yscrollcommand=sb_tree.set)
        self.tree.bind("<Delete>", lambda e: self.batch_remove_selected())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.refresh_queue_ui())

        # Empty state placed over the table
        self.empty_state = tk.Frame(table, bg=C_SURFACE)
        frame_icon = tk.Canvas(self.empty_state, width=56, height=44, bg=C_SURFACE, highlightthickness=0)
        frame_icon.create_rectangle(2, 2, 54, 42, outline=C_BORDER_STRONG, width=2)
        for x in (10, 22, 34, 46):
            frame_icon.create_rectangle(x - 3, 6, x + 1, 10, fill=C_BORDER_STRONG, width=0)
            frame_icon.create_rectangle(x - 3, 34, x + 1, 38, fill=C_BORDER_STRONG, width=0)
        frame_icon.create_polygon(24, 16, 24, 28, 34, 22, fill=C_ACCENT, outline=C_ACCENT)
        frame_icon.pack(pady=(0, 14))
        tk.Label(self.empty_state, text="Hàng đợi đang trống", font=self.F["h2"], fg=C_TEXT,
                 bg=C_SURFACE).pack()
        tk.Label(self.empty_state, text="Thêm vài video hoặc cả một thư mục. Mỗi video sẽ dùng\n"
                                        "chế độ và thư mục lưu đang chọn ở cột bên phải.",
                 font=self.F["body"], fg=C_TEXT_MUTED, bg=C_SURFACE, justify="center").pack(pady=(4, 16))
        er = tk.Frame(self.empty_state, bg=C_SURFACE)
        er.pack()
        FlatButton(er, "Thêm video", self.batch_add_files, variant="primary",
                   font=self.F["bold"]).pack(side=tk.LEFT, padx=(0, 6))
        FlatButton(er, "Thêm cả thư mục", self.batch_add_folder, font=self.F["bold"]).pack(side=tk.LEFT)

    def refresh_queue_ui(self):
        jobs = self.batch_manager.jobs if self.batch_manager else []
        n = len(jobs)
        if n == 0:
            self.empty_state.place(relx=0.5, rely=0.46, anchor="center")
        else:
            self.empty_state.place_forget()
        done = sum(1 for j in jobs if j.status == "Hoàn thành")
        failed = sum(1 for j in jobs if j.status in ("Thất bại", "Lỗi"))
        parts = []
        if n:
            parts.append(f"{n} video")
            if done:
                parts.append(f"{done} xong")
            if failed:
                parts.append(f"{failed} lỗi")
        self.lbl_queue_summary.config(text="  ·  ".join(parts))
        _, _, cnt = self.nav_items["batch"]
        cnt.config(text=str(n) if n else "")
        self.btn_remove_sel.set_enabled(bool(self.tree.selection()) and not self.is_batch_running)
        self.refresh_run_button()

    def _row_values(self, job):
        return (job.job_id, os.path.basename(job.input_path), MODE_SHORT.get(job.mode, job.mode),
                f"{job.progress}%", job.status, job.stage)

    def _row_tags(self, job, index):
        tags = ["even" if index % 2 else "odd"]
        st = STATUS_TAGS.get(job.status)
        if st:
            tags.append(st)
        return tuple(tags)

    def _insert_job_row(self, job):
        idx = len(self.tree.get_children())
        self.tree.insert("", tk.END, iid=str(job.job_id), values=self._row_values(job),
                         tags=self._row_tags(job, idx))

    def _restripe(self):
        for i, item in enumerate(self.tree.get_children()):
            tags = [t for t in self.tree.item(item, "tags") if t not in ("odd", "even")]
            self.tree.item(item, tags=tuple(["even" if i % 2 else "odd"] + tags))

    # -------------------------------------------------------------
    # PAGE: SINGLE VIDEO
    # -------------------------------------------------------------
    def build_tab_single(self):
        card = tk.Frame(self.tab_single, bg=C_SURFACE, highlightthickness=1, highlightbackground=C_BORDER)
        card.pack(fill=tk.X, anchor="n")
        inner = tk.Frame(card, bg=C_SURFACE, padx=20, pady=20)
        inner.pack(fill=tk.X)

        self.section_label(inner, "VIDEO NGUỒN").pack(fill=tk.X, pady=(0, 8))
        in_row = tk.Frame(inner, bg=C_SURFACE)
        in_row.pack(fill=tk.X)
        self.ent_single_in = self.entry(in_row, self.input_file_var)
        self.ent_single_in.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=7)
        FlatButton(in_row, "Chọn video", self.browse_single_input, variant="primary",
                   font=self.F["bold"]).pack(side=tk.LEFT)
        tk.Label(inner, text="Dán đường dẫn (Ctrl+V) hoặc bấm Chọn video. Hỗ trợ .mp4 .mov .mkv .avi .webm",
                 font=self.F["small"], fg=C_TEXT_FAINT, bg=C_SURFACE, anchor="w").pack(fill=tk.X, pady=(6, 0))

        tk.Frame(inner, bg=C_BORDER, height=1).pack(fill=tk.X, pady=20)

        specs = tk.Frame(inner, bg=C_SURFACE)
        specs.pack(fill=tk.X)
        self.spec_labels = {}
        for i, (key, label) in enumerate([("res", "ĐỘ PHÂN GIẢI"), ("fps", "KHUNG HÌNH"),
                                          ("dur", "THỜI LƯỢNG"), ("out", "TÊN FILE XUẤT")]):
            col = tk.Frame(specs, bg=C_SURFACE)
            if key == "out":
                col.grid(row=1, column=0, columnspan=4, sticky="nw", pady=(16, 0))
            else:
                col.grid(row=0, column=i, sticky="nw", padx=(0, 40))
            self.section_label(col, label).pack(anchor="w")
            v = tk.Label(col, text="—", font=self.F["h2"], fg=C_TEXT_MUTED, bg=C_SURFACE, anchor="w")
            v.pack(anchor="w", pady=(4, 0))
            self.spec_labels[key] = v
        specs.columnconfigure(3, weight=1)

        self.lbl_single_specs = tk.Label(inner, text="", font=self.F["small"], fg=C_TEXT_FAINT,
                                         bg=C_SURFACE, anchor="w")
        self.lbl_single_specs.pack(fill=tk.X, pady=(10, 0))

        self.input_file_var.trace_add("write", lambda *a: self._on_input_changed())

    def _on_input_changed(self):
        self.refresh_run_button()
        if self._spec_job:
            self.after_cancel(self._spec_job)
        self._spec_job = self.after(350, self._load_specs)

    def _load_specs(self):
        p = self.input_file_var.get().strip().strip('"').strip("'")
        for k in ("res", "fps", "dur", "out"):
            self.spec_labels[k].config(text="—", fg=C_TEXT_MUTED)
        if not p:
            self.lbl_single_specs.config(text="", fg=C_TEXT_FAINT)
            return
        if not os.path.isfile(p):
            self.lbl_single_specs.config(text="Không tìm thấy file ở đường dẫn này.", fg=C_DANGER)
            return
        base = os.path.splitext(os.path.basename(p))[0]
        self.spec_labels["out"].config(text=f"{base}_edited.mp4", fg=C_TEXT)
        self.lbl_single_specs.config(text="Đang đọc thông số video...", fg=C_TEXT_FAINT)

        def _info():
            try:
                sp = VideoEditorEngine().get_video_specs(p)
            except Exception as e:
                self.after(0, lambda: self.lbl_single_specs.config(
                    text=f"Không đọc được thông số: {e}", fg=C_DANGER))
                return

            def _apply():
                if self.input_file_var.get().strip().strip('"').strip("'") != p:
                    return
                if sp['width'] <= 0 or sp['height'] <= 0 or sp['duration'] <= 0:
                    self.lbl_single_specs.config(
                        text="File này không đọc được như video. Kiểm tra lại định dạng.", fg=C_DANGER)
                    return
                self.spec_labels["res"].config(text=f"{sp['width']} × {sp['height']}", fg=C_TEXT)
                self.spec_labels["fps"].config(text=f"{sp['fps']:.1f} fps", fg=C_TEXT)
                m, s = divmod(sp['duration'], 60)
                self.spec_labels["dur"].config(text=f"{int(m)}:{s:05.2f}", fg=C_TEXT)
                self.lbl_single_specs.config(text="Video hợp lệ, sẵn sàng xuất.", fg=C_SUCCESS)
            self.after(0, _apply)
        threading.Thread(target=_info, daemon=True).start()

    # -------------------------------------------------------------
    # PAGE: CAPTIONS
    # -------------------------------------------------------------
    def build_tab_captions(self):
        top = tk.Frame(self.tab_captions, bg=C_BG)
        top.pack(fill=tk.X, pady=(0, 12))
        self.lbl_caption_source = tk.Label(top, text="Chưa có video nào. Hãy xuất một video trước.",
                                           font=self.F["body"], fg=C_TEXT_MUTED, bg=C_BG, anchor="w")
        self.lbl_caption_source.pack(side=tk.LEFT)
        self.btn_regen = FlatButton(top, "Tạo lại caption", self.regenerate_captions_ui, font=self.F["bold"])
        self.btn_regen.pack(side=tk.RIGHT)

        grid = tk.Frame(self.tab_captions, bg=C_BG)
        grid.pack(fill=tk.BOTH, expand=True)
        grid.columnconfigure(0, weight=1)

        self.caption_boxes = []
        self.copy_buttons = []
        for i in range(3):
            card_opt = tk.Frame(grid, bg=C_SURFACE, highlightthickness=1, highlightbackground=C_BORDER)
            card_opt.grid(row=i, column=0, sticky="nsew", pady=(0, 10))
            grid.rowconfigure(i, weight=1)

            head = tk.Frame(card_opt, bg=C_SURFACE, padx=16, pady=12)
            head.pack(fill=tk.X)
            tk.Label(head, text=f"Phương án {i+1}", font=self.F["label"], fg=C_TEXT_FAINT,
                     bg=C_SURFACE).pack(side=tk.LEFT)
            lbl_opt_name = tk.Label(head, text="", font=self.F["bold"], fg=C_TEXT, bg=C_SURFACE)
            lbl_opt_name.pack(side=tk.LEFT, padx=(10, 0))

            btn_copy = FlatButton(head, "Copy", lambda idx=i: self.copy_caption(idx),
                                  font=self.F["bold"], padx=14, pady=5)
            btn_copy.pack(side=tk.RIGHT)
            self.copy_buttons.append(btn_copy)

            txt = tk.Text(card_opt, bg=C_SURFACE, fg=C_TEXT, font=self.F["body"], relief=tk.FLAT,
                          padx=16, pady=0, height=3, wrap=tk.WORD, insertbackground=C_ACCENT,
                          selectbackground=C_ACCENT, selectforeground=C_ON_ACCENT,
                          highlightthickness=0, spacing2=3)
            txt.pack(fill=tk.BOTH, expand=True, pady=(0, 14))
            txt.insert("1.0", "Caption sẽ hiện ở đây sau khi video được xuất.")
            txt.config(fg=C_TEXT_FAINT)
            self.caption_boxes.append((lbl_opt_name, txt))
        self._set_copy_enabled(False)

    def _set_copy_enabled(self, enabled):
        for b in self.copy_buttons:
            b.set_enabled(enabled)

    # -------------------------------------------------------------
    # LOG DRAWER & STATUS BAR
    # -------------------------------------------------------------
    def build_log_drawer(self, main):
        self.log_drawer = tk.Frame(main, bg=C_CONSOLE_BG, height=190)
        self.log_drawer.grid_propagate(False)
        self.log_drawer.pack_propagate(False)

        head = tk.Frame(self.log_drawer, bg=C_CONSOLE_BG, padx=24, pady=8)
        head.pack(fill=tk.X)
        tk.Label(head, text="NHẬT KÝ XỬ LÝ", font=self.F["label"], fg=C_TEXT_FAINT,
                 bg=C_CONSOLE_BG).pack(side=tk.LEFT)
        FlatButton(head, "Xóa log", lambda: self.txt_log.delete('1.0', tk.END), variant="ghost",
                   font=self.F["small"], padx=8, pady=3).pack(side=tk.RIGHT)

        box = tk.Frame(self.log_drawer, bg=C_CONSOLE_BG)
        box.pack(fill=tk.BOTH, expand=True, padx=(18, 0))
        self.txt_log = tk.Text(box, bg=C_CONSOLE_BG, fg=C_CONSOLE_TEXT, font=self.F["mono"],
                               insertbackground=C_ACCENT, relief=tk.FLAT, padx=6, pady=2,
                               wrap=tk.WORD, highlightthickness=0, selectbackground=C_SURFACE_3,
                               spacing1=1, spacing3=1)
        self.txt_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.txt_log.tag_configure("ts", foreground=C_TEXT_FAINT)
        sb = ttk.Scrollbar(box, orient="vertical", command=self.txt_log.yview,
                           style="Dark.Vertical.TScrollbar")
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_log.config(yscrollcommand=sb.set)

    def build_status_bar(self, main):
        tk.Frame(main, bg=C_BORDER, height=1).grid(row=2, column=0, sticky="ew")
        bar = tk.Frame(main, bg=C_SURFACE, padx=24, pady=10)
        bar.grid(row=3, column=0, sticky="ew")
        bar.columnconfigure(0, weight=1)

        left = tk.Frame(bar, bg=C_SURFACE)
        left.grid(row=0, column=0, sticky="ew", padx=(0, 20))
        left.columnconfigure(0, weight=1)
        self.lbl_status = tk.Label(left, textvariable=self.status_msg_var, font=self.F["bold"],
                                   fg=C_TEXT, bg=C_SURFACE, anchor="w", width=1)
        self.lbl_status.grid(row=0, column=0, sticky="ew")
        self.lbl_pct = tk.Label(left, text="0%", font=self.F["pct"], fg=C_TEXT_MUTED, bg=C_SURFACE,
                                anchor="e")
        self.lbl_pct.grid(row=0, column=1, sticky="e", padx=(12, 0))
        self.prog_bar = ThinProgress(left, self.progress_var)
        self.prog_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        right = tk.Frame(bar, bg=C_SURFACE)
        right.grid(row=0, column=1, sticky="e")

        self.completion_box = tk.Frame(right, bg=C_SURFACE)
        self.btn_open_folder = FlatButton(self.completion_box, "Mở thư mục", self.on_open_folder_click,
                                          variant="success", font=self.F["bold"], padx=10, pady=5)
        self.btn_open_folder.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_play_vid = FlatButton(self.completion_box, "Xem video", self.on_play_video_click,
                                       variant="success", font=self.F["bold"], padx=10, pady=5)
        self.btn_play_vid.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_view_caps = FlatButton(self.completion_box, "Xem caption",
                                        lambda: self.show_page("captions"), font=self.F["bold"],
                                        padx=10, pady=5)
        self.btn_view_caps.pack(side=tk.LEFT, padx=(0, 12))
        self._completion_anchor = tk.Frame(right, bg=C_SURFACE)
        self._completion_anchor.pack(side=tk.LEFT)

        self.btn_log = FlatButton(right, "Hiện nhật ký", self.toggle_log, variant="ghost",
                                  font=self.F["bold"], padx=10, pady=5)
        self.btn_log.pack(side=tk.LEFT)

    def _show_completion(self):
        self.completion_box.pack(side=tk.LEFT, before=self._completion_anchor)

    def toggle_log(self):
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.log_drawer.grid(row=1, column=0, sticky="ew")
            self.btn_log.config(text="Ẩn nhật ký")
            self.txt_log.see(tk.END)
        else:
            self.log_drawer.grid_remove()
            self.btn_log.config(text="Hiện nhật ký")

    def show_toast(self, text, kind="info"):
        fg = {"info": C_TEXT, "success": C_SUCCESS, "warn": C_WARNING, "error": C_DANGER}[kind]
        self.toast.config(text=text, fg=fg)
        self.toast.place(relx=1.0, rely=1.0, x=-24, y=-72, anchor="se")
        self.toast.lift()
        if self._toast_job:
            self.after_cancel(self._toast_job)
        self._toast_job = self.after(2600, self.toast.place_forget)

    def set_progress(self, pct, msg=None):
        self.progress_var.set(pct)
        self.lbl_pct.config(text=f"{pct}%", fg=C_SUCCESS if pct >= 100 else
                            (C_ACCENT if pct > 0 else C_TEXT_MUTED))
        if msg is not None:
            self.status_msg_var.set(msg)

    # -------------------------------------------------------------
    # LOGIC & EVENT HANDLERS
    # -------------------------------------------------------------
    def log(self, text):
        def _app():
            ts = time.strftime("%H:%M:%S  ")
            self.txt_log.insert(tk.END, ts, "ts")
            self.txt_log.insert(tk.END, text + "\n")
            self.txt_log.see(tk.END)
        self.after(0, _app)

    def _paint_dot(self, color):
        self.agy_dot.delete("all")
        self.agy_dot.create_oval(0, 0, 8, 8, fill=color, outline=color)

    def init_system_diagnostics_async(self):
        total, avail, load = get_system_ram_info()
        workers, _, _, _ = calculate_smart_workers()

        def _ram():
            self.lbl_ram_status.config(
                text=f"RAM trống {avail:.1f} / {total:.1f} GB\nĐang dùng {load}%")
            self.lbl_threads_hint.config(text=f"Tự động: máy này nên chạy {workers} luồng.")
        self.after(0, _ram)

        ok, msg, ver = test_agy_connection()

        def _agy():
            if ok:
                self.agy_status_var.set(f"AGY CLI v{ver}")
                self._paint_dot(C_SUCCESS)
                self.log(f"AGY CLI sẵn sàng: v{ver}")
            else:
                self.agy_status_var.set("Chưa kết nối AGY")
                self._paint_dot(C_WARNING)
            if self.status_msg_var.get().startswith("Đang kiểm tra"):
                self.status_msg_var.set("Sẵn sàng." if ok else "AGY chưa kết nối. Bấm Đăng nhập Google.")
        self.after(0, _agy)

    def on_test_agy_click(self):
        self.status_msg_var.set("Đang kiểm tra kết nối AGY...")
        self.agy_status_var.set("Đang kiểm tra...")
        self._paint_dot(C_TEXT_FAINT)
        threading.Thread(target=self.init_system_diagnostics_async, daemon=True).start()

    def on_login_agy_click(self):
        self.log("Đang mở Terminal đăng nhập Google AGY...")
        ok, msg = launch_login_terminal()
        if ok: messagebox.showinfo("Đăng Nhập AGY", msg)
        else: messagebox.showerror("Lỗi", msg)

    # Batch Operations
    def batch_add_files(self):
        files = filedialog.askopenfilenames(title="Chọn danh sách video", filetypes=VIDEO_TYPES)
        for f in files:
            norm = os.path.normpath(f)
            out_dir = self.output_dir_var.get().strip() or os.path.dirname(norm)
            job = self.batch_manager.add_job(norm, out_dir, self.mode_var.get(), self.sub_mode_var.get())
            self._insert_job_row(job)
        if files:
            self.log(f"Đã thêm {len(files)} video vào hàng đợi.")
            self.show_toast(f"Đã thêm {len(files)} video vào hàng đợi")
        self.refresh_queue_ui()

    def batch_add_folder(self):
        folder = filedialog.askdirectory(title="Chọn thư mục chứa video")
        if not folder: return
        exts = ('.mp4', '.mov', '.mkv', '.avi', '.webm')
        added = 0
        for root, _, files in os.walk(folder):
            for file in files:
                if file.lower().endswith(exts):
                    norm = os.path.normpath(os.path.join(root, file))
                    out_dir = self.output_dir_var.get().strip() or folder
                    job = self.batch_manager.add_job(norm, out_dir, self.mode_var.get(), self.sub_mode_var.get())
                    self._insert_job_row(job)
                    added += 1
        self.log(f"Đã quét và thêm {added} video từ thư mục: {folder}")
        if added:
            self.show_toast(f"Đã thêm {added} video từ thư mục")
        else:
            self.show_toast("Thư mục này không có video phù hợp", "warn")
        self.refresh_queue_ui()

    def batch_remove_selected(self):
        if self.is_batch_running:
            return
        for item in self.tree.selection():
            job_id = int(self.tree.item(item, "values")[0])
            self.batch_manager.remove_job(job_id)
            self.tree.delete(item)
        self._restripe()
        self.refresh_queue_ui()

    def batch_clear_all(self):
        if self.batch_manager.clear_jobs():
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.log("Đã làm trống toàn bộ hàng đợi.")
        elif self.is_batch_running:
            self.show_toast("Không thể xóa khi hàng đợi đang chạy", "warn")
        self.refresh_queue_ui()

    def on_start_batch_click(self):
        if not self.batch_manager.jobs:
            self.show_toast("Hàng đợi trống. Bấm Thêm video trước.", "warn")
            return

        workers = None
        if self.concurrency_mode_var.get() != "auto":
            workers = int(self.concurrency_mode_var.get())

        self.completion_box.pack_forget()
        self.is_batch_running = True
        self.set_progress(0, "Đang chạy hàng đợi...")
        self.refresh_queue_ui()

        self.batch_manager.start_batch(user_workers=workers, auto_caption=self.auto_caption_var.get())

    def on_cancel_batch_click(self):
        self.batch_manager.cancel_all()
        self.btn_batch_cancel.config(text="Đang hủy...")
        self.btn_batch_cancel.set_enabled(False)

    def on_batch_job_update(self, job):
        def _up():
            item_id = str(job.job_id)
            if self.tree.exists(item_id):
                idx = self.tree.index(item_id)
                self.tree.item(item_id, values=self._row_values(job), tags=self._row_tags(job, idx))
            if job.status == "Hoàn thành" and job.caption_variants:
                self.load_captions_ui(job.caption_variants)
                self.last_output_file = job.output_path
            jobs = self.batch_manager.jobs
            if jobs and self.is_batch_running:
                overall = int(sum(j.progress for j in jobs) / len(jobs))
                active = sum(1 for j in jobs if j.status == "Đang xử lý")
                done = sum(1 for j in jobs if j.status == "Hoàn thành")
                self.set_progress(min(overall, 99),
                                  f"Đang chạy: {done}/{len(jobs)} xong, {active} đang xử lý")
            self.refresh_queue_ui()
        self.after(0, _up)

    def on_batch_complete_handler(self):
        def _done():
            self.is_batch_running = False
            self.btn_batch_cancel.config(text="Hủy hàng đợi")
            self.btn_batch_cancel.set_enabled(True)
            jobs = self.batch_manager.jobs
            done = sum(1 for j in jobs if j.status == "Hoàn thành")
            self.set_progress(100, f"Xong hàng đợi: {done}/{len(jobs)} video thành công.")
            self._show_completion()
            self.refresh_queue_ui()

            send_notification("AGY Batch Completed", "Đã xử lý xong toàn bộ danh sách video hàng đợi!", is_success=True)
            self.show_toast(f"Đã xuất xong {done}/{len(jobs)} video", "success")
        self.after(0, _done)

    # Single Video Handlers
    def browse_single_input(self):
        p = filedialog.askopenfilename(title="Chọn video", filetypes=VIDEO_TYPES)
        if p:
            if not self.output_dir_var.get():
                self.output_dir_var.set(os.path.normpath(os.path.dirname(p)))
            self.input_file_var.set(os.path.normpath(p))

    def browse_single_output(self):
        d = filedialog.askdirectory(title="Chọn thư mục lưu")
        if d: self.output_dir_var.set(os.path.normpath(d))

    def on_start_single_click(self):
        in_p = self.input_file_var.get().strip().strip('"').strip("'")
        if not in_p or not os.path.exists(in_p):
            self.show_toast("Chưa có video hợp lệ. Chọn hoặc dán đường dẫn video.", "warn")
            self.ent_single_in.focus_set()
            return

        out_d = self.output_dir_var.get().strip() or os.path.dirname(in_p)
        base = os.path.splitext(os.path.basename(in_p))[0]
        out_f = os.path.join(out_d, f"{base}_edited.mp4")
        self.last_output_file = out_f

        self.is_single_running = True
        self.refresh_run_button()
        self.completion_box.pack_forget()
        self.set_progress(0, "Đang chuẩn bị...")

        def _worker():
            eng = VideoEditorEngine(log_callback=self.log,
                                    progress_callback=lambda p, m: self.after(0, lambda: self.set_progress(p, m)))
            ok, msg = eng.process_video(in_p, out_f, mode=self.mode_var.get(), sub_mode=self.sub_mode_var.get())

            caps = []
            if ok and self.auto_caption_var.get():
                self.after(0, lambda: self.status_msg_var.set("Đang tạo caption X..."))
                caps = generate_captions_with_agy(out_f)
                save_captions_to_file(out_f, caps)

            def _fin():
                self.is_single_running = False
                self.refresh_run_button()
                if ok:
                    self.set_progress(100, f"Đã xuất: {os.path.basename(out_f)}")
                    self._show_completion()
                    if caps: self.load_captions_ui(caps)
                    send_notification("AGY Video Editor", f"Đã xuất xong: {os.path.basename(out_f)}", is_success=True)
                    self.show_toast("Xuất video thành công", "success")
                else:
                    self.status_msg_var.set("Xuất video thất bại.")
                    self.lbl_pct.config(fg=C_DANGER)
                    messagebox.showerror("Không xuất được video", msg)
            self.after(0, _fin)

        threading.Thread(target=_worker, daemon=True).start()

    # Caption UI Handlers
    def load_captions_ui(self, variants):
        self.current_captions = variants
        for i, v in enumerate(variants[:3]):
            lbl, txt = self.caption_boxes[i]
            lbl.config(text=v['style'])
            txt.config(fg=C_TEXT)
            txt.delete('1.0', tk.END)
            txt.insert('1.0', v['caption'])
        self._set_copy_enabled(bool(variants))
        if self.last_output_file:
            self.lbl_caption_source.config(text=f"Cho video: {os.path.basename(self.last_output_file)}",
                                           fg=C_TEXT)

    def regenerate_captions_ui(self):
        if not self.last_output_file:
            self.show_toast("Hãy xuất một video trước để tạo caption.", "warn")
            return
        self.btn_regen.config(text="Đang tạo...")
        self.btn_regen.set_enabled(False)
        path = self.last_output_file

        def _work():
            vars_new = generate_captions_with_agy(path)
            save_captions_to_file(path, vars_new)

            def _fin():
                self.load_captions_ui(vars_new)
                self.btn_regen.config(text="Tạo lại caption")
                self.btn_regen.set_enabled(True)
                self.show_toast("Đã tạo bộ caption mới", "success")
            self.after(0, _fin)
        threading.Thread(target=_work, daemon=True).start()

    def copy_caption(self, idx):
        if idx < len(self.current_captions):
            # Copy what is in the box, so manual edits are kept
            text = self.caption_boxes[idx][1].get("1.0", "end-1c").strip()
            self.clipboard_clear()
            self.clipboard_append(text)
            btn = self.copy_buttons[idx]
            btn.config(text="Đã copy", fg=C_SUCCESS)
            self.after(1500, lambda: btn.config(text="Copy", fg=btn.v["fg"]))

    def on_open_folder_click(self):
        if self.last_output_file and os.path.exists(self.last_output_file):
            reveal_in_file_manager(self.last_output_file)
        else:
            self.show_toast("Không tìm thấy file đã xuất.", "error")

    def on_play_video_click(self):
        if self.last_output_file and os.path.exists(self.last_output_file):
            open_media_file(self.last_output_file)
        else:
            self.show_toast("Không tìm thấy file đã xuất.", "error")


def main():
    app = AGYShortDramaStudio()
    if sys.platform == "darwin":
        # Apps started from Terminal open behind it on macOS: bring the window forward once.
        def _bring_to_front():
            app.lift()
            app.attributes("-topmost", True)
            app.after(300, lambda: app.attributes("-topmost", False))
            app.focus_force()
        app.after(200, _bring_to_front)
    app.mainloop()


if __name__ == "__main__":
    main()
