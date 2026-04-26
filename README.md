# 20-20 Break Timer

A lightweight Windows system tray app that reminds you to take regular movement breaks throughout your workday.

Built around the idea of periodic screen/sitting breaks — work for a set interval, then step away, look away, breathe.

> **v1.1.0** adds a weekly **monitoring schedule** (per-day windows that govern when the app auto-prompts), a 12h/24h time-format toggle, and an isolated `.venv`-based setup.

## Features

- **System tray icon** — lives quietly in your taskbar, showing time remaining on the current cycle
- **Configurable intervals** — set work duration and break duration in seconds, minutes, or hours
- **Escalating alerts** — gentle beep when a break is due, urgent beep if you ignore it too long
- **Break countdown** — full-screen countdown window during breaks
- **Stats tracking** — daily completed/skipped counts, streak tracking, 14-day bar chart
- **Pause / Resume** — pause the timer when you step away or attend a meeting
- **Monitoring schedule** *(new in 1.1.0)* — per-day time windows that gate when the app auto-starts the timer; supports multiple windows per day (e.g. lunch break exclusion); manual start always works outside scheduled hours
- **12h / 24h time format** *(new in 1.1.0)* — toggle in Settings or the schedule editor
- **Boundary popups** *(new in 1.1.0)* — informed when a monitoring window opens or closes mid-cycle, with the option to override the schedule
- **Start with Windows** — optional autostart via the Windows registry
- **Start minimised** — can launch straight to the tray with no window
- **Isolated `.venv`** *(new in 1.1.0)* — `setup.bat` creates a project-local virtual environment so the app isn't affected by other Pythons on PATH

## Screenshots

### Core windows

| Main Timer | Stats | Settings |
|------------|-------|----------|
| ![Main timer window showing countdown](screenshots/Screenshot%202026-03-16%20123252.png) | ![Stats window showing streak and 14-day chart](screenshots/Screenshot%202026-03-16%20123346.png) | ![Settings window with schedule and time-format options](screenshots/Screenshot%202026-04-26%20081913.png) |

### Monitoring schedule (new in 1.1.0)

The schedule editor and the out-of-schedule state of the main window:

| Schedule editor | Out of schedule |
|-----------------|-----------------|
| ![Weekly monitoring schedule with draggable windows](screenshots/Screenshot%202026-04-26%20081803.png) | ![Main window showing OUT OF SCHEDULE state](screenshots/Screenshot%202026-04-26%20081728.png) |

## Requirements

- Windows 10/11
- Python 3.8+ (the [Windows Python Launcher](https://docs.python.org/3/using/windows.html#launcher) is recommended — `setup.bat` uses it automatically)
- [Pillow](https://pypi.org/project/Pillow/) and [pystray](https://pypi.org/project/pystray/) — installed into a project-local `.venv`

## Setup

**Option A — automated (recommended):**

```
setup.bat
```

This script will:

1. Locate a Python install (preferring `py -3` so it skips Pythons bundled with other apps)
2. Install Python via `winget` if none is found
3. Create a project-local `.venv` virtual environment
4. Install Pillow and pystray into the `.venv`

**Option B — manual:**

```
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Running

Double-click `run.bat`, which launches `.venv\Scripts\pythonw.exe 20-20.py` with no console window.

If you skipped `setup.bat`, `run.bat` falls back to `pyw` / `pythonw` from PATH — but the `.venv` route is more reliable.

## Usage

| Action | How |
|--------|-----|
| Open main window | Left-click or double-click the tray icon |
| Pause / Resume | Tray menu → Pause Timer |
| Take a break now | Tray menu → Take Break Now |
| View stats | Tray menu → Show Stats |
| Edit schedule | Tray menu → Schedule  (or main window → Schedule) |
| Change intervals | Tray menu → Settings |
| Quit | Tray menu → Quit |

Closing the main window hides it to the tray — the timer keeps running.

## Monitoring schedule

Opens from the **Schedule** button on the main window, the tray menu, or the **Edit schedule…** button in Settings.

- **7 columns, Sun → Sat**, each a vertical 24-hour timeline
- **Drag** a green block to move it; **drag its top or bottom edge** to resize
- **Right-click** a block to delete it
- **+ Add window** — append another window to that day (multiple per day supported, e.g. to exclude lunch)
- **15-minute snap** when dragging
- **Time format** — toggle 12-hour / 24-hour (also in Settings)
- **Enable monitoring schedule** — master switch; when off, the app behaves like 1.0 (always auto-monitoring)

The default schedule is **Mon–Fri 09:00–17:00, weekends empty**.

### How the schedule interacts with the timer

- **Inside a window** — the app auto-starts and prompts for breaks as normal
- **Outside a window** — the timer is auto-paused; the main window shows `OUT OF SCHEDULE` and the tray icon shows a `z` badge
- **Manual override** — you can always click **Resume Timer** or **Take Break Now**; the timer runs until the next scheduled window begins, at which point the override is cleared automatically
- **Window starts mid-session** — popup informs you the monitoring window has begun and a fresh work interval has started
- **Window ends mid-session** — popup pauses the timer and offers **Dismiss** (respect the schedule) or **Continue anyway** (override until the next window)

## Settings

Open **Settings** from the tray menu or main window.

| Setting | Default | Description |
|---------|---------|-------------|
| Time between breaks | 20 minutes | How long you work before a break is triggered |
| Break duration | 20 seconds | How long each break lasts |
| Start minimised | Off | Launch directly to tray with no window |
| Start with Windows | Off | Add to Windows startup via registry |
| Monitoring schedule | Mon–Fri 09:00–17:00 | Per-day windows that gate auto-monitoring |
| Time format | 12-hour | Display format for schedule times |

Settings are saved to `settings.json` in the app folder.

## Files

| File | Purpose |
|------|---------|
| `20-20.py` | Main application |
| `run.bat` | Launch shortcut (uses `.venv` if present, falls back to `pyw`) |
| `setup.bat` | Create `.venv` and install dependencies |
| `requirements.txt` | Python dependency list |
| `.venv/` | Project-local virtual environment (created by setup, gitignored) |
| `settings.json` | Saved settings (gitignored) |
| `timer_data.json` | Break history and stats (gitignored) |
