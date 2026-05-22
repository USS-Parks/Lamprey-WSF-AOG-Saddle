# Burn-in driver — PowerShell variant.
#
# Usage:
#   scripts\burn-in.ps1                   # default: full suite + sample trace replay
#   scripts\burn-in.ps1 -Quick            # smoke only (cargo test --workspace)
#   scripts\burn-in.ps1 -Output results\x # custom output directory

[CmdletBinding()]
param(
    [switch]$Quick,
    [string]$Output = ""
)

$ErrorActionPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RepoRoot

if ($Output -eq "") {
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    $Output = Join-Path "results" "burn-in-$stamp"
}

New-Item -ItemType Directory -Force -Path $Output | Out-Null
Write-Host "burn-in: writing artifacts to $Output"

# 1. Workspace test suite.
Write-Host "==> cargo test --workspace"
cargo test --workspace 2>&1 | Tee-Object -FilePath (Join-Path $Output "cargo-test.log")

if ($Quick) {
    Write-Host "burn-in: quick mode complete"
    exit 0
}

# 2. Python regression suite.
Write-Host "==> pytest tools/ adapters/"
python -m pytest tools/ adapters/ 2>&1 | Tee-Object -FilePath (Join-Path $Output "pytest.log")

# 3. Hardware-dependent Phase 1 criteria placeholder.
$deferred = @"
The following Phase 1 exit criteria require target hardware and are
intentionally not executed by this burn-in:

- test_scout_config_boots      (1x RTX 4090 + Ollama + Qwen3-14B, <60s)
- test_ranger_config_boots     (2x H100 + vLLM tensor parallel, <90s)
- test_two_gpu_configs         (NVIDIA + AMD)
- test_72_hour_stability       (continuous load, time-dependent)

Run these on the target hardware as part of deployment validation. See
docs/INTEGRATION-COVERAGE.md for the full deferral matrix.
"@
Set-Content -Path (Join-Path $Output "phase1-deferred.txt") -Value $deferred -Encoding utf8

Write-Host "burn-in: artifacts in $Output"
Get-ChildItem $Output
