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
& $python -m qaforge context test-design | Out-Null

Write-Step "Offline smoke tests"
& $python -m pytest -m smoke -q

if ($Full) {
    Write-Step "Full pytest run"
    & $python -m pytest -q

    Write-Step "QAForge runner"
    & $python -m qaforge run
}
else {
    Write-Host ""
    Write-Host "Basic local verification passed." -ForegroundColor Green
    Write-Host "Run full browser-backed checks with:"
    Write-Host "  .\scripts\verify-local.ps1 -Full"
}
