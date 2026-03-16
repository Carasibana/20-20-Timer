#!/usr/bin/env python3
"""
20-20 Break Timer
=================
Prompts you to take a short movement break at a configurable interval.
Lives in the system tray. Double-click / left-click to open the control window.

Dependencies: Pillow, pystray  (run setup.bat or: pip install Pillow pystray)
"""

import sys, time, datetime, threading, json, queue
from pathlib import Path

# ── Dependency bootstrap ───────────────────────────────────────────────────────
def _install(*pkgs):
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", *pkgs])

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except ImportError:
    _install("Pillow"); from PIL import Image, ImageDraw, ImageFont, ImageTk

try:
    import pystray
except ImportError:
    _install("pystray"); import pystray

import tkinter as tk
from tkinter import ttk

try:
    import winsound
    _HAS_SOUND = True
except ImportError:
    _HAS_SOUND = False

try:
    import winreg as _winreg
    _HAS_WINREG = True
except ImportError:
    _HAS_WINREG = False

# ── File paths ─────────────────────────────────────────────────────────────────
DATA_FILE     = Path(__file__).parent / "timer_data.json"
SETTINGS_FILE = Path(__file__).parent / "settings.json"
_SCRIPT_PATH  = Path(__file__).resolve()

URGENT_MULTIPLIER  = 1
_AUTOSTART_KEY     = r"Software\Microsoft\Windows\CurrentVersion\Run"
_AUTOSTART_NAME    = "20-20 Timer"

# ── Unit helpers ───────────────────────────────────────────────────────────────
UNIT_TO_SECS = {"seconds": 1, "minutes": 60, "hours": 3600}

def to_secs(value: float, unit: str) -> int:
    return max(1, int(value * UNIT_TO_SECS.get(unit, 1)))

def best_unit(total_secs: int) -> tuple:
    if total_secs % 3600 == 0 and total_secs >= 3600:
        return total_secs // 3600, "hours"
    if total_secs % 60 == 0 and total_secs >= 60:
        return total_secs // 60, "minutes"
    return total_secs, "seconds"

# ── Windows auto-start ─────────────────────────────────────────────────────────
def _pythonw_path() -> str:
    """Best path to pythonw.exe (no console window on launch)."""
    candidate = Path(sys.executable).parent / "pythonw.exe"
    return str(candidate) if candidate.exists() else sys.executable

def set_autostart(enabled: bool):
    if not _HAS_WINREG:
        return
    try:
        with _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, _AUTOSTART_KEY,
                             0, _winreg.KEY_SET_VALUE) as key:
            if enabled:
                value = f'"{_pythonw_path()}" "{_SCRIPT_PATH}"'
                _winreg.SetValueEx(key, _AUTOSTART_NAME, 0, _winreg.REG_SZ, value)
            else:
                try:
                    _winreg.DeleteValue(key, _AUTOSTART_NAME)
                except FileNotFoundError:
                    pass
    except Exception:
        pass

def get_autostart() -> bool:
    if not _HAS_WINREG:
        return False
    try:
        with _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, _AUTOSTART_KEY,
                             0, _winreg.KEY_READ) as key:
            _winreg.QueryValueEx(key, _AUTOSTART_NAME)
            return True
    except FileNotFoundError:
        return False
    except Exception:
        return False

# ── Settings helpers ───────────────────────────────────────────────────────────
def load_settings() -> dict:
    try:
        s = json.loads(SETTINGS_FILE.read_text()) if SETTINGS_FILE.exists() else {}
    except Exception:
        s = {}
    # Migrate old format
    if "work_value" not in s:
        s["work_value"] = s.pop("work_mins",  20)
        s["work_unit"]  = "minutes"
    if "break_value" not in s:
        s["break_value"] = s.pop("break_secs", 20)
        s["break_unit"]  = "seconds"
    s.setdefault("work_unit",       "minutes")
    s.setdefault("break_unit",      "seconds")
    s.setdefault("start_minimized", False)
    return s

def save_settings(s: dict):
    SETTINGS_FILE.write_text(json.dumps(s, indent=2))

# ── Data helpers ───────────────────────────────────────────────────────────────
def load_data() -> dict:
    try:
        return json.loads(DATA_FILE.read_text()) if DATA_FILE.exists() else {}
    except Exception:
        return {}

def save_data(d: dict):
    DATA_FILE.write_text(json.dumps(d, indent=2))

def today_key() -> str:
    return datetime.date.today().isoformat()

def ensure_today(d: dict) -> dict:
    k = today_key()
    d.setdefault(k, {"completed": 0, "missed": 0, "score": 0})
    return d[k]

def calc_streak(d: dict) -> tuple:
    today_rec      = d.get(today_key(), {})
    includes_today = today_rec.get("completed", 0) > 0
    streak         = 0
    day = datetime.date.today() if includes_today else datetime.date.today() - datetime.timedelta(days=1)
    while True:
        if d.get(day.isoformat(), {}).get("completed", 0) > 0:
            streak += 1
            day -= datetime.timedelta(days=1)
        else:
            break
    return streak, includes_today

