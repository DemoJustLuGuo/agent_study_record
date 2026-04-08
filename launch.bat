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

set "DEPS_MARKER=.deps_installed"
if /I "%FORCE_PIP_INSTALL%"=="1" goto install_deps
if /I "%SKIP_PIP_INSTALL%"=="1" goto deps_ready
if exist "%DEPS_MARKER%" (
    echo [INFO] Dependency installation skipped. Marker found: %DEPS_MARKER%
    echo [INFO] Use FORCE_PIP_INSTALL=1 to reinstall dependencies.
    goto deps_ready
)

:install_deps
echo [INFO] 正在根据requirements.txt安装依赖...
"%PYTHON_EXE%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Python dependency installation failed.
    pause
    exit /b 1
)
>"%DEPS_MARKER%" echo installed_at=%DATE% %TIME%
echo [INFO] Dependency installation completed.

:deps_ready

if "%OPENAI_API_KEY%"=="" if not "%SILICONFLOW_API_KEY%"=="" set "OPENAI_API_KEY=%SILICONFLOW_API_KEY%"

if "%OPENAI_API_KEY%"=="" (
    echo [WARN]  没有设置 OPENAI_API_KEY.
    set /p OPENAI_API_KEY=Please input OpenAI-compatible API key [sk-...]: 
)

if "%OPENAI_API_KEY%"=="" (
    echo [ERROR] 已经包含了OPENAI_API_KEY.
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

echo [INFO] 正在启动WebUI...
echo [INFO] URL: http://%APP_HOST%:%APP_PORT%
"%PYTHON_EXE%" -m app.main
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo [ERROR] Gradio app exited with code %EXIT_CODE%.
)

pause
exit /b %EXIT_CODE%
