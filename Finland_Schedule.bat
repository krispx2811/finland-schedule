@echo off
title Finland Optical Center
color 0B
cd /d "%~dp0"

:menu
cls
echo.
echo ============================================
echo   Finland Optical Center - Schedule Manager
echo ============================================
echo.
echo   1. Run the App
echo   2. Build .exe (one-time, creates standalone app)
echo   3. Install / Reinstall Dependencies
echo   4. Exit
echo.
set /p choice="Choose an option (1-4): "

if "%choice%"=="1" goto run
if "%choice%"=="2" goto build
if "%choice%"=="3" goto install
if "%choice%"=="4" exit /b 0
goto menu


:checkpython
python --version >nul 2>&1
if %errorlevel% neq 0 (
    cls
    echo.
    echo [!] Python is NOT installed.
    echo.
    echo Please install Python 3:
    echo   1. Download from https://www.python.org/downloads/
    echo   2. IMPORTANT: Check "Add Python to PATH" during install
    echo   3. Run this script again after installing
    echo.
    pause
    start https://www.python.org/downloads/
    exit /b 1
)
exit /b 0


:install
cls
call :checkpython
if %errorlevel% neq 0 exit /b 1
echo.
echo Installing dependencies...
echo.
python -m pip install --upgrade pip
python -m pip install flask reportlab openpyxl pyinstaller
if %errorlevel% neq 0 (
    echo.
    echo Trying with trusted hosts...
    python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org flask reportlab openpyxl pyinstaller
)
echo.
echo ============================================
echo   Dependencies installed!
echo ============================================
pause
goto menu


:run
cls
call :checkpython
if %errorlevel% neq 0 exit /b 1

REM Auto-install if flask is missing
python -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo First run detected. Installing dependencies...
    python -m pip install flask reportlab openpyxl
)

echo.
echo ============================================
echo   Starting Finland Optical Center
echo ============================================
echo.
echo The app will open in your browser automatically.
echo Press Ctrl+C in this window to STOP the app.
echo.
python run.py
pause
goto menu


:build
cls
call :checkpython
if %errorlevel% neq 0 exit /b 1

echo.
echo Installing build tools...
python -m pip install --upgrade pip
python -m pip install flask reportlab openpyxl pyinstaller
echo.

echo Cleaning old builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "Finland Schedule.spec" del "Finland Schedule.spec"
echo.

echo Building .exe (this takes 1-3 minutes)...
echo.
pyinstaller --onefile --windowed ^
  --name "Finland Schedule" ^
  --add-data "schedule_app\templates;schedule_app\templates" ^
  --add-data "schedule_app\static;schedule_app\static" ^
  --add-data "New Schedule.xlsx;." ^
  --hidden-import schedule_app ^
  --hidden-import schedule_app.database ^
  --hidden-import schedule_app.models ^
  --hidden-import schedule_app.config ^
  --hidden-import schedule_app.scheduler ^
  --hidden-import schedule_app.excel_import ^
  --hidden-import schedule_app.excel_export ^
  --hidden-import schedule_app.pdf_export ^
  --hidden-import schedule_app.web_app ^
  run.py

if %errorlevel% neq 0 (
    echo.
    echo [!] Build failed.
    pause
    goto menu
)

echo.
echo ============================================
echo   BUILD SUCCESSFUL!
echo ============================================
echo.
echo Your standalone app is at:
echo   dist\Finland Schedule.exe
echo.
echo Double-click it to run anywhere - no Python needed.
echo.
pause
goto menu
