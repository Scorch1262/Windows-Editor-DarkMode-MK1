# -*- coding: utf-8 -*-
"""
Editor-Darkmode-MK1
===================

Nachbau des Windows-10-Editors (Notepad) mit dunkler Oberfläche im Stil der
Dashboards (Lattice-Optik, Teal-/Amber-Akzente).

* Nur Python-Standardbibliothek (tkinter) – keine externen Pakete nötig.
* Einstellungen werden menschenlesbar in "Editor-Darkmode-MK1.ini" neben der
  exe abgelegt (falls der Ordner nicht beschreibbar ist: %APPDATA%).
* Aufruf mit Dateipfad als Argument öffnet die Datei direkt
  (z. B. für "Öffnen mit …").
"""

import codecs
import configparser
import datetime
import os
import subprocess
import sys
import tempfile
import urllib.parse
import webbrowser

import tkinter as tk
from tkinter import filedialog, ttk
from tkinter import font as tkfont

APP_TITLE = "Editor"
APP_ID = "Editor-Darkmode-MK1"
APP_VERSION = "1.1.0"

IS_WIN = sys.platform.startswith("win")

if IS_WIN:
    import ctypes

# ---------------------------------------------------------------------------
# Farben – angelehnt an die Dashboards (dunkler Grund, Teal + Amber)
# ---------------------------------------------------------------------------
C = {
    "bg": "#0b0d10",
    "panel": "#14171c",
    "card": "#181c22",
    "editor": "#0f1216",
    "border": "#262b33",
    "hover": "#1f252d",
    "pressed": "#2a313b",
    "text": "#e6e9ee",
    "dim": "#8a92a0",
    "faint": "#545b67",
    "accent": "#35d0ba",
    "accent_soft": "#173a35",
    "amber": "#ffb84d",
    "danger": "#ff5c5c",
    "sel": "#1d4943",
    "sel_inactive": "#1f2e2c",
    "thumb": "#2b313b",
    "thumb_hover": "#3a424e",
}

UI_FAMILY = "Segoe UI" if IS_WIN else "DejaVu Sans"
MONO_FAMILY = "Consolas" if IS_WIN else "DejaVu Sans Mono"
UI_FONT = (UI_FAMILY, 9)
UI_FONT_MSG = (UI_FAMILY, 10)
STATUS_FONT = (MONO_FAMILY, 9)

ENCODINGS = ["UTF-8", "UTF-8 mit BOM", "UTF-16 LE", "UTF-16 BE", "ANSI"]
ENCODING_CODEC = {
    "UTF-8": ("utf-8", b""),
    "UTF-8 mit BOM": ("utf-8", codecs.BOM_UTF8),
    "UTF-16 LE": ("utf-16-le", codecs.BOM_UTF16_LE),
    "UTF-16 BE": ("utf-16-be", codecs.BOM_UTF16_BE),
    "ANSI": ("cp1252", b""),
}
EOLS = {
    "CRLF": ("\r\n", "Windows (CRLF)"),
    "LF": ("\n", "Unix (LF)"),
    "CR": ("\r", "Macintosh (CR)"),
}

ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 10, 500, 10
FILETYPES = [("Textdokumente (*.txt)", "*.txt"), ("Alle Dateien (*.*)", "*.*")]


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(rel):
    return os.path.join(getattr(sys, "_MEIPASS", app_dir()), rel)


def enable_dpi_awareness():
    if not IS_WIN:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def dark_titlebar(win):
    """Dunkle Windows-Titelleiste (Win10 ab 1809 / Win11)."""
    if not IS_WIN:
        return
    try:
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        on = ctypes.c_int(1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (neu / alt)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(on), ctypes.sizeof(on)) == 0:
                break
        # Windows 11: Titelleistenfarbe exakt auf Panel-Farbe setzen
        r, g, b = (int(C["panel"][i:i + 2], 16) for i in (1, 3, 5))
        color = ctypes.c_int(r | (g << 8) | (b << 16))
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 35, ctypes.byref(color), ctypes.sizeof(color))
    except Exception:
        pass


def work_area(widget, x, y):
    """Arbeitsbereich (ohne Taskleiste) des Monitors, auf dem (x, y) liegt."""
    if IS_WIN:
        try:
            from ctypes import wintypes

            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                            ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

            user32 = ctypes.windll.user32
            user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
            user32.MonitorFromPoint.restype = wintypes.HANDLE
            user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
            hmon = user32.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 2)
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
                r = info.rcWork
                return r.left, r.top, r.right, r.bottom
        except Exception:
            pass
    return 0, 0, widget.winfo_screenwidth(), widget.winfo_screenheight()


class FileDropTarget:
    """
    Nimmt per Drag & Drop aus dem Explorer gezogene Dateien an (WM_DROPFILES).
    Die Fensterprozeduren der Tk-Fenster werden dazu per ctypes umgeleitet.
    Im Callback wird bewusst kein Tk aufgerufen – die Dateien landen in einer
    Warteschlange, die das Hauptfenster regelmäßig abholt.
    """
    WM_DROPFILES = 0x0233
    WM_COPYDATA = 0x004A
    WM_COPYGLOBALDATA = 0x0049
    MSGFLT_ALLOW = 1
    GWLP_WNDPROC = -4

    def __init__(self):
        self.queue = []
        self._hooks = {}
        self.available = False
        if not IS_WIN:
            return
        try:
            from ctypes import wintypes
            lresult = ctypes.c_ssize_t
            self.WNDPROC = ctypes.WINFUNCTYPE(lresult, wintypes.HWND, wintypes.UINT,
                                              wintypes.WPARAM, wintypes.LPARAM)
            u = ctypes.WinDLL("user32", use_last_error=True)
            s = ctypes.WinDLL("shell32")
            self._set = getattr(u, "SetWindowLongPtrW", None) or u.SetWindowLongW
            self._set.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
            self._set.restype = ctypes.c_void_p
            self._call = u.CallWindowProcW
            self._call.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
                                   wintypes.WPARAM, wintypes.LPARAM]
            self._call.restype = lresult
            self._parent = u.GetParent
            self._parent.argtypes = [wintypes.HWND]
            self._parent.restype = wintypes.HWND
            self._filter = getattr(u, "ChangeWindowMessageFilterEx", None)
            if self._filter is not None:
                self._filter.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.DWORD,
                                         ctypes.c_void_p]
            self._accept = s.DragAcceptFiles
            self._accept.argtypes = [wintypes.HWND, wintypes.BOOL]
            self._query = s.DragQueryFileW
            self._query.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.c_wchar_p,
                                    wintypes.UINT]
            self._query.restype = wintypes.UINT
            self._finish = s.DragFinish
            self._finish.argtypes = [ctypes.c_void_p]
            self.available = True
        except Exception:
            self.available = False

    def register(self, widget, include_frame=False):
        """Fenster eines Tk-Widgets (optional samt äußerem Rahmenfenster) anmelden."""
        if not self.available:
            return
        try:
            widget.update_idletasks()
            hwnd = widget.winfo_id()
            self._hook(hwnd)
            if include_frame:
                outer = self._parent(hwnd)
                if outer:
                    self._hook(outer)
        except Exception:
            pass

    def _hook(self, hwnd):
        if not hwnd or hwnd in self._hooks:
            return
        self._accept(hwnd, True)
        if self._filter is not None:  # Drag & Drop auch bei "Als Administrator ausführen"
            for msg in (self.WM_DROPFILES, self.WM_COPYDATA, self.WM_COPYGLOBALDATA):
                try:
                    self._filter(hwnd, msg, self.MSGFLT_ALLOW, None)
                except Exception:
                    pass
        entry = {}

        def proc(h, msg, wparam, lparam):
            if msg == self.WM_DROPFILES:
                try:
                    self.queue.extend(self._read_drop(wparam))
                except Exception:
                    pass
                return 0
            return self._call(entry["old"], h, msg, wparam, lparam)

        cb = self.WNDPROC(proc)
        entry["cb"] = cb  # Referenz halten, sonst räumt Python den Callback weg
        entry["old"] = self._set(hwnd, self.GWLP_WNDPROC, ctypes.cast(cb, ctypes.c_void_p))
        self._hooks[hwnd] = entry

    def _read_drop(self, hdrop):
        files = []
        try:
            count = self._query(hdrop, 0xFFFFFFFF, None, 0)
            for i in range(count):
                length = self._query(hdrop, i, None, 0)
                buf = ctypes.create_unicode_buffer(length + 1)
                self._query(hdrop, i, buf, length + 1)
                files.append(buf.value)
        finally:
            self._finish(hdrop)
        return files

    def take(self):
        files, self.queue = self.queue, []
        return files


def decode_bytes(data):
    """Erkennt die Codierung wie der Windows-Editor und liefert (text, name)."""
    if data.startswith(codecs.BOM_UTF8):
        return data[3:].decode("utf-8", errors="replace"), "UTF-8 mit BOM"
    if data.startswith(codecs.BOM_UTF16_LE):
        return data[2:].decode("utf-16-le", errors="replace"), "UTF-16 LE"
    if data.startswith(codecs.BOM_UTF16_BE):
        return data[2:].decode("utf-16-be", errors="replace"), "UTF-16 BE"
    try:
        return data.decode("utf-8"), "UTF-8"
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace"), "ANSI"


def detect_eol(text):
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    cr = text.count("\r") - crlf
    if crlf == lf == cr == 0:
        return "CRLF"
    # Bei Gleichstand gewinnt CRLF, dann LF
    return max((crlf, 2, "CRLF"), (lf, 1, "LF"), (cr, 0, "CR"))[2]


