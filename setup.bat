@echo off
echo 20-20 Timer Setup
echo -----------------
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% == 0 (
    echo Python found. Installing dependencies...
    goto :install
)

:: Python not found — try winget
echo Python not found. Attempting to install via winget...
echo.
winget install -e --id Python.Python.3 --accept-package-agreements --accept-source-agreements
if %errorlevel% == 0 (
    echo.
    echo Python installed! Please close this window and run setup.bat again.
    echo ^(Python needs a fresh terminal to be available.^)
    goto :end
)

:: winget failed — give manual instructions
echo.
echo ============================================================
echo  Couldn't install Python automatically.
echo  Please install it manually:
echo.
echo  1. Go to: https://www.python.org/downloads/
echo  2. Download and run the installer
echo  3. IMPORTANT: tick "Add Python to PATH" during install
echo  4. Once done, run this setup.bat again
echo ============================================================
goto :end

:install
pip install Pillow pystray
echo.
echo Done! Run the timer with run.bat ^(or: python "20-20.py"^)
echo.

:end
pause
