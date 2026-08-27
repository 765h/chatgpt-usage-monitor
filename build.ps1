$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = (Get-Command python -ErrorAction Stop).Source
$OutputExe = "$Root\dist\ChatGPTUsageMonitor.exe"

Write-Host "=== ChatGPTUsageMonitor Build ===" -ForegroundColor Cyan

Remove-Item -LiteralPath $OutputExe -Force -ErrorAction SilentlyContinue

& $Python -m pip install -r "$Root\requirements.txt" --quiet
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Building exe..." -ForegroundColor Yellow

$args_list = @(
    "-m", "PyInstaller",
    "--onefile",
    "--windowed",
    "--name", "ChatGPTUsageMonitor",
    "--distpath", "$Root\dist",
    "--workpath", "$Root\build",
    "--specpath", "$Root",
    "--hidden-import", "pystray._win32",
    "--hidden-import", "PIL.Image",
    "--hidden-import", "PIL.ImageDraw",
    "--hidden-import", "PIL.ImageFont",
    "--collect-all", "pystray",
    "$Root\main.py"
)

& $Python $args_list
$BuildExitCode = $LASTEXITCODE
if ($BuildExitCode -ne 0) {
    exit $BuildExitCode
}

if (Test-Path -LiteralPath $OutputExe) {
    Remove-Item "$Root\build" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item "$Root\ChatGPTUsageMonitor.spec" -Force -ErrorAction SilentlyContinue
    Write-Host "Done: $OutputExe" -ForegroundColor Green
} else {
    Write-Error "Build failed."
    exit 1
}
