$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimeRoot = Join-Path $HOME ".cloud-cua\runtime-venv"
$Python = Join-Path $RuntimeRoot "Scripts\python.exe"

if (-not (Test-Path $Python)) {
    python -m venv $RuntimeRoot
}

& $Python -m pip install --upgrade pip
& $Python -m pip install "${ProjectRoot}[h]"
& $Python -I -m cloud_cua.cli install-mcp --python-executable $Python
& $Python -I -m cloud_cua.cli doctor

Write-Host "Cloud CUA is installed for this Windows user. Restart Codex so it reloads MCP configuration."
