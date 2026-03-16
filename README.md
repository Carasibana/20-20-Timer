# 20-20 Break Timer

A lightweight Windows system tray app that reminds you to take regular movement breaks throughout your workday.

Built around the idea of periodic screen/sitting breaks — work for a set interval, then step away, look away, breathe.

## Features

- **System tray icon** — lives quietly in your taskbar, showing time remaining on the current cycle
- **Configurable intervals** — set work duration and break duration in seconds, minutes, or hours
- **Escalating alerts** — gentle beep when a break is due, urgent beep if you ignore it too long
- **Break countdown** — full-screen countdown window during breaks
- **Stats tracking** — daily completed/skipped counts, streak tracking, 14-day bar chart
- **Pause / Resume** — pause the timer when you step away or attend a meeting
- **Start with Windows** — optional autostart via the Windows registry
- **Start minimised** — can launch straight to the tray with no window

## Screenshots

| Main Timer | Stats | Settings |
|------------|-------|----------|
| ![Main timer window showing countdown](screenshots/Screenshot%202026-03-16%20123252.png) | ![Stats window showing streak and 14-day chart](screenshots/Screenshot%202026-03-16%20123346.png) | ![Settings window](screenshots/Screenshot%202026-03-16%20123327.png) |

## Requirements

- Windows 10/11
- Python 3.8+
- [Pillow](https://pypi.org/project/Pillow/) and [pystray](https://pypi.org/project/pystray/)

## Setup

**Option A — automated (recommended):**

```
setup.bat
```

This will check whether Python is installed, attempt to install it via `winget` if not, and then install the required dependencies. If automatic installation fails, it will print step-by-step instructions.

**Option B — manual:**

1. Install Python from [python.org](https://www.python.org/downloads/) — tick **"Add Python to PATH"** during install
2. Run:

```
pip install Pillow pystray
```

## Running

Double-click `run.bat`, or:

```
pythonw 20-20.py
```

Using `pythonw` instead of `python` prevents a console window from appearing. The app will appear in your system tray.

## Usage

| Action | How |
|--------|-----|
| Open main window | Left-click or double-click the tray icon |
| Pause / Resume | Tray menu → Pause Timer |
| Take a break now | Tray menu → Take Break Now |
| View stats | Tray menu → Show Stats |
| Change intervals | Tray menu → Settings |
| Quit | Tray menu → Quit |

Closing the main window hides it to the tray — the timer keeps running.

## Settings

Open **Settings** from the tray menu or main window.

| Setting | Default | Description |
|---------|---------|-------------|
| Time between breaks | 20 minutes | How long you work before a break is triggered |
| Break duration | 20 seconds | How long each break lasts |
| Start minimised | Off | Launch directly to tray with no window |
| Start with Windows | Off | Add to Windows startup via registry |

Settings are saved to `settings.json` in the app folder.

## Files

| File | Purpose |
|------|---------|
| `20-20.py` | Main application |
| `run.bat` | Launch shortcut (no console window) |
| `setup.bat` | Install dependencies |
| `settings.json` | Saved settings |
| `timer_data.json` | Break history and stats |
