# Claude Usage Monitor - Setup Script
# Usage: powershell -ExecutionPolicy Bypass -File setup.ps1

# 管理者権限が必要なため、なければ自動昇格
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process PowerShell -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Path)`"" -Wait
    exit
}

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExtDir  = Join-Path $Root "chrome_extension"
$PemPath = Join-Path $Root "extension.pem"
$CrxPath = Join-Path $Root "chrome_extension.crx"

$ChromeKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
$Chrome = (Get-ItemProperty $ChromeKey -ErrorAction SilentlyContinue)."(default)"
if (-not $Chrome) { $Chrome = "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe" }

$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) { Write-Error "Python not found"; exit 1 }
$Python = $PythonCmd.Source

Write-Host ""
Write-Host "=== Claude Usage Monitor Setup ===" -ForegroundColor Cyan

# [1] pip install
Write-Host "[1/4] Installing Python dependencies..."
& $Python -m pip install -r "$Root\requirements.txt" --quiet
Write-Host "  Done" -ForegroundColor Green

# [2] Pack Chrome extension as CRX
Write-Host "[2/4] Packing Chrome extension..."
if (Test-Path $CrxPath) { Remove-Item $CrxPath -Force }

$packArgs = @("--pack-extension=$ExtDir")
if (Test-Path $PemPath) { $packArgs += "--pack-extension-key=$PemPath" }
& $Chrome $packArgs 2>$null
Start-Sleep -Seconds 3

# Chrome outputs chrome_extension.crx in the parent of ExtDir
if (-not (Test-Path $CrxPath)) {
    Write-Error "CRX generation failed. Make sure Chrome is installed."
    exit 1
}
# Move the generated PEM to $PemPath if it was newly created
$generatedPem = Join-Path $Root "chrome_extension.pem"
if ((Test-Path $generatedPem) -and ($generatedPem -ne $PemPath)) {
    Move-Item $generatedPem $PemPath -Force
}
Write-Host "  Done: $CrxPath" -ForegroundColor Green

# [3] Compute extension ID and register Chrome policy
Write-Host "[3/4] Registering Chrome extension..."
$ExtId = & $Python -c "
import base64, hashlib
with open(r'$PemPath') as f:
    lines = [l.strip() for l in f if l.strip() and not l.startswith('---')]
der = base64.b64decode(''.join(lines))
h = hashlib.sha256(der).digest()
print(''.join(chr(ord('a')+((b>>4)&0xf))+chr(ord('a')+(b&0xf)) for b in h[:16]))
"
$ExtId = $ExtId.Trim()
if (-not $ExtId) { Write-Error "Failed to compute extension ID"; exit 1 }

$CrxUri = "file:///" + $CrxPath.Replace("\", "/")
$RegPath = "HKLM:\SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist"
if (-not (Test-Path $RegPath)) { New-Item -Path $RegPath -Force | Out-Null }
Set-ItemProperty -Path $RegPath -Name "1" -Value "${ExtId};${CrxUri}"
Write-Host "  Done (ID: $ExtId)" -ForegroundColor Green

# [4] Startup task
Write-Host "[4/4] Registering startup task..."
$action   = New-ScheduledTaskAction -Execute $Python -Argument "`"$Root\main.py`"" -WorkingDirectory $Root
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 0) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "ClaudeUsageMonitor" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "  Done" -ForegroundColor Green

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Restart Chrome completely (close all windows)"
Write-Host "  2. Open chrome://extensions/ and verify the extension is installed"
Write-Host "  3. Open claude.ai and log in"
Write-Host "  4. Run: python main.py (auto-starts on next login)"
Write-Host ""