def normalize_eol(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


# ---------------------------------------------------------------------------
# Einstellungen (menschenlesbare INI-Datei)
# ---------------------------------------------------------------------------
class Settings:
    DEFAULTS = {
        "font_family": "Consolas",
        "font_size": "11",
        "font_weight": "normal",
        "font_slant": "roman",
        "word_wrap": "0",
        "statusbar": "1",
        "zoom": "100",
        "geometry": "1000x640",
        "maximized": "0",
        "match_case": "0",
        "wrap_around": "0",
        "search_up": "0",
        "last_find": "",
        "last_replace": "",
    }

    def __init__(self):
        self.path = self._choose_path()
        self.cp = configparser.ConfigParser(interpolation=None)
        self.cp["editor"] = dict(self.DEFAULTS)
        try:
            self.cp.read(self.path, encoding="utf-8")
        except Exception:
            pass

    def _choose_path(self):
        name = APP_ID + ".ini"
        primary = os.path.join(app_dir(), name)
        if os.path.exists(primary) or self._writable(app_dir()):
            return primary
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        folder = os.path.join(base, APP_ID)
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception:
            pass
        return os.path.join(folder, name)

    @staticmethod
    def _writable(folder):
        probe = os.path.join(folder, ".schreibtest.tmp")
        try:
            with open(probe, "w"):
                pass
            os.remove(probe)
            return True
        except Exception:
            return False

    def get(self, key):
        return self.cp["editor"].get(key, self.DEFAULTS.get(key, ""))

    def getint(self, key, lo=None, hi=None):
        try:
            val = int(float(self.get(key)))
        except ValueError:
            val = int(self.DEFAULTS.get(key, "0"))
        if lo is not None:
            val = max(lo, val)
        if hi is not None:
            val = min(hi, val)
        return val

    def getbool(self, key):
        return self.get(key).strip().lower() in ("1", "true", "yes", "ja", "on")

    def set(self, key, value):
        if isinstance(value, bool):
            value = "1" if value else "0"
        self.cp["editor"][key] = str(value)

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                fh.write("; Einstellungen fuer %s v%s\n" % (APP_ID, APP_VERSION))
                fh.write("; Kann bei geschlossenem Editor von Hand bearbeitet werden.\n")
                fh.write("; word_wrap / statusbar / match_case ...: 1 = an, 0 = aus\n\n")
                self.cp.write(fh)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Dialog-Grundgerüst
# ---------------------------------------------------------------------------
class DarkDialog(tk.Toplevel):
    def __init__(self, parent, title):
        super().__init__(parent)
        self.withdraw()
        self.parent_win = parent
        self.title(title)
        self.configure(bg=C["panel"])
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda e: self.close())
        self.body = ttk.Frame(self, style="Dlg.TFrame", padding=(16, 14, 16, 14))
        self.body.pack(fill="both", expand=True)
        # dünne Akzentlinie oben – Dashboard-Optik
        tk.Frame(self, bg=C["accent"], height=1).place(x=0, y=0, relwidth=1)

    def present(self, modal=True, focus=None):
        self.update_idletasks()
        p = self.parent_win
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = p.winfo_rootx() + (p.winfo_width() - w) // 2
        y = p.winfo_rooty() + max(40, (p.winfo_height() - h) // 3)
        self.geometry("+%d+%d" % (max(0, x), max(0, y)))
        dark_titlebar(self)
        self.deiconify()
        self.lift()
        if focus is not None:
            focus.focus_set()
        if modal:
            try:
                self.grab_set()
            except tk.TclError:
                pass
            self.wait_window(self)

    def close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


class MessageDialog(DarkDialog):
    """Dunkle Meldung mit frei wählbaren Schaltflächen."""

    def __init__(self, parent, title, message, buttons, default=None,
                 cancel=None, kind="info"):
        super().__init__(parent, title)
        self.result = cancel
        row = ttk.Frame(self.body, style="Dlg.TFrame")
        row.pack(fill="x")
        icon = tk.Canvas(row, width=30, height=30, bg=C["panel"],
                         highlightthickness=0, bd=0)
        color = {"warn": C["amber"], "error": C["danger"]}.get(kind, C["accent"])
        icon.create_oval(3, 3, 27, 27, outline=color, width=2)
        icon.create_text(15, 15, text="!" if kind in ("warn", "error") else "i",
                         fill=color, font=(UI_FAMILY, 11, "bold"))
        icon.pack(side="left", anchor="n", padx=(0, 14))
        ttk.Label(row, text=message, style="Msg.TLabel", wraplength=380,
                  justify="left").pack(side="left", fill="x", anchor="w", pady=(4, 0))

        bar = ttk.Frame(self.body, style="Dlg.TFrame")
        bar.pack(fill="x", pady=(20, 0))
        first = None
        for label, key in reversed(buttons):
            style = "Accent.TButton" if key == default else "TButton"
            b = ttk.Button(bar, text=label, style=style,
                           command=lambda k=key: self._done(k))
            b.pack(side="right", padx=(8, 0))
            if key == default:
                first = b
        self.bind("<Return>", lambda e: self._done(default) if default else None)
        self.cancel_key = cancel
        self.present(modal=True, focus=first)

    def _done(self, key):
        self.result = key
        self.close()


def show_message(parent, message, title=APP_TITLE, kind="info"):
    MessageDialog(parent, title, message, [("OK", "ok")], default="ok",
                  cancel="ok", kind=kind)


def ask(parent, message, buttons, default, cancel, title=APP_TITLE, kind="warn"):
    return MessageDialog(parent, title, message, buttons, default=default,
                         cancel=cancel, kind=kind).result


# ---------------------------------------------------------------------------
# Suchen / Ersetzen
# ---------------------------------------------------------------------------
class FindReplaceDialog(DarkDialog):
    def __init__(self, app, replace=False):
        super().__init__(app.root, "Ersetzen" if replace else "Suchen")
        self.app = app
        self.replace_mode = replace
        b = self.body
        b.columnconfigure(1, weight=1)

        ttk.Label(b, text="Suchen nach:", style="Dlg.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 10), pady=3)
        self.e_find = ttk.Entry(b, textvariable=app.find_var, width=34)
        self.e_find.grid(row=0, column=1, sticky="ew", pady=3)

        r = 1
        if replace:
            ttk.Label(b, text="Ersetzen durch:", style="Dlg.TLabel").grid(
                row=1, column=0, sticky="w", padx=(0, 10), pady=3)
            self.e_repl = ttk.Entry(b, textvariable=app.replace_var, width=34)
            self.e_repl.grid(row=1, column=1, sticky="ew", pady=3)
            r = 2

        opts = ttk.Frame(b, style="Dlg.TFrame")
        opts.grid(row=r, column=0, columnspan=2, sticky="w", pady=(12, 0))
        ttk.Checkbutton(opts, text="Groß-/Kleinschreibung",
                        variable=app.match_case).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(opts, text="Umbrechen",
                        variable=app.wrap_around).grid(row=1, column=0, sticky="w", pady=(4, 0))
        if not replace:
            dirf = ttk.LabelFrame(opts, text=" Richtung ", padding=(10, 4, 10, 6))
            dirf.grid(row=0, column=1, rowspan=2, sticky="w", padx=(22, 0))
            ttk.Radiobutton(dirf, text="Nach oben", value="up",
                            variable=app.direction).pack(side="left")
            ttk.Radiobutton(dirf, text="Nach unten", value="down",
                            variable=app.direction).pack(side="left", padx=(10, 0))

        btns = ttk.Frame(b, style="Dlg.TFrame")
        btns.grid(row=0, column=2, rowspan=r + 1, sticky="n", padx=(14, 0))
        self.b_next = ttk.Button(btns, text="Weitersuchen", style="Accent.TButton",
                                 command=self.find_next, width=14)
        self.b_next.pack(fill="x", pady=(2, 4))
        self.action_buttons = [self.b_next]
        if replace:
            br = ttk.Button(btns, text="Ersetzen", command=self.replace_one, width=14)
            br.pack(fill="x", pady=4)
            ba = ttk.Button(btns, text="Alle ersetzen", command=self.replace_all, width=14)
            ba.pack(fill="x", pady=4)
            self.action_buttons += [br, ba]
        ttk.Button(btns, text="Abbrechen", command=self.close, width=14).pack(fill="x", pady=4)

        self.bind("<Return>", lambda e: self.find_next())
        self.bind("<F3>", lambda e: self.find_next())
        self._trace = app.find_var.trace_add("write", lambda *a: self._update_buttons())
        self._update_buttons()
        self.present(modal=False, focus=self.e_find)
        self.e_find.select_range(0, "end")

    def _update_buttons(self):
        state = "!disabled" if self.app.find_var.get() else "disabled"
        for btn in self.action_buttons:
            btn.state([state])

    def find_next(self):
        if not self.app.find_var.get():
            return
        up = (not self.replace_mode) and self.app.direction.get() == "up"
        self.app.search(backwards=up, parent=self)

    def replace_one(self):
        self.app.replace_current(parent=self)

    def replace_all(self):
        self.app.replace_all()

    def close(self):
        try:
            self.app.find_var.trace_remove("write", self._trace)
        except Exception:
            pass
        self.app.find_dialog = None
        super().close()
        self.app.text.focus_set()


class GotoDialog(DarkDialog):
    def __init__(self, app):
        super().__init__(app.root, "Gehe zu Zeile")
        self.app = app
        ttk.Label(self.body, text="Zeilennummer:", style="Dlg.TLabel").pack(anchor="w")
        cur = app.text.index("insert").split(".")[0]
        self.var = tk.StringVar(value=cur)
        vcmd = (self.register(lambda s: s.isdigit() or s == ""), "%P")
        self.entry = ttk.Entry(self.body, textvariable=self.var, width=36,
                               validate="key", validatecommand=vcmd)
        self.entry.pack(fill="x", pady=(4, 16))
        bar = ttk.Frame(self.body, style="Dlg.TFrame")
        bar.pack(fill="x")
        ttk.Button(bar, text="Abbrechen", command=self.close).pack(side="right")
        ttk.Button(bar, text="Gehe zu", style="Accent.TButton",
                   command=self.go).pack(side="right", padx=(0, 8))
        self.bind("<Return>", lambda e: self.go())
        self.entry.select_range(0, "end")
        self.present(modal=True, focus=self.entry)

    def go(self):
        try:
            line = int(self.var.get())
        except ValueError:
            line = 0
        total = int(self.app.text.index("end-1c").split(".")[0])
        if line < 1 or line > total:
            show_message(self, "Die Zeilennummer liegt außerhalb des gültigen Bereichs.",
                         title="Editor – Gehe zu Zeile", kind="warn")
            self.entry.focus_set()
            return
        t = self.app.text
        t.tag_remove("sel", "1.0", "end")
        t.mark_set("insert", "%d.0" % line)
        t.see("insert")
        self.close()
        t.focus_set()


class FontDialog(DarkDialog):
    STYLES = [("Standard", "normal", "roman"), ("Kursiv", "normal", "italic"),
              ("Fett", "bold", "roman"), ("Fett Kursiv", "bold", "italic")]
    SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72]

    def __init__(self, app):
        super().__init__(app.root, "Schriftart")
        self.app = app
        self.result = None
        fam = app.base_font["family"]
        size = app.base_size
        style_name = next((n for n, w, s in self.STYLES
                           if w == app.base_font["weight"] and s == app.base_font["slant"]),
                          "Standard")
        self.families = sorted({f for f in tkfont.families(app.root) if not f.startswith("@")},
                               key=str.lower)

        self.v_fam = tk.StringVar(value=fam)
        self.v_style = tk.StringVar(value=style_name)
        self.v_size = tk.StringVar(value=str(size))

        cols = ttk.Frame(self.body, style="Dlg.TFrame")
        cols.pack(fill="both", expand=True)
        self.lb_fam = self._column(cols, 0, "Schriftart:", self.v_fam, self.families, 26)
        self.lb_style = self._column(cols, 1, "Schriftschnitt:", self.v_style,
                                     [n for n, _, _ in self.STYLES], 14)
        self.lb_size = self._column(cols, 2, "Schriftgrad:", self.v_size,
                                    [str(s) for s in self.SIZES], 7)

        prev = ttk.LabelFrame(self.body, text=" Beispiel ", padding=(10, 6))
        prev.pack(fill="x", pady=(14, 0))
        self.preview_font = tkfont.Font(family=fam, size=size)
        tk.Label(prev, text="AaBbYyZz  ÄäÖöÜüß 0123", font=self.preview_font,
                 bg=C["editor"], fg=C["text"], height=2, anchor="center").pack(fill="x")

        bar = ttk.Frame(self.body, style="Dlg.TFrame")
        bar.pack(fill="x", pady=(16, 0))
        ttk.Button(bar, text="Abbrechen", command=self.close).pack(side="right")
        ttk.Button(bar, text="OK", style="Accent.TButton",
                   command=self.ok).pack(side="right", padx=(0, 8))

        for v in (self.v_fam, self.v_style, self.v_size):
            v.trace_add("write", lambda *a: self._update_preview())
        self.bind("<Return>", lambda e: self.ok())
        self._update_preview()
        self.present(modal=True)

    def _column(self, parent, col, label, var, items, width):
        f = ttk.Frame(parent, style="Dlg.TFrame")
        f.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 10, 0))
        ttk.Label(f, text=label, style="Dlg.TLabel").pack(anchor="w")
        e = ttk.Entry(f, textvariable=var, width=width)
        e.pack(fill="x", pady=(4, 0))
        holder = tk.Frame(f, bg=C["border"], bd=0)
        holder.pack(fill="both", expand=True)
        lb = tk.Listbox(holder, height=8, width=width, exportselection=False,
                        bg=C["editor"], fg=C["text"], selectbackground=C["sel"],
                        selectforeground=C["text"], highlightthickness=0, bd=0,
                        relief="flat", activestyle="none", font=UI_FONT)
        sb = ttk.Scrollbar(holder, orient="vertical", command=lb.yview,
                           style="Dark.Vertical.TScrollbar")
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True, padx=(1, 0), pady=1)
        sb.pack(side="right", fill="y", pady=1, padx=(0, 1))
        for it in items:
            lb.insert("end", it)

        def on_select(_e=None):
            sel = lb.curselection()
            if sel:
                var.set(lb.get(sel[0]))

        def sync(*_a):
            val = var.get().lower()
            for i, it in enumerate(items):
                if it.lower() == val or (it.lower().startswith(val) and val):
                    lb.selection_clear(0, "end")
                    lb.selection_set(i)
                    lb.see(i)
                    break

        lb.bind("<<ListboxSelect>>", on_select)
        sync()
        e.bind("<KeyRelease>", sync)
        return lb

    def _values(self):
        fam = self.v_fam.get().strip()
        match = next((f for f in self.families if f.lower() == fam.lower()), None)
        try:
            size = int(float(self.v_size.get()))
        except ValueError:
            size = None
        st = next((s for s in self.STYLES if s[0] == self.v_style.get()), None)
        return match, size, st

    def _update_preview(self):
        fam, size, st = self._values()
        try:
            self.preview_font.configure(
                family=fam or self.app.base_font["family"],
                size=max(1, min(size or self.app.base_size, 72)),
                weight=st[1] if st else "normal", slant=st[2] if st else "roman")
        except tk.TclError:
            pass

    def ok(self):
        fam, size, st = self._values()
        if fam is None:
            show_message(self, "Es gibt keine Schriftart mit diesem Namen.\n"
                               "Wählen Sie eine Schriftart aus der Liste aus.",
                         title="Schriftart", kind="warn")
            return
        if size is None or not 1 <= size <= 999:
            show_message(self, "Der Schriftgrad muss eine Zahl zwischen 1 und 999 sein.",
                         title="Schriftart", kind="warn")
            return
        if st is None:
            st = self.STYLES[0]
        self.result = (fam, size, st[1], st[2])
        self.close()


