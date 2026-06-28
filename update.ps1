$Root      = Split-Path -Parent $MyInvocation.MyCommand.Path
$NewExe    = "$Root\dist\ClaudeMonitor.exe"
$InstallDir = "$env:APPDATA\ClaudeMonitor"
$InstalledExe = "$InstallDir\ClaudeMonitor.exe"

if (-not (Test-Path $NewExe)) {
    Write-Error "dist\ClaudeMonitor.exe が見つかりません。先に build.ps1 を実行してください。"
    exit 1
}

Write-Host "=== ClaudeMonitor Update ===" -ForegroundColor Cyan

$procs = Get-Process ClaudeMonitor -ErrorAction SilentlyContinue
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
$running = Get-Process ClaudeMonitor -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "Done (PID: $($running[0].Id))" -ForegroundColor Green
} else {
    Write-Error "起動に失敗しました。"
}
