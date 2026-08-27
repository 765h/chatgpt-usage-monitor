# ChatGPT Usage Monitor - development setup
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = (Get-Command python -ErrorAction Stop).Source

& $Python -m pip install -r "$Root\requirements.txt" --quiet
Write-Host "Setup complete. Run: python main.py" -ForegroundColor Green
