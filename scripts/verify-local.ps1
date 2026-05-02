param(
    [switch]$Full
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$workspaceTemp = Join-Path $repoRoot ".tmp"
New-Item -ItemType Directory -Force $workspaceTemp | Out-Null
$env:TMP = $workspaceTemp
$env:TEMP = $workspaceTemp
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $repoRoot ".playwright-browsers"

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $python = $venvPython
}
else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "No .venv Python found and `python` is not on PATH. Run .\scripts\setup-local.ps1 first."
    }
    $python = "python"
}

Write-Step "Python version"
& $python --version

Write-Step "QAForge import check"
& $python -m qaforge --version

Write-Step "Skill/context check"
& $python -m qaforge skills
& $python -m qaforge context test-design *> $null

Write-Step "Offline smoke tests"
& $python -m pytest -m smoke -q --basetemp=".tmp\pytest-smoke"

if ($Full) {
    Write-Step "Full pytest run"
    & $python -m pytest -q --basetemp=".tmp\pytest-full"

    Write-Step "QAForge runner"
    & $python -m qaforge run
}
else {
    Write-Host ""
    Write-Host "Basic local verification passed." -ForegroundColor Green
    Write-Host "Run full browser-backed checks with:"
    Write-Host "  .\scripts\verify-local.ps1 -Full"
}
