@echo off
:: Prefer the project's .venv if setup.bat has been run.
if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp020-20.py"
    exit /b
)

:: No venv — fall back to the Windows Python Launcher, then PATH pythonw.
where pyw >nul 2>&1
if %errorlevel% == 0 (
    start "" pyw "%~dp020-20.py"
    exit /b
)
where pythonw >nul 2>&1
if %errorlevel% == 0 (
    start "" pythonw "%~dp020-20.py"
    exit /b
)
echo Python not found on PATH. Run setup.bat first.
pause
