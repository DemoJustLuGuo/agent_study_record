@echo off
setlocal

chcp 65001 >nul
set "PYTHONIOENCODING=UTF-8"
set "PYTHONLEGACYWINDOWSSTDIO="

cd /d "%~dp0"

set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "venv\Scripts\python.exe" set "PYTHON_EXE=%CD%\venv\Scripts\python.exe"
if not defined PYTHON_EXE set "PYTHON_EXE=python"

"%PYTHON_EXE%" --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+ or create .venv.
    pause
    exit /b 1
)

"%PYTHON_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10+ is required.
    "%PYTHON_EXE%" --version
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found.
    pause
    exit /b 1
)

echo [INFO] Verifying/installing Python dependencies from requirements.txt...
"%PYTHON_EXE%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Python dependency installation failed.
    pause
    exit /b 1
)

if "%OPENAI_API_KEY%"=="" if not "%SILICONFLOW_API_KEY%"=="" set "OPENAI_API_KEY=%SILICONFLOW_API_KEY%"

if "%OPENAI_API_KEY%"=="" if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        if /I "%%A"=="OPENAI_API_KEY" set "OPENAI_API_KEY=%%B"
    )
)

if "%OPENAI_API_KEY%"=="" if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        if /I "%%A"=="SILICONFLOW_API_KEY" set "OPENAI_API_KEY=%%B"
    )
)

if "%OPENAI_API_KEY%"=="" (
    echo [WARN] OPENAI_API_KEY is not set.
    set /p OPENAI_API_KEY=Please input OpenAI-compatible API key [sk-...]: 
)

if "%OPENAI_API_KEY%"=="" (
    echo [ERROR] OPENAI_API_KEY is required.
    pause
    exit /b 1
)

if "%SILICONFLOW_API_KEY%"=="" set "SILICONFLOW_API_KEY=%OPENAI_API_KEY%"

if "%APP_HOST%"=="" set "APP_HOST=127.0.0.1"
if "%APP_PORT%"=="" set "APP_PORT=7860"
if "%BACKEND_URL%"=="" set "BACKEND_URL=http://%APP_HOST%:%APP_PORT%"

if "%PYTHONPATH%"=="" (
    set "PYTHONPATH=%CD%"
) else (
    set "PYTHONPATH=%CD%;%PYTHONPATH%"
)

echo [INFO] Starting Gradio app...
echo [INFO] URL: http://%APP_HOST%:%APP_PORT%
"%PYTHON_EXE%" -m app.main
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo [ERROR] Gradio app exited with code %EXIT_CODE%.
)

pause
exit /b %EXIT_CODE%
