# Saddle validation driver for GitHub Actions and local operators.

[CmdletBinding()]
param(
    [ValidateSet(
        "all",
        "quality-gates",
        "core-policy",
        "rust-workspace",
        "integration",
        "config-parse"
    )]
    [string]$Suite = "all",
    [string]$Output = "results/saddle-validation"
)

$ErrorActionPreference = "Continue"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RepoRoot

New-Item -ItemType Directory -Force -Path $Output -ErrorAction Stop | Out-Null
$results = New-Object System.Collections.Generic.List[object]

function Invoke-SaddleStep {
    param(
        [string]$Name,
        [string]$Command,
        [scriptblock]$Body
    )

    $logPath = Join-Path $Output "$Name.log"
    Write-Host "==> $Name"
    Write-Host "    $Command"
    $started = Get-Date
    $global:LASTEXITCODE = 0
    & $Body 2>&1 | Tee-Object -FilePath $logPath -ErrorAction Stop
    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    $elapsed = [math]::Round(((Get-Date) - $started).TotalSeconds, 2)
    $status = if ($exitCode -eq 0) { "passed" } else { "failed" }

    $results.Add([pscustomobject]@{
        name = $Name
        command = $Command
        status = $status
        exit_code = $exitCode
        elapsed_seconds = $elapsed
        log = $logPath
    })

    if ($exitCode -ne 0) {
        Write-Host "FAILED: $Name"
    }
    $global:LASTEXITCODE = 0
}

$runQuality = $Suite -in @("all", "quality-gates")
$runCore = $Suite -in @("all", "core-policy")
$runRust = $Suite -in @("all", "rust-workspace")
$runIntegration = $Suite -in @("all", "integration")
$runConfig = $Suite -in @("all", "config-parse")

if ($runQuality) {
    Invoke-SaddleStep "format-check" "cargo fmt --all --check" {
        cargo fmt --all --check
    }
    Invoke-SaddleStep "workspace-check" "cargo check --workspace --all-targets --locked" {
        cargo check --workspace --all-targets --locked
    }
    Invoke-SaddleStep "workspace-clippy" "cargo clippy --workspace --all-targets --locked -- -D warnings -A clippy::pedantic" {
        cargo clippy --workspace --all-targets --locked -- -D warnings -A clippy::pedantic
    }
}

if ($runCore) {
    Invoke-SaddleStep "router-policy" "cargo test -p mai-router --locked" {
        cargo test -p mai-router --locked
    }
    Invoke-SaddleStep "compliance-policy" "cargo test -p mai-compliance --locked" {
        cargo test -p mai-compliance --locked
    }
}

if ($runRust) {
    Invoke-SaddleStep "rust-workspace" "cargo test --workspace --locked" {
        cargo test --workspace --locked
    }
}

if ($runIntegration) {
    Invoke-SaddleStep "action-authorization" "cargo test -p saddle-bridge --test sad34_action_gate --locked" {
        cargo test -p saddle-bridge --test sad34_action_gate --locked
    }
    Invoke-SaddleStep "bridge-contracts" "cargo test -p saddle-bridge --test contract_properties --locked" {
        cargo test -p saddle-bridge --test contract_properties --locked
    }
    Invoke-SaddleStep "saddle-conformance" "cargo test -p saddle-conformance --locked" {
        cargo test -p saddle-conformance --locked
    }
    Invoke-SaddleStep "sad43-professional-scheduler" "python tools/verify_sad43_professional_scheduler.py --root . --evidence-output test-evidence/saddle/SAD-43/professional-scheduler-gate.json --verify" {
        python tools/verify_sad43_professional_scheduler.py --root . --evidence-output test-evidence/saddle/SAD-43/professional-scheduler-gate.json --verify
    }
}

if ($runConfig) {
    Invoke-SaddleStep "config-parse" "parse every tracked TOML configuration" {
        python -c "import pathlib,tomllib; files=sorted(pathlib.Path('config').rglob('*.toml')); [tomllib.loads(p.read_text(encoding='utf-8')) for p in files]; print(f'parsed {len(files)} TOML files')"
    }
}

$summaryPath = Join-Path $Output "summary.json"
$results | ConvertTo-Json -Depth 5 | Set-Content -Path $summaryPath -Encoding utf8 -ErrorAction Stop

$markdownPath = Join-Path $Output "summary.md"
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# Saddle Workspace Validation")
$lines.Add("")
$lines.Add("| Suite | Status | Seconds | Command |")
$lines.Add("|---|---:|---:|---|")
foreach ($result in $results) {
    $lines.Add("| $($result.name) | $($result.status) | $($result.elapsed_seconds) | ``$($result.command)`` |")
}
$lines | Set-Content -Path $markdownPath -Encoding utf8 -ErrorAction Stop

$failed = @($results | Where-Object { $_.status -ne "passed" })
if ($failed.Count -gt 0) {
    Write-Host "Saddle validation completed with failures. See $Output."
    exit 1
}

Write-Host "Saddle validation completed successfully. See $Output."
exit 0
