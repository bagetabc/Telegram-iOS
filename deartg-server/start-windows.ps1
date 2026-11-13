# DearTG local server launcher for Windows PowerShell
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command py -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.11+ is required. Install Python from https://www.python.org/downloads/windows/ and enable Add Python to PATH."
}

$Python = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $Python -m venv .venv
}
$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements.txt

$DataDir = Join-Path $PSScriptRoot "data"
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
$SecretsFile = Join-Path $DataDir "local-secrets.ps1"

if (-not (Test-Path $SecretsFile)) {
    $TokenSecret = (& $VenvPython -c "import secrets; print(secrets.token_hex(32))").Trim()
    $AdminToken = (& $VenvPython -c "import secrets; print(secrets.token_urlsafe(48))").Trim()
    @(
        ('$env:DEARTG_TOKEN_SECRET = ' + (ConvertTo-Json $TokenSecret -Compress))
        ('$env:DEARTG_ADMIN_TOKEN = ' + (ConvertTo-Json $AdminToken -Compress))
    ) | Set-Content -Encoding UTF8 $SecretsFile
    Write-Host "Created persistent local secrets in data\local-secrets.ps1"
}

. $SecretsFile
$env:DEARTG_DATA_DIR = $DataDir

Write-Host ""
Write-Host "DearTG API is starting..."
Write-Host "PC:     http://127.0.0.1:8080"
Write-Host "Docs:   http://127.0.0.1:8080/docs"
Write-Host "Health: http://127.0.0.1:8080/health"
Write-Host "Keep this window open while using DearTG."
Write-Host "Press Ctrl+C to stop."
Write-Host ""

& $VenvPython -m uvicorn app:app --host 0.0.0.0 --port 8080
