# Run the whole test suite (no third-party packages required).
# Usage: .\scripts\test.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    python -m unittest discover -s tests -v
} finally {
    Pop-Location
}
