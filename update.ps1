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
    $remaining = @(Get-Process ChatGPTUsageMonitor -ErrorAction SilentlyContinue)
    for ($attempt = 0; $attempt -lt 50 -and $remaining.Count -gt 0; $attempt++) {
        Start-Sleep -Milliseconds 100
        $remaining = @(Get-Process ChatGPTUsageMonitor -ErrorAction SilentlyContinue)
    }
    if ($remaining.Count -gt 0) {
        Write-Error "既存プロセスが5秒以内に終了しないため、差し替えを中止しました。"
        exit 1
    }
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