# ── Tray icon generator ────────────────────────────────────────────────────────
_ICON_SZ = 64

def _try_font(size: int):
    for name in ("arialbd.ttf", "arial.ttf", "segoeui.ttf", "calibri.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()

def make_icon(label: str, color: str) -> Image.Image:
    img = Image.new("RGBA", (_ICON_SZ, _ICON_SZ), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    m   = 3
    d.ellipse([m, m, _ICON_SZ - m, _ICON_SZ - m], fill=color, outline="#ffffff", width=2)
    fnt = _try_font(18 if len(label) <= 3 else 14)
    bb  = d.textbbox((0, 0), label, font=fnt)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    d.text((_ICON_SZ // 2 - tw // 2, _ICON_SZ // 2 - th // 2),
           label, fill="#ffffff", font=fnt)
    return img

def make_app_icon() -> "ImageTk.PhotoImage":
    """Taskbar / title-bar icon: dark circle with a purple ring and '20' in green."""
    sz  = 64
    img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    # Filled dark circle
    d.ellipse([1, 1, sz - 1, sz - 1], fill="#1e1e2e")
    # Purple ring (3 px wide)
    d.ellipse([1, 1, sz - 1, sz - 1], outline="#bd93f9", width=4)
    # Inner accent ring in a slightly dimmer purple
    d.ellipse([7, 7, sz - 7, sz - 7], outline="#6272a4", width=1)
    # "20" label in green
    fnt = _try_font(26)
    lbl = "20"
    bb  = d.textbbox((0, 0), lbl, font=fnt)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    d.text((sz // 2 - tw // 2, sz // 2 - th // 2 - 1),
           lbl, fill="#50fa7b", font=fnt)
    # Tiny "min" label below
    fnt2 = _try_font(10)
    sub  = "min"
    bb2  = d.textbbox((0, 0), sub, font=fnt2)
    sw2  = bb2[2] - bb2[0]
    d.text((sz // 2 - sw2 // 2, sz // 2 + th // 2 + 1),
           sub, fill="#6272a4", font=fnt2)
    return ImageTk.PhotoImage(img)

# ── App states ─────────────────────────────────────────────────────────────────
WORKING   = "working"
BREAK_DUE = "break_due"
URGENT    = "urgent"
ON_BREAK  = "on_break"

# ── Colour palette ─────────────────────────────────────────────────────────────
C = dict(
    bg       = "#1e1e2e",
    bg_light = "#2a2a3e",
    green    = "#50fa7b",
    orange   = "#ffb86c",
    red      = "#ff5555",
    blue     = "#8be9fd",
    purple   = "#bd93f9",
    text     = "#f8f8f2",
    muted    = "#6272a4",
    grey     = "#44475a",
)

# ── Main application ───────────────────────────────────────────────────────────
class App:
    def __init__(self):
        self.settings   = load_settings()
        self.work_secs  = to_secs(self.settings["work_value"],  self.settings["work_unit"])
        self.break_secs = to_secs(self.settings["break_value"], self.settings["break_unit"])

        self.state    = WORKING
        self.t_cycle  = time.monotonic()
        self.t_break  = 0.0
        self.paused   = False
        self._t_pause = 0.0
        self.data     = load_data()
        self._q       = queue.Queue()
        self._running = True

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("20-20 Timer")

        # Give the app its own identity in the Windows taskbar (not grouped
        # under python.exe) and apply a custom icon to every window.
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "20-20BreakTimer.App"
            )
        except Exception:
            pass
        self._app_icon = make_app_icon()          # keep reference so GC won't collect it
        self.root.iconphoto(True, self._app_icon)  # True = apply to all child windows

        self._notif_win    = None
        self._stats_win    = None
        self._cdown_win    = None
        self._main_win     = None
        self._settings_win = None

        self._tray = pystray.Icon(
            "20-20 Timer",
            make_icon("20m", C["green"]),
            "20-20 Timer",
            menu=pystray.Menu(
                pystray.MenuItem("Open Timer",     self._tray_open,  default=True),
                pystray.MenuItem(
                    lambda item: "Resume Timer" if self.paused else "Pause Timer",
                    self._tray_pause_toggle),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Show Stats",     self._tray_stats),
                pystray.MenuItem("Take Break Now", self._tray_break),
                pystray.MenuItem("Settings",       self._tray_settings),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit",           self._tray_quit),
            ),
        )
        threading.Thread(target=self._tray.run, daemon=True).start()
        threading.Thread(target=self._timer_loop, daemon=True).start()

        self.root.after(100,  self._pump_queue)
        self.root.after(1000, self._refresh_tray)
        self.root.after(200,  self._open_main_win)

    def run(self):
        self.root.mainloop()

    def apply_settings(self, work_value: float, work_unit: str,
                       break_value: float, break_unit: str,
                       start_minimized: bool, start_with_windows: bool):
        self.settings["work_value"]      = work_value
        self.settings["work_unit"]       = work_unit
        self.settings["break_value"]     = break_value
        self.settings["break_unit"]      = break_unit
        self.settings["start_minimized"] = start_minimized
        save_settings(self.settings)

        self.work_secs  = to_secs(work_value,  work_unit)
        self.break_secs = to_secs(break_value, break_unit)

        set_autostart(start_with_windows)

        if self.state in (WORKING, BREAK_DUE, URGENT):
            self.state   = WORKING
            self.t_cycle = time.monotonic()
            self._close_notif()

    # ── Queue pump ─────────────────────────────────────────────────────────────
    def _pump_queue(self):
        try:
            while True:
                self._q.get_nowait()()
        except queue.Empty:
            pass
        if self._running:
            self.root.after(100, self._pump_queue)

    # ── Timer loop (background thread) ────────────────────────────────────────
    def _timer_loop(self):
        _last_gentle = 0.0
        _last_urgent = 0.0

        while self._running:
            if self.paused:
                time.sleep(0.5)
                continue

            now     = time.monotonic()
            elapsed = now - self.t_cycle

            if self.state == WORKING:
                if elapsed >= self.work_secs:
                    self.state   = BREAK_DUE
                    _last_gentle = now
                    self._q.put(self._show_notif)
                    self._beep_gentle()

            elif self.state == BREAK_DUE:
                if elapsed >= self.work_secs * (1 + URGENT_MULTIPLIER):
                    self.state   = URGENT
                    _last_urgent = now
                    self._q.put(self._make_urgent)
                    self._beep_urgent()
                elif now - _last_gentle >= 60:
                    _last_gentle = now
                    self._beep_gentle()

            elif self.state == URGENT:
                if now - _last_urgent >= 30:
                    _last_urgent = now
                    self._beep_urgent()

            elif self.state == ON_BREAK:
                if now - self.t_break >= self.break_secs:
                    self._finish_break()

            time.sleep(0.5)

    # ── Sound ──────────────────────────────────────────────────────────────────
    def _beep_gentle(self):
        if _HAS_SOUND:
            threading.Thread(target=lambda: winsound.Beep(880, 350), daemon=True).start()

    def _beep_urgent(self):
        if _HAS_SOUND:
            def _play():
                for freq in (1200, 900, 1200):
                    winsound.Beep(freq, 220)
                    time.sleep(0.05)
            threading.Thread(target=_play, daemon=True).start()

    # ── Tray icon refresh ──────────────────────────────────────────────────────
    def _refresh_tray(self):
        if not self._running:
            return
        now = time.monotonic()

        if self.paused:
            label, color = "||", C["grey"]
            tooltip = "20-20 Timer — PAUSED"
        elif self.state == WORKING:
            secs_left = max(0, self.work_secs - (now - self.t_cycle))
            m = int(secs_left // 60)
            s = int(secs_left % 60)
            label = f"{m}m" if m > 0 else f"{s}s"
            color = C["green"]
            tooltip = f"20-20 Timer — break in {m:02d}:{s:02d}"
        elif self.state == BREAK_DUE:
            label, color = "NOW", C["orange"]
            tooltip = "20-20 Timer — BREAK TIME!"
        elif self.state == URGENT:
            overdue = int(now - self.t_cycle - self.work_secs)
            label, color = "!!!", C["red"]
            tooltip = f"20-20 Timer — URGENT ({overdue // 60}m overdue)"
        else:
            secs_left = max(0, self.break_secs - int(now - self.t_break))
            label, color = f"{secs_left}s", C["blue"]
            tooltip = f"20-20 Timer — break: {secs_left}s left"

        try:
            self._tray.icon  = make_icon(label, color)
            self._tray.title = tooltip
        except Exception:
            pass

        self.root.after(1000, self._refresh_tray)

    # ── Pause / Resume ─────────────────────────────────────────────────────────
    def pause(self):
        if self.paused or self.state == ON_BREAK:
            return
        self.paused   = True
        self._t_pause = time.monotonic()

    def resume(self):
        if not self.paused:
            return
        self.t_cycle += time.monotonic() - self._t_pause
        self.paused   = False

    # ── Break flow ─────────────────────────────────────────────────────────────
    def start_break(self):
        if self.state not in (BREAK_DUE, URGENT):
            return
        self.state   = ON_BREAK
        self.t_break = time.monotonic()
        self._close_notif()
        self._cdown_win = CountdownWindow(self.root, self)

    def skip_break(self):
        rec = ensure_today(self.data)
        rec["missed"] += 1
        save_data(self.data)
        self.state   = WORKING
        self.t_cycle = time.monotonic()
        self._close_notif()

    def force_break(self):
        if self.state == ON_BREAK:
            return
        self.state   = ON_BREAK
        self.t_break = time.monotonic()
        self._close_notif()
        self._cdown_win = CountdownWindow(self.root, self)

    def _finish_break(self):
        if self.state != ON_BREAK:
            return
        self.state   = WORKING
        self.t_cycle = time.monotonic()
        rec = ensure_today(self.data)
        rec["completed"] += 1
        rec["score"]     += 1
        save_data(self.data)
        self._q.put(self._on_break_done)

    def _on_break_done(self):
        if self._cdown_win:
            try:
                self._cdown_win.destroy()
            except Exception:
                pass
            self._cdown_win = None
        FlashWindow(self.root, "  Break complete!  +1 point  ", C["green"])

    # ── Window helpers ─────────────────────────────────────────────────────────
    def _show_notif(self):
        self._close_notif()
        self._notif_win = NotifWindow(self.root, self, urgent=False)

    def _make_urgent(self):
        if self._notif_win:
            self._notif_win.go_urgent()
        else:
            self._notif_win = NotifWindow(self.root, self, urgent=True)

    def _close_notif(self):
        if self._notif_win:
            try:
                self._notif_win.destroy()
            except Exception:
                pass
            self._notif_win = None

    def _show_stats(self):
        if self._stats_win and self._stats_win.winfo_exists():
            self._stats_win.lift(); self._stats_win.focus_force(); return
        self._stats_win = StatsWindow(self.root, self.data)

    def _show_settings(self):
        if self._settings_win and self._settings_win.winfo_exists():
            self._settings_win.lift(); self._settings_win.focus_force(); return
        self._settings_win = SettingsWindow(self.root, self)

    def _open_main_win(self):
        if self._main_win and self._main_win.winfo_exists():
            # Toggle: clicking the tray icon while open hides the window
            if self._main_win.winfo_viewable():
                self._main_win.withdraw()
            else:
                self._main_win.show()
            return
        self._main_win = MainWindow(self.root, self)
        # Respect start_minimized setting on first launch
        if self.settings.get("start_minimized", False):
            self._main_win.withdraw()

    # ── Tray callbacks ─────────────────────────────────────────────────────────
    def _tray_open(self, *_):          self._q.put(self._open_main_win)
    def _tray_pause_toggle(self, *_):
        def _toggle():
            if self.paused:
                self.resume()
            else:
                self.pause()
            try:
                self._tray.update_menu()
            except Exception:
                pass
        self._q.put(_toggle)
    def _tray_stats(self, *_):         self._q.put(self._show_stats)
    def _tray_break(self, *_):         self._q.put(self.force_break)
    def _tray_settings(self, *_):      self._q.put(self._show_settings)

    def _tray_quit(self, *_):
        self._running = False
        self._tray.stop()
        self.root.after(200, self.root.quit)


# ── Main control window ────────────────────────────────────────────────────────
class MainWindow(tk.Toplevel):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app
        self.title("20-20 Timer")
        self.resizable(False, False)
        self.config(bg=C["bg"])

        # X button → hide to tray
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        # Taskbar button click while open → hide to tray instead of minimise
        self.bind("<Configure>", self._on_configure)

        self._build()
        self.update_idletasks()
        sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
        w  = self.winfo_reqwidth();   h  = self.winfo_reqheight()
        self.geometry(f"+{sw // 2 - w // 2}+{sh // 2 - h // 2}")
        self._tick()

    def _on_configure(self, event):
        """<Configure> fires after the window state is updated, so state()
        reliably returns 'iconic' when the user clicks the taskbar button.
        We intercept that and withdraw to tray instead."""
        if event.widget is self and self.state() == "iconic":
            self.after(0, self.withdraw)

    def show(self):
        self.deiconify(); self.lift(); self.focus_force()

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=C["bg_light"], pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="20-20 Break Timer",
                 font=("Segoe UI", 13, "bold"),
                 bg=C["bg_light"], fg=C["text"]).pack()
        tk.Label(hdr, text="Close this window to keep running in the tray",
                 font=("Segoe UI", 8), bg=C["bg_light"], fg=C["muted"]).pack(pady=(2, 0))

        # State label
        self._state_lbl = tk.Label(self, text="WORKING",
                                   font=("Segoe UI", 9, "bold"),
                                   bg=C["bg"], fg=C["muted"])
        self._state_lbl.pack(pady=(16, 2))

        # Big countdown
        self._big_lbl = tk.Label(self, text="20:00",
                                 font=("Segoe UI", 56, "bold"),
                                 bg=C["bg"], fg=C["green"])
        self._big_lbl.pack()

        self._sub_lbl = tk.Label(self, text="until next break",
                                 font=("Segoe UI", 9), bg=C["bg"], fg=C["muted"])
        self._sub_lbl.pack(pady=(0, 10))

        # Progress bar
        self._cv  = tk.Canvas(self, width=260, height=8,
                              bg=C["bg_light"], highlightthickness=0, bd=0)
        self._cv.pack()
        self._bar = self._cv.create_rectangle(0, 0, 0, 8, fill=C["green"], outline="")

        # Action area
        self._action = tk.Frame(self, bg=C["bg"])
        self._action.pack(pady=16, fill="x", padx=24)

        self._pause_btn = tk.Button(
            self._action, text="  Pause Timer  ",
            bg=C["bg_light"], fg=C["text"],
            font=("Segoe UI", 10), relief="flat", cursor="hand2",
            padx=10, pady=6, command=self._toggle_pause)

        self._start_btn = tk.Button(
            self._action, text="  Start Break  ",
            bg=C["orange"], fg="#000000",
            font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
            padx=10, pady=6, command=self.app.start_break)

        self._skip_btn = tk.Button(
            self._action, text="Skip",
            bg=C["bg_light"], fg=C["muted"],
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            padx=8, pady=6, command=self.app.skip_break)

        self._in_break_lbl = tk.Label(
            self._action, text="Break in progress…",
            font=("Segoe UI", 10), bg=C["bg"], fg=C["blue"])

        # Divider + bottom buttons
        tk.Frame(self, bg=C["bg_light"], height=1).pack(fill="x")
        btns = tk.Frame(self, bg=C["bg"], pady=12)
        btns.pack()
        for text, color, cmd in [
            ("Take Break Now", C["blue"],   self.app.force_break),
            ("View Stats",     C["purple"], self.app._show_stats),
            ("Settings",       C["muted"],  self.app._show_settings),
        ]:
            tk.Button(btns, text=text, bg=C["bg_light"], fg=color,
                      font=("Segoe UI", 9), relief="flat", cursor="hand2",
                      padx=10, pady=5, command=cmd).pack(side="left", padx=4)

        # Footer
        tk.Frame(self, bg=C["bg_light"], height=1).pack(fill="x")
        self._footer_lbl = tk.Label(self, text="",
                                    font=("Segoe UI", 8), bg=C["bg"], fg=C["muted"])
        self._footer_lbl.pack(pady=8)

    def _toggle_pause(self):
        if self.app.paused:
            self.app.resume()
        else:
            self.app.pause()

    def _show_action(self, *widgets):
        for w in (self._pause_btn, self._start_btn,
                  self._skip_btn, self._in_break_lbl):
            w.pack_forget()
        for w in widgets:
            w.pack(side="left", padx=4)

    def _tick(self):
        if not self.winfo_exists():
            return

        now   = time.monotonic()
        state = self.app.state

        if self.app.paused:
            self._state_lbl.config(text="PAUSED", fg=C["muted"])
            self._big_lbl.config(text="—:——", fg=C["grey"])
            self._sub_lbl.config(text="timer is paused")
            self._cv.coords(self._bar, 0, 0, 0, 8)
            self._pause_btn.config(text="  Resume Timer  ", fg=C["green"])
            self._show_action(self._pause_btn)

        elif state == WORKING:
            secs_left = max(0, self.app.work_secs - (now - self.app.t_cycle))
            m, s = int(secs_left // 60), int(secs_left % 60)
            pct  = 1 - (secs_left / self.app.work_secs)
            self._state_lbl.config(text="WORKING", fg=C["muted"])
            self._big_lbl.config(text=f"{m:02d}:{s:02d}", fg=C["green"])
            self._sub_lbl.config(text="until next break")
            self._cv.coords(self._bar, 0, 0, int(260 * pct), 8)
            self._cv.itemconfig(self._bar, fill=C["green"])
            self._pause_btn.config(text="  Pause Timer  ", fg=C["text"])
            self._show_action(self._pause_btn)

        elif state == BREAK_DUE:
            overdue = int(now - self.app.t_cycle - self.app.work_secs)
            self._state_lbl.config(text="BREAK TIME!", fg=C["orange"])
            self._big_lbl.config(text="NOW", fg=C["orange"])
            self._sub_lbl.config(text=f"{overdue}s overdue — take your break!")
            self._cv.coords(self._bar, 0, 0, 260, 8)
            self._cv.itemconfig(self._bar, fill=C["orange"])
            self._start_btn.config(bg=C["orange"])
            self._show_action(self._start_btn, self._skip_btn)

        elif state == URGENT:
            overdue = int(now - self.app.t_cycle - self.app.work_secs)
            self._state_lbl.config(text="URGENT!", fg=C["red"])
            self._big_lbl.config(text="NOW!", fg=C["red"])
            self._sub_lbl.config(text=f"{overdue // 60}m {overdue % 60}s overdue")
            self._cv.coords(self._bar, 0, 0, 260, 8)
            self._cv.itemconfig(self._bar, fill=C["red"])
            self._start_btn.config(bg=C["red"])
            self._show_action(self._start_btn, self._skip_btn)

        else:  # ON_BREAK
            secs_left = max(0, self.app.break_secs - int(now - self.app.t_break))
            pct = secs_left / self.app.break_secs
            self._state_lbl.config(text="ON BREAK", fg=C["blue"])
            self._big_lbl.config(text=str(secs_left), fg=C["blue"])
            self._sub_lbl.config(text="look away, stretch, breathe")
            self._cv.coords(self._bar, 0, 0, int(260 * pct), 8)
            self._cv.itemconfig(self._bar, fill=C["blue"])
            self._show_action(self._in_break_lbl)

        today_rec = self.app.data.get(today_key(), {})
        streak, _ = calc_streak(self.app.data)
        completed = today_rec.get("completed", 0)
        missed    = today_rec.get("missed",    0)
        self._footer_lbl.config(
            text=f"Today: {completed} completed  •  {missed} skipped"
                 f"  |  streak: {streak} day{'s' if streak != 1 else ''}")

        self.after(500, self._tick)


# ── Settings window ────────────────────────────────────────────────────────────
class SettingsWindow(tk.Toplevel):
    _UNITS = ["seconds", "minutes", "hours"]

    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app
        self.title("20-20 Timer - Settings")
        self.resizable(False, False)
        self.config(bg=C["bg"])
        self.grab_set()

        s = app.settings

        # Header
        hdr = tk.Frame(self, bg=C["bg_light"], pady=14)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Timer Settings",
                 font=("Segoe UI", 13, "bold"),
                 bg=C["bg_light"], fg=C["text"]).pack()

        body = tk.Frame(self, bg=C["bg"], padx=28, pady=20)
        body.pack(fill="x")
        body.columnconfigure(0, weight=1)

        def section_label(text, note, row):
            tk.Label(body, text=text, font=("Segoe UI", 10),
                     bg=C["bg"], fg=C["text"]).grid(
                     row=row, column=0, sticky="w", pady=(0, 2))
            tk.Label(body, text=note, font=("Segoe UI", 8),
                     bg=C["bg"], fg=C["muted"]).grid(
                     row=row + 1, column=0, sticky="w", pady=(0, 10))

        def value_unit_row(row, val, unit):
            frame = tk.Frame(body, bg=C["bg"])
            frame.grid(row=row, column=1, rowspan=2, sticky="e",
                       padx=(20, 0), pady=(0, 10))
            spin = tk.Spinbox(frame, from_=1, to=999, textvariable=val,
                              width=5, font=("Segoe UI", 11),
                              bg=C["bg_light"], fg=C["text"],
                              buttonbackground=C["bg_light"], relief="flat",
                              highlightthickness=1, highlightbackground=C["grey"],
                              highlightcolor=C["purple"])
            spin.pack(side="left", padx=(0, 6))
            combo = ttk.Combobox(frame, textvariable=unit,
                                 values=self._UNITS, state="readonly",
                                 width=8, font=("Segoe UI", 10))
            combo.pack(side="left")
            return frame

        # ── Work interval ──────────────────────────────────────────────────────
        section_label("Time between breaks",
                      "How long you work before being reminded", 0)
        self._work_val  = tk.DoubleVar(value=s["work_value"])
        self._work_unit = tk.StringVar(value=s["work_unit"])
        value_unit_row(0, self._work_val, self._work_unit)

        # ── Break duration ─────────────────────────────────────────────────────
        section_label("Break duration",
                      "How long each break lasts", 2)
        self._break_val  = tk.DoubleVar(value=s["break_value"])
        self._break_unit = tk.StringVar(value=s["break_unit"])
        value_unit_row(2, self._break_val, self._break_unit)

        # ── Divider ────────────────────────────────────────────────────────────
        tk.Frame(body, bg=C["grey"], height=1).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=(4, 14))

        # ── Startup behaviour ──────────────────────────────────────────────────
        tk.Label(body, text="Startup behaviour",
                 font=("Segoe UI", 10, "bold"),
                 bg=C["bg"], fg=C["text"]).grid(
                 row=5, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self._start_min_var = tk.BooleanVar(value=s.get("start_minimized", False))
        self._autostart_var = tk.BooleanVar(value=get_autostart())

        def checkbox(row, var, text, note):
            f = tk.Frame(body, bg=C["bg"])
            f.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
            tk.Checkbutton(f, variable=var, bg=C["bg"],
                           activebackground=C["bg"],
                           selectcolor=C["bg_light"],
                           fg=C["text"], font=("Segoe UI", 10),
                           relief="flat", cursor="hand2").pack(side="left")
            lf = tk.Frame(f, bg=C["bg"])
            lf.pack(side="left")
            tk.Label(lf, text=text, font=("Segoe UI", 10),
                     bg=C["bg"], fg=C["text"]).pack(anchor="w")
            tk.Label(lf, text=note, font=("Segoe UI", 8),
                     bg=C["bg"], fg=C["muted"]).pack(anchor="w")

        checkbox(6,  self._start_min_var,
                 "Start minimised to tray",
                 "Window stays hidden on launch — click the tray icon to open")
        checkbox(7,  self._autostart_var,
                 "Start with Windows",
                 "Automatically launch when you log in"
                 + ("" if _HAS_WINREG else "  (not available on this OS)"))

        if not _HAS_WINREG:
            self._autostart_var.set(False)

        # ── Buttons ────────────────────────────────────────────────────────────
        tk.Frame(self, bg=C["bg_light"], height=1).pack(fill="x")
        btns = tk.Frame(self, bg=C["bg"], pady=14)
        btns.pack()
        tk.Button(btns, text="Save & Apply",
                  bg=C["purple"], fg="#000000",
                  font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
                  padx=14, pady=6, command=self._save).pack(side="left", padx=8)
        tk.Button(btns, text="Cancel",
                  bg=C["bg_light"], fg=C["muted"],
                  font=("Segoe UI", 9), relief="flat", cursor="hand2",
                  padx=10, pady=6, command=self.destroy).pack(side="left")

        self.update_idletasks()
        sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
        w  = self.winfo_reqwidth();   h  = self.winfo_reqheight()
        self.geometry(f"+{sw // 2 - w // 2}+{sh // 2 - h // 2}")

    def _save(self):
        try:
            wv = float(self._work_val.get())
            bv = float(self._break_val.get())
        except (ValueError, tk.TclError):
            return
        wu = self._work_unit.get()
        bu = self._break_unit.get()
        if wu not in UNIT_TO_SECS or bu not in UNIT_TO_SECS:
            return
        self.app.apply_settings(
            wv, wu, bv, bu,
            self._start_min_var.get(),
            self._autostart_var.get(),
        )
        self.destroy()


# ── Break-due notification popup (bottom-right corner) ────────────────────────
class NotifWindow(tk.Toplevel):
    def __init__(self, parent, app: App, *, urgent: bool):
        super().__init__(parent)
        self.app     = app
        self._urgent = urgent
        self.title("")
        self.resizable(False, False)
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        self._build()
        self._reposition()

    def _build(self):
        for w in self.winfo_children():
            w.destroy()
        bg  = C["red"] if self._urgent else C["orange"]
        msg = ("  URGENT — move NOW!  " if self._urgent
               else "  Time for your break!  ")
        sub = ("You've been sitting too long." if self._urgent
               else "Stand up, look away, move, breathe.")
        self.config(bg=bg)
        tk.Label(self, text=msg, bg=bg, fg="#ffffff",
                 font=("Segoe UI", 11, "bold"), pady=10).pack()
        tk.Label(self, text=sub, bg=bg, fg="#ffffff",
                 font=("Segoe UI", 9)).pack()
        btns = tk.Frame(self, bg=bg)
        btns.pack(pady=10)
        bv, bu = best_unit(self.app.break_secs)
        tk.Button(btns, text=f"  Start {bv:g}{bu[0]} Break  ",
                  bg="#ffffff", fg="#000000",
                  font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
                  command=self.app.start_break).pack(side="left", padx=8)
        tk.Button(btns, text="Skip", bg=bg, fg="#ffffff",
                  font=("Segoe UI", 9), relief="flat", cursor="hand2",
                  command=self.app.skip_break).pack(side="left", padx=4)

    def go_urgent(self):
        self._urgent = True
        self._build()
        self._reposition()

    def _reposition(self):
        self.update_idletasks()
        w  = self.winfo_reqwidth();   h  = self.winfo_reqheight()
        sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
        self.geometry(f"+{sw - w - 20}+{sh - h - 60}")


# ── Break countdown window ─────────────────────────────────────────────────────
class CountdownWindow(tk.Toplevel):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app
        self.title("20-20 Timer - Break")
        self.resizable(False, False)
        self.wm_attributes("-topmost", True)
        self.config(bg=C["bg"])

        tk.Label(self, text="Stand up  •  look away  •  move  •  breathe",
                 font=("Segoe UI", 10), bg=C["bg"], fg=C["muted"]).pack(pady=(16, 4))

        self._num = tk.Label(self, text=str(app.break_secs),
                             font=("Segoe UI", 72, "bold"),
                             bg=C["bg"], fg=C["blue"])
        self._num.pack()

        tk.Label(self, text="seconds remaining",
                 font=("Segoe UI", 10), bg=C["bg"], fg=C["muted"]).pack(pady=(0, 8))

        self._cv  = tk.Canvas(self, width=220, height=10,
                              bg=C["bg_light"], highlightthickness=0, bd=0)
        self._cv.pack(pady=(0, 20))
        self._bar = self._cv.create_rectangle(0, 0, 220, 10, fill=C["blue"], outline="")

        self.update_idletasks()
        sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
        w  = self.winfo_reqwidth();   h  = self.winfo_reqheight()
        self.geometry(f"+{sw // 2 - w // 2}+{sh // 2 - h // 2}")
        self._tick()

    def _tick(self):
        if not self.winfo_exists():
            return
        secs_left = max(0, self.app.break_secs - int(time.monotonic() - self.app.t_break))
        self._num.config(text=str(secs_left))
        self._cv.coords(self._bar, 0, 0, int(220 * secs_left / self.app.break_secs), 10)
        if secs_left > 0:
            self.after(250, self._tick)


# ── Stats window ───────────────────────────────────────────────────────────────
class StatsWindow(tk.Toplevel):
    def __init__(self, parent, data: dict):
        super().__init__(parent)
        self.title("20-20 Timer - Stats")
        self.resizable(False, False)
        self.config(bg=C["bg"])

        streak, includes_today = calc_streak(data)
        today_rec = data.get(today_key(), {})

        hdr = tk.Frame(self, bg=C["bg_light"], pady=18)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"{'🔥' if streak > 0 else '—'}  {streak} day streak",
                 font=("Segoe UI", 22, "bold"),
                 bg=C["bg_light"], fg=C["purple"]).pack()
        if not includes_today and streak > 0:
            tk.Label(hdr, text="Complete a break today to extend it!",
                     font=("Segoe UI", 9), bg=C["bg_light"], fg=C["orange"]).pack(pady=(2, 0))

        tk.Label(self, text="TODAY", font=("Segoe UI", 9, "bold"),
                 bg=C["bg"], fg=C["muted"]).pack(anchor="w", padx=24, pady=(14, 4))

        cols = tk.Frame(self, bg=C["bg"])
        cols.pack(fill="x", padx=20)
        for val, lbl, color in [
            (today_rec.get("score",     0), "Score",     C["purple"]),
            (today_rec.get("completed", 0), "Completed", C["green"]),
            (today_rec.get("missed",    0), "Skipped",   C["red"]),
        ]:
            box = tk.Frame(cols, bg=C["bg_light"], padx=14, pady=10)
            box.pack(side="left", expand=True, fill="both", padx=4)
            tk.Label(box, text=str(val), font=("Segoe UI", 28, "bold"),
                     bg=C["bg_light"], fg=color).pack()
            tk.Label(box, text=lbl, font=("Segoe UI", 9),
                     bg=C["bg_light"], fg=C["muted"]).pack()

        total = sum(r.get("score", 0) for r in data.values())
        tk.Label(self, text=f"All-time breaks completed: {total}",
                 font=("Segoe UI", 9), bg=C["bg"], fg=C["muted"]).pack(
                 anchor="w", padx=24, pady=(10, 2))

        tk.Label(self, text="LAST 14 DAYS", font=("Segoe UI", 9, "bold"),
                 bg=C["bg"], fg=C["muted"]).pack(anchor="w", padx=24, pady=(10, 2))

        cw, ch = 380, 110
        cv = tk.Canvas(self, bg=C["bg"], highlightthickness=0, width=cw, height=ch)
        cv.pack(padx=20, pady=(0, 4))

        days   = [(datetime.date.today() - datetime.timedelta(days=i)).isoformat()
                  for i in range(13, -1, -1)]
        scores = [data.get(d, {}).get("score", 0) for d in days]
        max_s  = max(scores) if max(scores) > 0 else 1
        bar_w, gap = 20, 7
        x_off = (cw - (len(days) * (bar_w + gap) - gap)) // 2
        bar_h_max = 78

        for i, (day, score) in enumerate(zip(days, scores)):
            x1 = x_off + i * (bar_w + gap)
            bh = int((score / max_s) * bar_h_max) if score > 0 else 3
            y2 = bar_h_max + 2;  y1 = y2 - bh
            color = C["purple"] if day == today_key() else C["blue"]
            cv.create_rectangle(x1, y1, x1 + bar_w, y2, fill=color, outline="")
            if score > 0:
                cv.create_text(x1 + bar_w // 2, y1 - 6, text=str(score),
                               fill=C["text"], font=("Segoe UI", 7))
            cv.create_text(x1 + bar_w // 2, ch - 4,
                           text=datetime.date.fromisoformat(day).strftime("%d"),
                           fill=C["muted"], font=("Segoe UI", 7))

        tk.Label(self, text="← older          today →",
                 font=("Segoe UI", 8), bg=C["bg"], fg=C["muted"]).pack(anchor="e", padx=28)

        tk.Button(self, text="Close", command=self.destroy,
                  bg=C["bg_light"], fg=C["text"], font=("Segoe UI", 9),
                  relief="flat", padx=24, pady=6).pack(pady=14)

        self.update_idletasks()
        sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
        w  = self.winfo_reqwidth();   h  = self.winfo_reqheight()
        self.geometry(f"+{sw // 2 - w // 2}+{sh // 2 - h // 2}")


# ── Brief flash notification ───────────────────────────────────────────────────
class FlashWindow(tk.Toplevel):
    def __init__(self, parent, msg: str, color: str):
        super().__init__(parent)
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        self.config(bg=color)
        tk.Label(self, text=msg, font=("Segoe UI", 11, "bold"),
                 bg=color, fg="#000000", padx=20, pady=12).pack()
        self.update_idletasks()
        sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
        w  = self.winfo_reqwidth();   h  = self.winfo_reqheight()
        self.geometry(f"+{sw - w - 20}+{sh - h - 60}")
        self.after(2500, self.destroy)


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.run()
