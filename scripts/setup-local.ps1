param(
    [switch]$SkipBrowserInstall,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Find-Python {
    $candidates = @(
        @{ Command = "python"; Args = @() },
        @{ Command = "py"; Args = @("-3") }
    )

    foreach ($candidate in $candidates) {
        $cmd = Get-Command $candidate.Command -ErrorAction SilentlyContinue
        if (-not $cmd) {
            continue
        }

        try {
            $versionCheck = @"
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
"@
            & $candidate.Command @($candidate.Args) -c $versionCheck *> $null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        }
        catch {
            continue
        }
    }

    Write-Host @"
Python 3.10+ was not found.

Install Python from:
  https://www.python.org/downloads/windows/

During install, check:
  Add python.exe to PATH

Then open a new PowerShell window and run:
  .\scripts\setup-local.ps1
"@ -ForegroundColor Red
    exit 1
}

function Invoke-BasePython {
    param(
        [hashtable]$Python,
        [string[]]$Arguments
    )
    & $Python.Command @($Python.Args) @Arguments
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

Write-Step "Finding Python 3.10+"
$python = Find-Python
Invoke-BasePython -Python $python -Arguments @("--version")

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if ((Test-Path $venvPython) -and -not $Force) {
    Write-Step "Using existing virtual environment"
}
else {
    if ((Test-Path (Join-Path $repoRoot ".venv")) -and $Force) {
        Write-Step "Recreating virtual environment"
        Remove-Item -Recurse -Force (Join-Path $repoRoot ".venv")
    }
    else {
        Write-Step "Creating virtual environment"
    }
    Invoke-BasePython -Python $python -Arguments @("-m", "venv", ".venv")
}

Write-Step "Installing QAForge and test dependencies"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -e ".[test]"

if (-not $SkipBrowserInstall) {
    Write-Step "Installing Playwright Chromium"
    & $venvPython -m playwright install chromium
}
else {
    Write-Host "Skipping Playwright browser install." -ForegroundColor Yellow
}

if (-not (Test-Path ".env")) {
    Write-Step "Creating .env from .env.example"
    Copy-Item ".env.example" ".env"
    Write-Host "Edit .env and add your ANTHROPIC_API_KEY before using plan/generate/heal." -ForegroundColor Yellow
}
else {
    Write-Host ".env already exists; leaving it unchanged." -ForegroundColor Yellow
}

Write-Step "Running offline smoke verification"
& $venvPython -m pytest -m smoke -q
& $venvPython -m qaforge skills

Write-Host ""
Write-Host "Local setup complete." -ForegroundColor Green
Write-Host "Activate it with:" -ForegroundColor Green
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "Next useful commands:"
Write-Host "  python -m qaforge context test-design"
Write-Host "  python -m qaforge plan `"User login with email and password`" --auto"
Write-Host "  python -m qaforge run"
