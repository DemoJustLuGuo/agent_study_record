@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"
if not defined PYTHON_EXE set "PYTHON_EXE=python"

"%PYTHON_EXE%" --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+ or create .venv.
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found.
    pause
    exit /b 1
)

echo [INFO] Checking dependencies...
set "REQ_CHECK_SCRIPT=%TEMP%\req_check_%RANDOM%.py"
> "%REQ_CHECK_SCRIPT%" (
    echo import sys
    echo from importlib import metadata as md
    echo mismatches = []
    echo with open^('requirements.txt', 'r', encoding='utf-8'^) as f:
    echo^    for raw in f:
    echo^        line = raw.strip^(^)
    echo^        if ^(not line^) or line.startswith^('#'^):
    echo^            continue
    echo^        line = line.split^(';', 1^)[0].strip^(^)
    echo^        if not line:
    echo^            continue
    echo^        if '==' in line:
    echo^            pkg, expected = [part.strip^(^) for part in line.split^('==', 1^)]
    echo^            try:
    echo^                installed = md.version^(pkg^)
    echo^            except md.PackageNotFoundError:
    echo^                mismatches.append^(f"{pkg}=={expected} [not installed]"^)
    echo^                continue
    echo^            if installed != expected:
    echo^                mismatches.append^(f"{pkg}=={expected} [installed {installed}]"^)
    echo^        else:
    echo^            pkg = line
    echo^            try:
    echo^                md.version^(pkg^)
    echo^            except md.PackageNotFoundError:
    echo^                mismatches.append^(f"{pkg} [not installed]"^)
    echo if mismatches:
    echo^    print^('[INFO] Dependencies are missing or version-mismatched:'^)
    echo^    for item in mismatches:
    echo^        print^(f' - {item}'^)
    echo^    sys.exit^(1^)
    echo print^('[INFO] Dependencies satisfy requirements.txt'^)
)

"%PYTHON_EXE%" "%REQ_CHECK_SCRIPT%"
set "REQ_STATUS=%ERRORLEVEL%"
del "%REQ_CHECK_SCRIPT%" >nul 2>&1

if not "%REQ_STATUS%"=="0" (
    echo [INFO] Installing dependencies from requirements.txt...
    "%PYTHON_EXE%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed.
        pause
        exit /b 1
    )
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

if "%PYTHONPATH%"=="" (
    set "PYTHONPATH=%CD%"
) else (
    set "PYTHONPATH=%CD%;%PYTHONPATH%"
)

echo [INFO] Starting Flask app on http://%APP_HOST%:%APP_PORT% ...
"%PYTHON_EXE%" -m app.main
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo [ERROR] App exited with code %EXIT_CODE%.
)

pause
exit /b %EXIT_CODE%
