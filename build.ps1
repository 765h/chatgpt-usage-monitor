$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== ClaudeMonitor Build ===" -ForegroundColor Cyan

python -m pip install pyinstaller --quiet

if (-not (Test-Path "$Root\chrome_extension.crx")) {
    Write-Error "chrome_extension.crx not found. Run setup.ps1 first."
    exit 1
}
if (-not (Test-Path "$Root\extension.pem")) {
    Write-Error "extension.pem not found. Run setup.ps1 first."
    exit 1
}

Write-Host "Building exe..." -ForegroundColor Yellow

$args_list = @(
    "-m", "PyInstaller",
    "--onefile",
    "--windowed",
    "--name", "ClaudeMonitor",
    "--distpath", "$Root\dist",
    "--workpath", "$Root\build",
    "--specpath", "$Root",
    "--add-data", "$Root\chrome_extension.crx;.",
    "--add-data", "$Root\extension.pem;.",
    "--hidden-import", "pystray._win32",
    "--hidden-import", "PIL.Image",
    "--hidden-import", "PIL.ImageDraw",
    "--hidden-import", "PIL.ImageFont",
    "--hidden-import", "winreg",
    "--collect-all", "pystray",
    "$Root\main.py"
)

& python $args_list

if (Test-Path "$Root\dist\ClaudeMonitor.exe") {
    Remove-Item "$Root\build" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item "$Root\ClaudeMonitor.spec" -Force -ErrorAction SilentlyContinue
    Write-Host "Done: $Root\dist\ClaudeMonitor.exe" -ForegroundColor Green
} else {
    Write-Error "Build failed."
    exit 1
}
