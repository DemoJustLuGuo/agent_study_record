$ErrorActionPreference = "Stop"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "UTF-8"
$env:PYTHONLEGACYWINDOWSSTDIO = ""

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$candidates = @()
if ($isWindows) {
    $candidates += (Join-Path $projectRoot ".venv\Scripts\python.exe")
    $candidates += (Join-Path $projectRoot "venv\Scripts\python.exe")
} else {
    $candidates += (Join-Path $projectRoot ".venv/bin/python")
    $candidates += (Join-Path $projectRoot "venv/bin/python")
}
$candidates += "python3"
$candidates += "python"

$pythonExe = $null
foreach ($candidate in $candidates) {
    if ($candidate -in @("python", "python3")) {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) {
            $pythonExe = $candidate
            break
        }
    } elseif (Test-Path -LiteralPath $candidate) {
        $pythonExe = $candidate
        break
    }
}

if (-not $pythonExe) {
    Write-Host "[ERROR] Python not found. Please install Python 3.10+ or create .venv."
    Read-Host "Press Enter to exit"
    exit 1
}

& $pythonExe --version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Python not found. Please install Python 3.10+ or create .venv."
    Read-Host "Press Enter to exit"
    exit 1
}

& $pythonExe -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Python 3.10+ is required."
    & $pythonExe --version
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not (Test-Path -LiteralPath (Join-Path $projectRoot "requirements.txt"))) {
    Write-Host "[ERROR] requirements.txt not found."
    Read-Host "Press Enter to exit"
    exit 1
}

$depsMarker = Join-Path $projectRoot ".deps_installed"
if ($env:FORCE_PIP_INSTALL -eq "1") {
    $needsInstall = $true
} elseif ($env:SKIP_PIP_INSTALL -eq "1") {
    $needsInstall = $false
} elseif (Test-Path -LiteralPath $depsMarker) {
    Write-Host "[INFO] Dependency installation skipped. Marker found: .deps_installed"
    Write-Host "[INFO] Use FORCE_PIP_INSTALL=1 to reinstall dependencies."
    $needsInstall = $false
} else {
    $needsInstall = $true
}

if ($needsInstall) {
    Write-Host "[INFO] 正在根据requirements.txt安装依赖..."
    & $pythonExe -m pip install --disable-pip-version-check -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Python dependency installation failed."
        Read-Host "Press Enter to exit"
        exit 1
    }
    "installed_at=$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))" | Set-Content -LiteralPath $depsMarker -Encoding UTF8
    Write-Host "[INFO] Dependency installation completed."
}

if (-not $env:OPENAI_API_KEY -and $env:SILICONFLOW_API_KEY) {
    $env:OPENAI_API_KEY = $env:SILICONFLOW_API_KEY
}

if (-not $env:OPENAI_API_KEY) {
    $env:OPENAI_API_KEY = Read-Host "Please input OpenAI-compatible API key [sk-...]"
}

if (-not $env:OPENAI_API_KEY) {
    Write-Host "[ERROR] 缺少 OPENAI_API_KEY。"
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not $env:SILICONFLOW_API_KEY) {
    $env:SILICONFLOW_API_KEY = $env:OPENAI_API_KEY
}

if (-not $env:APP_HOST) { $env:APP_HOST = "127.0.0.1" }
if (-not $env:APP_PORT) { $env:APP_PORT = "7860" }
if (-not $env:BACKEND_URL) { $env:BACKEND_URL = "http://$($env:APP_HOST):$($env:APP_PORT)" }

if (-not $env:PYTHONPATH) {
    $env:PYTHONPATH = $projectRoot
} else {
    $separator = if ($isWindows) { ";" } else { ":" }
    $env:PYTHONPATH = "$projectRoot$separator$($env:PYTHONPATH)"
}

Write-Host "[INFO] 正在启动WebUI..."
Write-Host "[INFO] URL: http://$($env:APP_HOST):$($env:APP_PORT)"
& $pythonExe -m app.main
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host "[ERROR] Gradio app exited with code $exitCode."
}

Read-Host "Press Enter to exit"
exit $exitCode
