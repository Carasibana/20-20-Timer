@echo off
echo 20-20 Timer Setup
echo -----------------
echo.

set "VENV=%~dp0.venv"
set "REQS=%~dp0requirements.txt"

:: Find a usable Python. Prefer the Windows Python Launcher (py) so we skip
:: bundled Pythons from other apps (e.g. Inkscape) that come earlier in PATH.
set "PYEXE="
where py >nul 2>&1 && set "PYEXE=py -3"
if "%PYEXE%"=="" (
    where python >nul 2>&1 && set "PYEXE=python"
)

if "%PYEXE%"=="" (
    echo Python not found. Attempting to install via winget...
    echo.
    winget install -e --id Python.Python.3 --accept-package-agreements --accept-source-agreements
    if %errorlevel% == 0 (
        echo.
        echo Python installed! Please close this window and run setup.bat again.
        echo ^(Python needs a fresh terminal to be available.^)
        goto :end
    )
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
)

echo Python found: %PYEXE%

if not exist "%VENV%\Scripts\pythonw.exe" (
    echo Creating virtual environment in .venv ...
    %PYEXE% -m venv "%VENV%"
    if errorlevel 1 (
        echo Failed to create virtual environment.
        goto :end
    )
) else (
    echo Virtual environment already exists.
)

echo Installing dependencies into .venv ...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip >nul
"%VENV%\Scripts\python.exe" -m pip install -r "%REQS%"
if errorlevel 1 (
    echo Dependency install failed.
    goto :end
)

echo.
echo Done! Run the timer with run.bat
echo.

:end
pause
