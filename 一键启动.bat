@echo off
setlocal

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

if "%SILICONFLOW_API_KEY%"=="" if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        if /I "%%A"=="SILICONFLOW_API_KEY" set "SILICONFLOW_API_KEY=%%B"
    )
)

if "%SILICONFLOW_API_KEY%"=="" (
    echo [WARN] SILICONFLOW_API_KEY is not set.
    set /p SILICONFLOW_API_KEY=Please input SiliconFlow API key [sk-...]: 
)

if "%SILICONFLOW_API_KEY%"=="" (
    echo [ERROR] SILICONFLOW_API_KEY is required.
    pause
    exit /b 1
)

if "%APP_HOST%"=="" set "APP_HOST=127.0.0.1"
if "%APP_PORT%"=="" set "APP_PORT=7860"
if "%BACKEND_URL%"=="" set "BACKEND_URL=http://%APP_HOST%:%APP_PORT%"

if "%PYTHONPATH%"=="" (
    set "PYTHONPATH=%CD%"
) else (
    set "PYTHONPATH=%CD%;%PYTHONPATH%"
)

where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js 18+.
    pause
    exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm not found. Please reinstall Node.js.
    pause
    exit /b 1
)

if not exist "electron\package.json" (
    echo [ERROR] electron\package.json not found.
    pause
    exit /b 1
)

echo [INFO] Checking Electron dependencies...
pushd electron

if not exist "node_modules" (
    echo [INFO] node_modules not found, running npm install...
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed.
        popd
        pause
        exit /b 1
    )
) else (
    call npm ls --depth=0 >nul 2>&1
    if errorlevel 1 (
        echo [INFO] Detected invalid/missing npm packages, running npm install...
        call npm install
        if errorlevel 1 (
            echo [ERROR] npm install failed.
            popd
            pause
            exit /b 1
        )
    )
)

echo [INFO] Starting Electron desktop app...
echo [INFO] Backend URL: %BACKEND_URL%
call npm start
set "EXIT_CODE=%ERRORLEVEL%"
popd

if not "%EXIT_CODE%"=="0" (
    echo [ERROR] Electron app exited with code %EXIT_CODE%.
)

pause
exit /b %EXIT_CODE%