class AboutDialog(DarkDialog):
    def __init__(self, app):
        super().__init__(app.root, "Info über Editor")
        head = ttk.Frame(self.body, style="Dlg.TFrame")
        head.pack(fill="x")
        dot = tk.Canvas(head, width=14, height=14, bg=C["panel"], highlightthickness=0)
        dot.create_oval(2, 2, 12, 12, fill=C["accent"], outline=C["accent"])
        dot.pack(side="left", padx=(0, 10))
        ttk.Label(head, text="Editor", style="Title.TLabel").pack(side="left")
        ttk.Label(head, text="  Darkmode", style="TitleDim.TLabel").pack(side="left")
        tk.Frame(self.body, bg=C["border"], height=1).pack(fill="x", pady=12)
        info = ("%s\nVersion %s\n\n"
                "Nachbau des Windows-10-Editors mit dunkler Oberfläche.\n"
                "Python %s · Tk %s\n\n"
                "Einstellungen:\n%s") % (APP_ID, APP_VERSION,
                                          sys.version.split()[0], tk.TkVersion,
                                          app.settings.path)
        ttk.Label(self.body, text=info, style="Msg.TLabel", justify="left",
                  wraplength=420).pack(anchor="w")
        bar = ttk.Frame(self.body, style="Dlg.TFrame")
        bar.pack(fill="x", pady=(16, 0))
        b = ttk.Button(bar, text="OK", style="Accent.TButton", command=self.close)
        b.pack(side="right")
        self.bind("<Return>", lambda e: self.close())
        self.present(modal=True, focus=b)


# ---------------------------------------------------------------------------
# Eigene Dropdown-Menüs (komplett dunkel, ohne weißen Windows-Rahmen)
# ---------------------------------------------------------------------------
class DarkMenu:
    """Beschreibung eines Menüs – angezeigt wird es vom MenuManager."""

    def __init__(self):
        self.items = []

    def add_command(self, label, command=None, accelerator=""):
        self.items.append({"kind": "command", "label": label, "command": command,
                           "accel": accelerator, "state": "normal"})

    def add_checkbutton(self, label, variable, command=None, accelerator=""):
        self.items.append({"kind": "check", "label": label, "variable": variable,
                           "command": command, "accel": accelerator, "state": "normal"})

    def add_radiobutton(self, label, value, variable, command=None):
        self.items.append({"kind": "radio", "label": label, "value": value,
                           "variable": variable, "command": command, "accel": "",
                           "state": "normal"})

    def add_cascade(self, label, menu):
        self.items.append({"kind": "cascade", "label": label, "menu": menu, "accel": "",
                           "state": "normal"})

    def add_separator(self):
        self.items.append({"kind": "sep"})

    def entryconfigure(self, label, state=None):
        for it in self.items:
            if it.get("label") == label and state is not None:
                it["state"] = state


