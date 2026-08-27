$ErrorActionPreference = "Stop"
$Root      = Split-Path -Parent $MyInvocation.MyCommand.Path
$NewExe    = "$Root\dist\ChatGPTUsageMonitor.exe"
$InstallDir = "$env:APPDATA\ChatGPTUsageMonitor"
$InstalledExe = "$InstallDir\ChatGPTUsageMonitor.exe"

if (-not (Test-Path $NewExe)) {
    Write-Error "dist\ChatGPTUsageMonitor.exe が見つかりません。先に build.ps1 を実行してください。"
    exit 1
}

Write-Host "=== ChatGPTUsageMonitor Update ===" -ForegroundColor Cyan

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

$procs = Get-Process ChatGPTUsageMonitor -ErrorAction SilentlyContinue
if ($procs) {
    Write-Host "既存プロセスを停止中..." -ForegroundColor Yellow
    $procs | Stop-Process -Force
    Start-Sleep -Milliseconds 800
}

Write-Host "exe を差し替え中..."
Copy-Item $NewExe $InstalledExe -Force

Write-Host "起動中..."
Start-Process $InstalledExe

Start-Sleep -Milliseconds 1000
$running = Get-Process ChatGPTUsageMonitor -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "Done (PID: $($running[0].Id))" -ForegroundColor Green
} else {
    Write-Error "起動に失敗しました。"
}