class MenuView:
    """Ein geöffnetes Menüfenster."""

    def __init__(self, mgr, menu):
        self.mgr = mgr
        self.menu = menu
        self.rows = []
        self.active = None
        self.sub = None
        win = self.win = tk.Toplevel(mgr.root)
        win.withdraw()
        win.overrideredirect(True)
        win.configure(bg=C["border"], bd=0, highlightthickness=0)
        try:
            win.attributes("-topmost", True)
        except tk.TclError:
            pass
        inner = tk.Frame(win, bg=C["card"], bd=0, highlightthickness=0)
        inner.pack(padx=1, pady=1, fill="both", expand=True)  # 1 px Rahmen in Border-Farbe
        inner.columnconfigure(1, weight=1, minsize=110)
        tk.Frame(inner, bg=C["card"], height=4).grid(row=0, column=0, columnspan=4)
        r = 1
        for it in menu.items:
            if it["kind"] == "sep":
                tk.Frame(inner, bg=C["border"], height=1).grid(
                    row=r, column=0, columnspan=4, sticky="ew", padx=10, pady=4)
                r += 1
                continue
            disabled = it.get("state") == "disabled"
            fg = C["faint"] if disabled else C["text"]
            mark, mark_font = "", UI_FONT
            if it["kind"] == "check" and it["variable"].get():
                mark = "✓"
            elif it["kind"] == "radio" and it["variable"].get() == it["value"]:
                mark, mark_font = "●", (UI_FAMILY, 7)
            cells = [
                tk.Label(inner, text=mark, font=mark_font, width=3, anchor="center",
                         fg=C["faint"] if disabled else C["accent"]),
                tk.Label(inner, text=it["label"], font=UI_FONT, anchor="w", fg=fg,
                         padx=2, pady=4),
                tk.Label(inner, text=it.get("accel", ""), font=UI_FONT, anchor="e",
                         fg=C["faint"] if disabled else C["dim"], padx=12),
                tk.Label(inner, text="›" if it["kind"] == "cascade" else "",
                         font=(UI_FAMILY, 10), width=2, anchor="w", fg=fg),
            ]
            row = {"item": it, "cells": cells, "disabled": disabled}
            for col, cell in enumerate(cells):
                cell.configure(bg=C["card"], bd=0, highlightthickness=0)
                cell.grid(row=r, column=col, sticky="nsew")
                cell._menu_row = row
                cell._menu_view = self
            self.rows.append(row)
            r += 1
        tk.Frame(inner, bg=C["card"], height=4).grid(row=r, column=0, columnspan=4)

    def show(self, x, y, flip_y=None, alt_x=None):
        """Zeigt das Menü bei (x, y) und hält es innerhalb des Monitors."""
        w = self.win
        w.update_idletasks()
        width, height = w.winfo_reqwidth(), w.winfo_reqheight()
        left, top, right, bottom = work_area(w, x, y)
        if x + width > right:
            x = (alt_x - width) if alt_x is not None else right - width
        if y + height > bottom:
            y = (flip_y - height) if flip_y is not None else bottom - height
        x, y = max(left, x), max(top, y)
        w.geometry("+%d+%d" % (x, y))
        w.deiconify()
        w.lift()

    def set_active(self, row):
        if row is self.active:
            return
        if self.active is not None:
            for c in self.active["cells"]:
                c.configure(bg=C["card"])
        self.active = row
        if row is not None:
            bg = C["hover"] if row["disabled"] else C["sel"]
            for c in row["cells"]:
                c.configure(bg=bg)

    def move(self, step):
        if not self.rows:
            return
        if self.active is None:
            idx = 0 if step > 0 else len(self.rows) - 1
        else:
            idx = (self.rows.index(self.active) + step) % len(self.rows)
        self.set_active(self.rows[idx])

    def destroy(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass


class MenuManager:
    """Öffnet/schließt Menüs, Maus- und Tastatursteuerung wie unter Windows."""

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.chain = []
        self.bar_index = None
        self._job = None

    @property
    def is_open(self):
        return bool(self.chain)

    # -- Öffnen ---------------------------------------------------------
    def open_bar(self, idx, keyboard=False):
        self.close_all(refocus=False)
        lbl, menu, before = self.app.menu_labels[idx]
        if before:
            before()
        self.bar_index = idx
        lbl.configure(bg=C["pressed"])
        x = lbl.winfo_rootx()
        y = lbl.winfo_rooty() + lbl.winfo_height()
        self._open_root(menu, x, y, flip_y=lbl.winfo_rooty(), keyboard=keyboard)

    def popup(self, menu, x, y, above=False):
        self.close_all(refocus=False)
        view = MenuView(self, menu)
        if above:
            view.win.update_idletasks()
            y -= view.win.winfo_reqheight()
        self._start(view, x, y, flip_y=y)

    def _open_root(self, menu, x, y, flip_y=None, keyboard=False):
        view = MenuView(self, menu)
        self._start(view, x, y, flip_y=flip_y)
        if keyboard:
            view.move(1)

    def _start(self, view, x, y, flip_y=None):
        self.chain = [view]
        self._bind(view)
        view.show(x, y, flip_y=flip_y)
        self._grab(view, 0)

    def _grab(self, view, tries):
        if view not in self.chain:
            return
        try:
            view.win.grab_set()
            view.win.focus_force()
        except tk.TclError:
            if tries < 10:
                view.win.after(20, lambda: self._grab(view, tries + 1))

    def _open_sub(self, view, row, keyboard=False):
        self._cancel_job()
        self._close_after(view)
        if row["disabled"] or row["item"]["kind"] != "cascade":
            return
        sub = MenuView(self, row["item"]["menu"])
        self._bind(sub)
        cell = row["cells"][0]
        sub.show(view.win.winfo_rootx() + view.win.winfo_width() - 3,
                 cell.winfo_rooty() - 5, alt_x=view.win.winfo_rootx() + 3)
        view.sub = sub
        self.chain.append(sub)
        if keyboard:
            sub.move(1)

    # -- Schließen ------------------------------------------------------
    def _close_after(self, view):
        while self.chain and self.chain[-1] is not view:
            self.chain.pop().destroy()
        view.sub = None

    def close_all(self, refocus=True):
        self._cancel_job()
        had = bool(self.chain)
        for v in reversed(self.chain):
            v.destroy()
        self.chain = []
        if self.bar_index is not None:
            try:
                self.app.menu_labels[self.bar_index][0].configure(bg=C["panel"])
            except tk.TclError:
                pass
        self.bar_index = None
        if had and refocus:
            try:
                self.app.text.focus_set()
            except tk.TclError:
                pass

    def _cancel_job(self):
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None

    # -- Ereignisse -----------------------------------------------------
    def _bind(self, view):
        w = view.win
        w.bind("<Motion>", self._on_motion)
        w.bind("<ButtonPress-1>", self._on_press)
        w.bind("<ButtonPress-3>", self._on_press)
        w.bind("<ButtonRelease-1>", self._on_release)
        w.bind("<FocusOut>", lambda e: self.root.after(80, self._check_focus))
        for key, fn in (("<Down>", lambda: self._key_move(1)), ("<Up>", lambda: self._key_move(-1)),
                        ("<Right>", self._key_right), ("<Left>", self._key_left),
                        ("<Return>", self._key_enter), ("<KP_Enter>", self._key_enter),
                        ("<space>", self._key_enter), ("<Escape>", self._key_escape),
                        ("<F10>", self.close_all)):
            w.bind(key, lambda e, f=fn: (f(), "break")[1])

    def _widget_at(self, x, y):
        try:
            return self.root.winfo_containing(x, y)
        except (KeyError, tk.TclError):
            return None

    @staticmethod
    def _row_of(widget):
        while widget is not None:
            if hasattr(widget, "_menu_row"):
                return widget._menu_row, widget._menu_view
            widget = getattr(widget, "master", None)
        return None, None

    def _bar_index_of(self, widget):
        for i, (lbl, _m, _b) in enumerate(self.app.menu_labels):
            if widget is lbl:
                return i
        return None

    def _in_menu(self, widget):
        while widget is not None:
            if any(widget is v.win for v in self.chain):
                return True
            widget = getattr(widget, "master", None)
        return False

    def _on_motion(self, e):
        if not self.chain:
            return
        w = self._widget_at(e.x_root, e.y_root)
        row, view = self._row_of(w)
        if row is not None and view in self.chain:
            if view.active is not row:
                view.set_active(row)
                self._cancel_job()
                if view.sub is not None:
                    self._close_after(view)
                if row["item"]["kind"] == "cascade" and not row["disabled"]:
                    self._job = self.root.after(180, lambda: self._open_sub(view, row))
            return
        idx = self._bar_index_of(w)
        if idx is not None and self.bar_index is not None and idx != self.bar_index:
            self.open_bar(idx)

    def _on_press(self, e):
        w = self._widget_at(e.x_root, e.y_root)
        if self._in_menu(w):
            return "break"
        idx = self._bar_index_of(w)
        if idx is not None and idx != self.bar_index:
            self.open_bar(idx)
        else:
            self.close_all()
        return "break"

    def _on_release(self, e):
        w = self._widget_at(e.x_root, e.y_root)
        row, view = self._row_of(w)
        if row is None or view not in self.chain:
            return "break"
        self._activate(view, row, keyboard=False)
        return "break"

    def _activate(self, view, row, keyboard):
        if row["disabled"]:
            return
        it = row["item"]
        if it["kind"] == "cascade":
            self._open_sub(view, row, keyboard=keyboard)
            return
        self.close_all()

        def run():
            if it["kind"] == "check":
                it["variable"].set(not it["variable"].get())
            elif it["kind"] == "radio":
                it["variable"].set(it["value"])
            if it.get("command"):
                it["command"]()

        self.root.after_idle(run)

    def _check_focus(self):
        if not self.chain:
            return
        try:
            f = self.root.focus_get()
        except (KeyError, tk.TclError):
            f = None
        if f is None or not self._in_menu(f):
            self.close_all(refocus=False)

    # -- Tastatur -------------------------------------------------------
    def _key_move(self, step):
        if self.chain:
            self.chain[-1].move(step)

    def _key_right(self):
        if not self.chain:
            return
        v = self.chain[-1]
        if v.active is not None and v.active["item"]["kind"] == "cascade":
            self._open_sub(v, v.active, keyboard=True)
        elif self.bar_index is not None:
            self.open_bar((self.bar_index + 1) % len(self.app.menu_labels), keyboard=True)

    def _key_left(self):
        if len(self.chain) > 1:
            self._close_after(self.chain[-2])
        elif self.bar_index is not None:
            self.open_bar((self.bar_index - 1) % len(self.app.menu_labels), keyboard=True)

    def _key_enter(self):
        if self.chain and self.chain[-1].active is not None:
            self._activate(self.chain[-1], self.chain[-1].active, keyboard=True)

    def _key_escape(self):
        if len(self.chain) > 1:
            self._close_after(self.chain[-2])
        else:
            self.close_all()


# ---------------------------------------------------------------------------
# Hauptfenster
# ---------------------------------------------------------------------------
class EditorApp:
    def __init__(self, root, path=None):
        self.root = root
        self.settings = Settings()
        self.path = None
        self.encoding = "UTF-8"
        self.eol = "CRLF"
        self.find_dialog = None
        self._last_state = None
        self.menus = MenuManager(self)
        self.drop = FileDropTarget()

        s = self.settings
        self.zoom = s.getint("zoom", ZOOM_MIN, ZOOM_MAX)
        self.base_size = s.getint("font_size", 1, 999)
        family = s.get("font_family")
        if family not in tkfont.families(root):
            family = MONO_FAMILY if MONO_FAMILY in tkfont.families(root) else "Courier New"
        self.base_font = {
            "family": family,
            "weight": "bold" if s.get("font_weight") == "bold" else "normal",
            "slant": "italic" if s.get("font_slant") == "italic" else "roman",
        }
        self.font = tkfont.Font(root=root, **self.base_font, size=self._zoomed_size())

        # Variablen für Menüs und Suche
        self.v_wrap = tk.BooleanVar(value=s.getbool("word_wrap"))
        self.v_status = tk.BooleanVar(value=s.getbool("statusbar"))
        self.v_encoding = tk.StringVar(value=self.encoding)
        self.v_eol = tk.StringVar(value=self.eol)
        self.find_var = tk.StringVar(value=s.get("last_find"))
        self.replace_var = tk.StringVar(value=s.get("last_replace"))
        self.match_case = tk.BooleanVar(value=s.getbool("match_case"))
        self.wrap_around = tk.BooleanVar(value=s.getbool("wrap_around"))
        self.direction = tk.StringVar(value="up" if s.getbool("search_up") else "down")

        self._setup_window()
        self._setup_style()
        self._build_menubar()
        self._build_editor()
        self._build_statusbar()
        self._build_menus()
        self._bind_keys()
        self.apply_wrap()
        self.apply_statusbar()
        self._apply_tabs()
        # Dateien per Drag & Drop auf das Fenster ziehen
        self.drop.register(self.root, include_frame=True)
        self.drop.register(self.text)
        self.drop.register(self.statusbar)

        if path:
            # erst nach dem Anzeigen des Fensters öffnen (Rückfragen brauchen ein sichtbares Fenster)
            self.root.after(60, lambda: self._open_from_cmdline(path))
        self.text.edit_modified(False)
        self.text.focus_set()
        self._poll()

    # ---------------------------------------------------------------- Fenster
    def _setup_window(self):
        r = self.root
        r.title("Unbenannt - " + APP_TITLE)
        r.configure(bg=C["bg"])
        r.minsize(360, 220)
        r.geometry(self.settings.get("geometry"))
        if self.settings.getbool("maximized") and IS_WIN:
            r.state("zoomed")
        ico = resource_path(os.path.join("assets", "editor.ico"))
        if IS_WIN and os.path.exists(ico):
            try:
                r.iconbitmap(default=ico)
            except tk.TclError:
                pass
        r.protocol("WM_DELETE_WINDOW", self.exit_app)

    def _setup_style(self):
        st = ttk.Style(self.root)
        st.theme_use("clam")
        st.configure(".", background=C["panel"], foreground=C["text"],
                     fieldbackground=C["editor"], bordercolor=C["border"],
                     lightcolor=C["panel"], darkcolor=C["panel"],
                     troughcolor=C["editor"], focuscolor=C["accent"],
                     selectbackground=C["sel"], selectforeground=C["text"],
                     insertcolor=C["amber"], font=UI_FONT)
        st.configure("Dlg.TFrame", background=C["panel"])
        st.configure("Dlg.TLabel", background=C["panel"], foreground=C["text"])
        st.configure("Msg.TLabel", background=C["panel"], foreground=C["text"], font=UI_FONT_MSG)
        st.configure("Title.TLabel", background=C["panel"], foreground=C["text"],
                     font=(UI_FAMILY, 15, "bold"))
        st.configure("TitleDim.TLabel", background=C["panel"], foreground=C["dim"],
                     font=(UI_FAMILY, 15))

        st.configure("TButton", background=C["card"], foreground=C["text"],
                     bordercolor=C["border"], lightcolor=C["card"], darkcolor=C["card"],
                     padding=(14, 5), focusthickness=1, focuscolor=C["border"])
        st.map("TButton",
               background=[("disabled", C["panel"]), ("pressed", C["pressed"]),
                           ("active", C["hover"])],
               foreground=[("disabled", C["faint"])],
               bordercolor=[("focus", C["accent"])],
               lightcolor=[("pressed", C["pressed"]), ("active", C["hover"])],
               darkcolor=[("pressed", C["pressed"]), ("active", C["hover"])])
        st.configure("Accent.TButton", background=C["accent_soft"], foreground=C["accent"],
                     bordercolor=C["accent"], lightcolor=C["accent_soft"],
                     darkcolor=C["accent_soft"])
        st.map("Accent.TButton",
               background=[("disabled", C["panel"]), ("pressed", "#1f4c46"),
                           ("active", "#1b433d")],
               foreground=[("disabled", C["faint"])],
               bordercolor=[("disabled", C["border"])],
               lightcolor=[("active", "#1b433d")], darkcolor=[("active", "#1b433d")])

        st.configure("TEntry", fieldbackground=C["editor"], foreground=C["text"],
                     bordercolor=C["border"], lightcolor=C["editor"],
                     darkcolor=C["editor"], insertcolor=C["amber"], padding=(6, 4))
        st.map("TEntry", bordercolor=[("focus", C["accent"])],
               lightcolor=[("focus", C["editor"])])

        for w in ("TCheckbutton", "TRadiobutton"):
            st.configure(w, background=C["panel"], foreground=C["text"],
                         indicatorbackground=C["editor"], indicatorforeground=C["accent"],
                         upperbordercolor=C["border"], lowerbordercolor=C["border"],
                         focuscolor=C["panel"])
            st.map(w, background=[("active", C["panel"])],
                   indicatorbackground=[("pressed", C["hover"]), ("selected", C["editor"])],
                   upperbordercolor=[("selected", C["accent"])],
                   lowerbordercolor=[("selected", C["accent"])])

        st.configure("TLabelframe", background=C["panel"], bordercolor=C["border"],
                     lightcolor=C["panel"], darkcolor=C["panel"])
        st.configure("TLabelframe.Label", background=C["panel"], foreground=C["dim"])

        # Schmale, pfeillose Scrollbalken
        for orient in ("Vertical", "Horizontal"):
            name = "Dark.%s.TScrollbar" % orient
            st.layout(name, [("%s.Scrollbar.trough" % orient, {
                "sticky": "nswe",
                "children": [("%s.Scrollbar.thumb" % orient,
                              {"expand": "1", "sticky": "nswe"})]})])
            st.configure(name, troughcolor=C["editor"], background=C["thumb"],
                         bordercolor=C["editor"], lightcolor=C["thumb"],
                         darkcolor=C["thumb"], arrowsize=12, gripcount=0)
            st.map(name,
                   background=[("pressed", C["accent"]), ("active", C["thumb_hover"])],
                   lightcolor=[("pressed", C["accent"]), ("active", C["thumb_hover"])],
                   darkcolor=[("pressed", C["accent"]), ("active", C["thumb_hover"])])

    # ---------------------------------------------------------------- Aufbau
    def _build_menubar(self):
        self.menubar = tk.Frame(self.root, bg=C["panel"], bd=0, highlightthickness=0)
        self.menubar.pack(side="top", fill="x")
        tk.Frame(self.root, bg=C["border"], height=1).pack(side="top", fill="x")
        self.menu_labels = []

    def _add_menubar_entry(self, text, underline, menu, before_post=None):
        lbl = tk.Label(self.menubar, text=text, underline=underline, bg=C["panel"],
                       fg=C["text"], font=UI_FONT, padx=9, pady=4, bd=0)
        lbl.pack(side="left")
        idx = len(self.menu_labels)
        self.menu_labels.append((lbl, menu, before_post))
        lbl.bind("<Enter>", lambda e: lbl.configure(bg=C["hover"]))
        lbl.bind("<Leave>", lambda e: self.menus.bar_index != idx and lbl.configure(bg=C["panel"]))
        lbl.bind("<Button-1>", lambda e, i=idx: self.open_menu(i))

    def open_menu(self, idx, keyboard=False):
        if self.menus.bar_index == idx:
            self.menus.close_all()
        else:
            self.menus.open_bar(idx, keyboard=keyboard)
        return "break"

    def _build_editor(self):
        frame = tk.Frame(self.root, bg=C["editor"], bd=0)
        frame.pack(side="top", fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.text = tk.Text(
            frame, wrap="none", undo=True, maxundo=-1, autoseparators=True,
            bg=C["editor"], fg=C["text"], insertbackground=C["amber"],
            insertwidth=2, insertofftime=500, insertontime=600,
            selectbackground=C["sel"], selectforeground=C["text"],
            inactiveselectbackground=C["sel_inactive"],
            relief="flat", bd=0, highlightthickness=0, padx=6, pady=4,
            font=self.font, exportselection=True)
        self.vscroll = ttk.Scrollbar(frame, orient="vertical", command=self.text.yview,
                                     style="Dark.Vertical.TScrollbar")
        self.hscroll = ttk.Scrollbar(frame, orient="horizontal", command=self.text.xview,
                                     style="Dark.Horizontal.TScrollbar")
        self.corner = tk.Frame(frame, bg=C["editor"], width=12, height=12)
        self.text.configure(yscrollcommand=self.vscroll.set, xscrollcommand=self.hscroll.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        self.vscroll.grid(row=0, column=1, sticky="ns")
        self.hscroll.grid(row=1, column=0, sticky="ew")
        self.corner.grid(row=1, column=1, sticky="nsew")

    def _build_statusbar(self):
        self.status_sep = tk.Frame(self.root, bg=C["border"], height=1)
        self.statusbar = tk.Frame(self.root, bg=C["panel"], bd=0)
        sb = self.statusbar
        self.dot = tk.Canvas(sb, width=10, height=10, bg=C["panel"], highlightthickness=0)
        self.dot_id = self.dot.create_oval(1, 1, 9, 9, fill=C["accent"], outline="")
        self.dot.pack(side="left", padx=(10, 6))
        self.lbl_state = tk.Label(sb, text="", bg=C["panel"], fg=C["dim"],
                                  font=STATUS_FONT, anchor="w")
        self.lbl_state.pack(side="left")

        def field(width, **kw):
            lbl = tk.Label(sb, text="", bg=C["panel"], fg=C["dim"], font=STATUS_FONT,
                           width=width, anchor="w", padx=8, pady=3, **kw)
            lbl.pack(side="right")
            tk.Frame(sb, bg=C["border"], width=1).pack(side="right", fill="y", pady=3)
            return lbl

        # von rechts nach links wie im Original: Codierung | Zeilenende | Zoom | Position
        self.lbl_enc = field(14)
        self.lbl_eol = field(15)
        self.lbl_zoom = field(6)
        self.lbl_pos = field(22)
        self.lbl_enc.bind("<Button-1>", lambda e: self._popup_above(self.m_enc, self.lbl_enc))
        self.lbl_eol.bind("<Button-1>", lambda e: self._popup_above(self.m_eol, self.lbl_eol))
        self.lbl_zoom.bind("<Button-1>", lambda e: self.zoom_reset())
        for lbl in (self.lbl_enc, self.lbl_eol, self.lbl_zoom):
            lbl.bind("<Enter>", lambda e: e.widget.configure(fg=C["text"], bg=C["hover"]))
            lbl.bind("<Leave>", lambda e: e.widget.configure(fg=C["dim"], bg=C["panel"]))

    @staticmethod
    def _menu(parent=None):
        return DarkMenu()

    def _build_menus(self):
        # Datei
        m = self.m_file = self._menu()
        m.add_command(label="Neu", accelerator="Strg+N", command=self.new_file)
        m.add_command(label="Neues Fenster", accelerator="Strg+Umschalt+N",
                      command=self.new_window)
        m.add_command(label="Öffnen...", accelerator="Strg+O", command=self.open_file)
        m.add_command(label="Speichern", accelerator="Strg+S", command=self.save)
        m.add_command(label="Speichern unter...", accelerator="Strg+Umschalt+S",
                      command=self.save_as)
        m.add_separator()
        m.add_command(label="Drucken...", accelerator="Strg+P", command=self.print_file)
        m.add_separator()
        m.add_command(label="Beenden", command=self.exit_app)

        # Bearbeiten
        m = self.m_edit = self._menu()
        m.add_command(label="Rückgängig", accelerator="Strg+Z", command=self.undo)
        m.add_command(label="Wiederholen", accelerator="Strg+Y", command=self.redo)
        m.add_separator()
        m.add_command(label="Ausschneiden", accelerator="Strg+X", command=self.cut)
        m.add_command(label="Kopieren", accelerator="Strg+C", command=self.copy)
        m.add_command(label="Einfügen", accelerator="Strg+V", command=self.paste)
        m.add_command(label="Löschen", accelerator="Entf", command=self.delete)
        m.add_separator()
        m.add_command(label="Mit Bing suchen...", accelerator="Strg+E", command=self.search_bing)
        m.add_command(label="Suchen...", accelerator="Strg+F", command=self.open_find)
        m.add_command(label="Weitersuchen", accelerator="F3", command=self.find_next)
        m.add_command(label="Vorheriges suchen", accelerator="Umschalt+F3",
                      command=self.find_previous)
        m.add_command(label="Ersetzen...", accelerator="Strg+H", command=self.open_replace)
        m.add_command(label="Gehe zu...", accelerator="Strg+G", command=self.goto_line)
        m.add_separator()
        m.add_command(label="Alles markieren", accelerator="Strg+A", command=self.select_all)
        m.add_command(label="Uhrzeit/Datum", accelerator="F5", command=self.insert_datetime)

        # Format
        m = self.m_format = self._menu()
        m.add_checkbutton(label="Zeilenumbruch", variable=self.v_wrap, command=self.apply_wrap)
        m.add_command(label="Schriftart...", command=self.choose_font)
        m.add_separator()
        self.m_enc = self._menu(m)
        for enc in ENCODINGS:
            self.m_enc.add_radiobutton(label=enc, value=enc, variable=self.v_encoding,
                                       command=self._encoding_changed)
        self.m_eol = self._menu(m)
        for key in ("CRLF", "LF", "CR"):
            self.m_eol.add_radiobutton(label=EOLS[key][1], value=key, variable=self.v_eol,
                                       command=self._eol_changed)
        m.add_cascade(label="Codierung", menu=self.m_enc)
        m.add_cascade(label="Zeilenende", menu=self.m_eol)

        # Ansicht
        m = self.m_view = self._menu()
        mz = self._menu(m)
        mz.add_command(label="Vergrößern", accelerator="Strg+Plus", command=self.zoom_in)
        mz.add_command(label="Verkleinern", accelerator="Strg+Minus", command=self.zoom_out)
        mz.add_command(label="Standardzoom wiederherstellen", accelerator="Strg+0",
                       command=self.zoom_reset)
        m.add_cascade(label="Zoom", menu=mz)
        m.add_checkbutton(label="Statusleiste", variable=self.v_status,
                          command=self.apply_statusbar)

        # Hilfe
        m = self.m_help = self._menu()
        m.add_command(label="Hilfe anzeigen", command=lambda: webbrowser.open(
            "https://www.bing.com/search?q=" +
            urllib.parse.quote("Hilfe zum Editor in Windows 10")))
        m.add_separator()
        m.add_command(label="Info über Editor", command=lambda: AboutDialog(self))

        self._add_menubar_entry("Datei", 0, self.m_file)
        self._add_menubar_entry("Bearbeiten", 0, self.m_edit, self._update_edit_menu)
        self._add_menubar_entry("Format", 1, self.m_format)
        self._add_menubar_entry("Ansicht", 0, self.m_view)
        self._add_menubar_entry("Hilfe", 0, self.m_help)

        # Kontextmenü
        m = self.m_ctx = self._menu()
        m.add_command(label="Rückgängig", command=self.undo)
        m.add_separator()
        m.add_command(label="Ausschneiden", command=self.cut)
        m.add_command(label="Kopieren", command=self.copy)
        m.add_command(label="Einfügen", command=self.paste)
        m.add_command(label="Löschen", command=self.delete)
        m.add_separator()
        m.add_command(label="Alles markieren", command=self.select_all)
        m.add_separator()
        m.add_command(label="Mit Bing suchen...", command=self.search_bing)

    def _update_edit_menu(self):
        has_sel = bool(self.text.tag_ranges("sel"))
        has_text = self.text.compare("end-1c", "!=", "1.0")
        has_clip = True
        try:
            self.root.clipboard_get()
        except tk.TclError:
            has_clip = False
        has_term = bool(self.find_var.get())
        for menu in (self.m_edit, self.m_ctx):
            for label, ok in (("Ausschneiden", has_sel), ("Kopieren", has_sel),
                              ("Löschen", has_sel), ("Mit Bing suchen...", has_sel),
                              ("Einfügen", has_clip)):
                self._set_state(menu, label, ok)
        for label, ok in (("Weitersuchen", has_term or has_text),
                          ("Vorheriges suchen", has_term or has_text),
                          ("Suchen...", has_text), ("Ersetzen...", True)):
            self._set_state(self.m_edit, label, ok)

    @staticmethod
    def _set_state(menu, label, enabled):
        try:
            menu.entryconfigure(label, state="normal" if enabled else "disabled")
        except tk.TclError:
            pass

    def _popup_above(self, menu, widget):
        self.menus.popup(menu, widget.winfo_rootx(), widget.winfo_rooty(), above=True)
        return "break"

    # ---------------------------------------------------------------- Tasten
    def _bind_keys(self):
        t = self.text

        def bind(seqs, func):
            for seq in seqs:
                t.bind(seq, lambda e, f=func: (f(e), "break")[1])

        def shift(e):
            return bool(e.state & 0x0001)

        bind(("<Control-n>", "<Control-N>"),
             lambda e: self.new_window() if shift(e) else self.new_file())
        bind(("<Control-o>", "<Control-O>"), lambda e: self.open_file())
        bind(("<Control-s>", "<Control-S>"),
             lambda e: self.save_as() if shift(e) else self.save())
        bind(("<Control-p>", "<Control-P>"), lambda e: self.print_file())
        bind(("<Control-z>", "<Control-Z>"), lambda e: self.undo())
        bind(("<Control-y>", "<Control-Y>"), lambda e: self.redo())
        bind(("<Control-e>", "<Control-E>"), lambda e: self.search_bing())
        bind(("<Control-f>", "<Control-F>"), lambda e: self.open_find())
        bind(("<Control-h>", "<Control-H>"), lambda e: self.open_replace())
        bind(("<Control-g>", "<Control-G>"), lambda e: self.goto_line())
        bind(("<Control-a>", "<Control-A>", "<Control-slash>"), lambda e: self.select_all())
        bind(("<F5>",), lambda e: self.insert_datetime())
        bind(("<F3>",), lambda e: self.find_next())
        bind(("<Shift-F3>",), lambda e: self.find_previous())
        bind(("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"),
             lambda e: self.zoom_in())
        bind(("<Control-minus>", "<Control-KP_Subtract>"), lambda e: self.zoom_out())
        bind(("<Control-0>", "<Control-KP_0>", "<Control-KP_Insert>"),
             lambda e: self.zoom_reset())
        # Emacs-artige Tk-Standardbelegungen neutralisieren
        bind(("<Control-b>", "<Control-d>", "<Control-k>", "<Control-t>",
              "<Control-B>", "<Control-D>", "<Control-K>", "<Control-T>"), lambda e: None)

        t.bind("<Control-MouseWheel>",
               lambda e: (self.zoom_in() if e.delta > 0 else self.zoom_out(), "break")[1])
        t.bind("<Control-Button-4>", lambda e: (self.zoom_in(), "break")[1])
        t.bind("<Control-Button-5>", lambda e: (self.zoom_out(), "break")[1])
        t.bind("<Button-3>", self._context_menu)

        # Menüleiste per Alt-Taste / F10
        for idx, (lbl, _m, _p) in enumerate(self.menu_labels):
            ch = lbl.cget("text")[lbl.cget("underline")].lower()
            for seq in ("<Alt-%s>" % ch, "<Alt-%s>" % ch.upper()):
                self.root.bind_all(seq, lambda e, i=idx: self.open_menu(i, keyboard=True))
        t.bind("<F10>", lambda e: self.open_menu(0, keyboard=True))

    def _context_menu(self, event):
        if not self.text.tag_ranges("sel"):
            self.text.mark_set("insert", "@%d,%d" % (event.x, event.y))
        self._update_edit_menu()
        self.text.focus_set()
        self.menus.popup(self.m_ctx, event.x_root, event.y_root)
        return "break"

    # ---------------------------------------------------------------- Status
    def _poll(self):
        try:
            if self.drop.queue:
                self._process_drop()
            state = (self.text.index("insert"), self.text.edit_modified(), self.zoom,
                     self.encoding, self.eol, self.path)
            if state != self._last_state:
                self._last_state = state
                self._refresh_status()
        except tk.TclError:
            return
        self.root.after(100, self._poll)

    def _display_name(self):
        return os.path.basename(self.path) if self.path else "Unbenannt"

    def _refresh_status(self):
        line, col = self.text.index("insert").split(".")
        modified = self.text.edit_modified()
        self.lbl_pos.configure(text="Zeile %s, Spalte %d" % (line, int(col) + 1))
        self.lbl_zoom.configure(text="%d%%" % self.zoom)
        self.lbl_eol.configure(text=EOLS[self.eol][1])
        self.lbl_enc.configure(text=self.encoding)
        self.dot.itemconfigure(self.dot_id, fill=C["amber"] if modified else C["accent"])
        self.lbl_state.configure(text="Nicht gespeichert" if modified else
                                 ("Gespeichert" if self.path else "Bereit"))
        self.root.title(("*" if modified else "") + self._display_name() + " - " + APP_TITLE)

    # ---------------------------------------------------------------- Datei
    def confirm_discard(self):
        if not self.text.edit_modified():
            return True
        name = self.path or "Unbenannt"
        res = ask(self.root, 'Möchten Sie die Änderungen an "%s" speichern?' % name,
                  [("Speichern", "save"), ("Nicht speichern", "discard"),
                   ("Abbrechen", "cancel")], default="save", cancel="cancel")
        if res == "save":
            return self.save()
        return res == "discard"

    def _set_content(self, content):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.text.mark_set("insert", "1.0")
        self.text.see("1.0")

    def new_file(self):
        if not self.confirm_discard():
            return
        self.path = None
        self.encoding, self.eol = "UTF-8", "CRLF"
        self.v_encoding.set(self.encoding)
        self.v_eol.set(self.eol)
        self._set_content("")

    def new_window(self, path=None):
        try:
            if getattr(sys, "frozen", False):
                cmd = [sys.executable]
            else:
                cmd = [sys.executable, os.path.abspath(__file__)]
            if path:
                cmd.append(path)
            flags = 0x00000008 if IS_WIN else 0  # DETACHED_PROCESS
            subprocess.Popen(cmd, cwd=app_dir(), creationflags=flags, close_fds=True)
        except Exception as exc:
            show_message(self.root, "Neues Fenster konnte nicht geöffnet werden:\n%s" % exc,
                         kind="error")

    def open_file(self):
        if not self.confirm_discard():
            return
        initial = os.path.dirname(self.path) if self.path else None
        path = filedialog.askopenfilename(parent=self.root, title="Öffnen",
                                          filetypes=FILETYPES, initialdir=initial)
        if path:
            self.load_file(path)

    def load_file(self, path):
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError as exc:
            show_message(self.root, "%s\n\nDie Datei konnte nicht geöffnet werden:\n%s"
                         % (path, exc.strerror or exc), kind="error")
            return False
        text, enc = decode_bytes(data)
        self.eol = detect_eol(text)
        self.encoding = enc
        self.v_encoding.set(enc)
        self.v_eol.set(self.eol)
        self.path = os.path.abspath(path)
        self._set_content(normalize_eol(text))
        return True

    def _process_drop(self):
        """Abgelegte Dateien öffnen: erste in diesem Fenster, weitere in neuen Fenstern."""
        if self.menus.is_open:
            self.menus.close_all()
        if self.root.grab_current() is not None:
            return  # gerade ist ein Dialog offen – später erneut versuchen
        dropped = self.drop.take()
        files = [f for f in dropped if os.path.isfile(f)]
        if not files:
            if dropped:
                show_message(self.root, "Ordner können nicht geöffnet werden.\n"
                                        "Bitte eine oder mehrere Dateien ziehen.", kind="warn")
            return
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except tk.TclError:
            pass
        if self.confirm_discard():
            self.load_file(files[0])
        for extra in files[1:]:
            self.new_window(extra)
        self.text.focus_set()

    def _open_from_cmdline(self, path):
        if os.path.isfile(path):
            self.load_file(path)
            return
        res = ask(self.root, 'Die Datei "%s" ist nicht vorhanden.\n\n'
                             'Möchten Sie eine neue Datei erstellen?' % path,
                  [("Ja", "yes"), ("Nein", "no")], default="yes", cancel="no")
        if res == "yes":
            try:
                with open(path, "wb"):
                    pass
                self.load_file(path)
            except OSError as exc:
                show_message(self.root, "Die Datei konnte nicht erstellt werden:\n%s" % exc,
                             kind="error")

    def _encode_current(self):
        """Liefert die Bytes des aktuellen Inhalts oder None bei Abbruch."""
        content = self.text.get("1.0", "end-1c")
        content = content.replace("\n", EOLS[self.eol][0])
        codec, bom = ENCODING_CODEC[self.encoding]
        try:
            return bom + content.encode(codec)
        except UnicodeEncodeError:
            res = ask(self.root,
                      "Diese Datei enthält Zeichen, die in der Codierung \"%s\" nicht "
                      "darstellbar sind. Beim Speichern gehen diese Zeichen verloren "
                      "(sie werden durch \"?\" ersetzt).\n\nTrotzdem speichern? Um die "
                      "Zeichen zu behalten, wählen Sie unter Format › Codierung z. B. "
                      "UTF-8." % self.encoding,
                      [("OK", "ok"), ("Abbrechen", "cancel")], default="cancel",
                      cancel="cancel")
            if res != "ok":
                return None
            return bom + content.encode(codec, errors="replace")
        except UnicodeError:
            # einzelne Surrogate o. Ä.
            return bom + content.encode(codec, errors="replace")

    def save(self):
        if not self.path:
            return self.save_as()
        return self._write(self.path)

    def save_as(self):
        initial_dir = os.path.dirname(self.path) if self.path else None
        initial_file = os.path.basename(self.path) if self.path else "*.txt"
        path = filedialog.asksaveasfilename(parent=self.root, title="Speichern unter",
                                            filetypes=FILETYPES, defaultextension=".txt",
                                            initialdir=initial_dir, initialfile=initial_file)
        if not path:
            return False
        return self._write(path)

    def _write(self, path):
        data = self._encode_current()
        if data is None:
            return False
        try:
            with open(path, "wb") as fh:
                fh.write(data)
        except OSError as exc:
            show_message(self.root, "%s\n\nDie Datei konnte nicht gespeichert werden:\n%s"
                         % (path, exc.strerror or exc), kind="error")
            return False
        self.path = os.path.abspath(path)
        self.text.edit_modified(False)
        self.text.edit_separator()
        return True

    def print_file(self):
        if not IS_WIN:
            show_message(self.root, "Drucken wird nur unter Windows unterstützt.", kind="warn")
            return
        res = ask(self.root, 'Das Dokument "%s" wird an den Standarddrucker gesendet.'
                  % self._display_name(),
                  [("Drucken", "print"), ("Abbrechen", "cancel")], default="print",
                  cancel="cancel", kind="info", title="Drucken")
        if res != "print":
            return
        data = self._encode_current()
        if data is None:
            return
        try:
            base = os.path.splitext(self._display_name())[0] or "Unbenannt"
            folder = tempfile.mkdtemp(prefix="editor-druck-")
            tmp = os.path.join(folder, base + ".txt")
            with open(tmp, "wb") as fh:
                fh.write(data)
            os.startfile(tmp, "print")  # noqa: S606 – nur Windows
        except Exception as exc:
            show_message(self.root, "Drucken fehlgeschlagen:\n%s" % exc, kind="error")

    def exit_app(self):
        if not self.confirm_discard():
            return
        s = self.settings
        try:
            if self.root.state() == "zoomed":
                s.set("maximized", True)
            else:
                s.set("maximized", False)
                s.set("geometry", self.root.geometry())
        except tk.TclError:
            pass
        s.set("font_family", self.base_font["family"])
        s.set("font_size", self.base_size)
        s.set("font_weight", self.base_font["weight"])
        s.set("font_slant", self.base_font["slant"])
        s.set("word_wrap", self.v_wrap.get())
        s.set("statusbar", self.v_status.get())
        s.set("zoom", self.zoom)
        s.set("match_case", self.match_case.get())
        s.set("wrap_around", self.wrap_around.get())
        s.set("search_up", self.direction.get() == "up")
        s.set("last_find", self.find_var.get().replace("\n", " "))
        s.set("last_replace", self.replace_var.get().replace("\n", " "))
        s.save()
        self.root.destroy()

    # ---------------------------------------------------------------- Bearbeiten
    def undo(self):
        try:
            self.text.edit_undo()
        except tk.TclError:
            pass

    def redo(self):
        try:
            self.text.edit_redo()
        except tk.TclError:
            pass

    def cut(self):
        self.text.event_generate("<<Cut>>")

    def copy(self):
        self.text.event_generate("<<Copy>>")

    def paste(self):
        self.text.event_generate("<<Paste>>")
        self.text.see("insert")

    def delete(self):
        if self.text.tag_ranges("sel"):
            self.text.delete("sel.first", "sel.last")

    def select_all(self):
        self.text.tag_add("sel", "1.0", "end-1c")
        self.text.mark_set("insert", "end-1c")
        self.text.see("insert")

    def insert_datetime(self):
        now = datetime.datetime.now().strftime("%H:%M %d.%m.%Y")
        if self.text.tag_ranges("sel"):
            self.text.delete("sel.first", "sel.last")
        self.text.insert("insert", now)
        self.text.see("insert")

    def _selected_text(self):
        try:
            return self.text.get("sel.first", "sel.last")
        except tk.TclError:
            return ""

    def search_bing(self):
        term = self._selected_text().strip()
        if term:
            webbrowser.open("https://www.bing.com/search?q=" + urllib.parse.quote(term))

    def goto_line(self):
        GotoDialog(self)

    # ---------------------------------------------------------------- Suche
    def _prefill_find(self):
        sel = self._selected_text()
        if sel and "\n" not in sel and len(sel) < 200:
            self.find_var.set(sel)

    def open_find(self):
        self._open_find_dialog(replace=False)

    def open_replace(self):
        self._open_find_dialog(replace=True)

    def _open_find_dialog(self, replace):
        self._prefill_find()
        if self.find_dialog is not None:
            if self.find_dialog.replace_mode == replace:
                self.find_dialog.lift()
                self.find_dialog.e_find.focus_set()
                self.find_dialog.e_find.select_range(0, "end")
                return
            self.find_dialog.close()
        self.find_dialog = FindReplaceDialog(self, replace=replace)

    def find_next(self):
        if not self.find_var.get():
            self.open_find()
            return
        self.search(backwards=False)

    def find_previous(self):
        if not self.find_var.get():
            self.open_find()
            return
        self.search(backwards=True)

    def search(self, backwards=False, parent=None, quiet=False):
        term = self.find_var.get()
        if not term:
            return False
        t = self.text
        nocase = not self.match_case.get()
        wrap = self.wrap_around.get()
        has_sel = bool(t.tag_ranges("sel"))
        if backwards:
            start = "sel.first" if has_sel else "insert"
            idx = t.search(term, start, stopindex="1.0", backwards=True, nocase=nocase)
            if not idx and wrap:
                idx = t.search(term, "end", stopindex=start, backwards=True, nocase=nocase)
        else:
            start = "sel.last" if has_sel else "insert"
            idx = t.search(term, start, stopindex="end", nocase=nocase)
            if not idx and wrap:
                idx = t.search(term, "1.0", stopindex=start, nocase=nocase)
        if idx:
            end = "%s+%dc" % (idx, len(term))
            t.tag_remove("sel", "1.0", "end")
            t.tag_add("sel", idx, end)
            t.mark_set("insert", idx if backwards else end)
            t.see(idx)
            return True
        if not quiet:
            show_message(parent or self.root, 'Kann "%s" nicht finden.' % term, kind="info")
        return False

    def _selection_matches(self):
        sel = self._selected_text()
        term = self.find_var.get()
        if not sel or not term:
            return False
        if self.match_case.get():
            return sel == term
        return sel.lower() == term.lower()

    def replace_current(self, parent=None):
        if self._selection_matches():
            t = self.text
            t.edit_separator()
            first = t.index("sel.first")
            t.delete("sel.first", "sel.last")
            t.insert(first, self.replace_var.get())
            t.mark_set("insert", "%s+%dc" % (first, len(self.replace_var.get())))
            t.edit_separator()
        self.search(backwards=False, parent=parent)

    def replace_all(self):
        term = self.find_var.get()
        if not term:
            return
        repl = self.replace_var.get()
        nocase = not self.match_case.get()
        t = self.text
        t.configure(autoseparators=False)
        t.edit_separator()
        pos = "1.0"
        count = 0
        try:
            while True:
                idx = t.search(term, pos, stopindex="end", nocase=nocase)
                if not idx:
                    break
                t.delete(idx, "%s+%dc" % (idx, len(term)))
                t.insert(idx, repl)
                pos = "%s+%dc" % (idx, len(repl))
                count += 1
        finally:
            t.edit_separator()
            t.configure(autoseparators=True)
        if count:
            t.tag_remove("sel", "1.0", "end")

    # ---------------------------------------------------------------- Format / Ansicht
    def apply_wrap(self):
        if self.v_wrap.get():
            self.text.configure(wrap="word")
            self.hscroll.grid_remove()
            self.corner.grid_remove()
        else:
            self.text.configure(wrap="none")
            self.hscroll.grid()
            self.corner.grid()

    def apply_statusbar(self):
        if self.v_status.get():
            self.status_sep.pack(side="bottom", fill="x", before=self.text.master)
            self.statusbar.pack(side="bottom", fill="x", before=self.status_sep)
        else:
            self.statusbar.pack_forget()
            self.status_sep.pack_forget()

    def choose_font(self):
        dlg = FontDialog(self)
        if dlg.result:
            fam, size, weight, slant = dlg.result
            self.base_font = {"family": fam, "weight": weight, "slant": slant}
            self.base_size = size
            self.font.configure(family=fam, weight=weight, slant=slant,
                                size=self._zoomed_size())
            self._apply_tabs()
        self.text.focus_set()

    def _encoding_changed(self):
        if self.v_encoding.get() != self.encoding:
            self.encoding = self.v_encoding.get()
            self.text.edit_modified(True)

    def _eol_changed(self):
        if self.v_eol.get() != self.eol:
            self.eol = self.v_eol.get()
            self.text.edit_modified(True)

    def _zoomed_size(self):
        return max(1, int(round(self.base_size * self.zoom / 100.0)))

    def _apply_tabs(self):
        self.text.configure(tabs=(self.font.measure(" " * 8),))

    def _set_zoom(self, value):
        self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, value))
        self.font.configure(size=self._zoomed_size())
        self._apply_tabs()

    def zoom_in(self):
        self._set_zoom(self.zoom + ZOOM_STEP)

    def zoom_out(self):
        self._set_zoom(self.zoom - ZOOM_STEP)

    def zoom_reset(self):
        self._set_zoom(100)


def main():
    enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    path = sys.argv[1] if len(sys.argv) > 1 else None
    EditorApp(root, path)
    root.update_idletasks()
    dark_titlebar(root)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
