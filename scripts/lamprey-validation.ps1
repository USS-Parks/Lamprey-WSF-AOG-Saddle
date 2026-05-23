# Lamprey validation driver for GitHub Actions and local operators.
#
# Examples:
#   scripts\lamprey-validation.ps1 -Suite router
#   scripts\lamprey-validation.ps1 -Suite all -Output results\lamprey-validation

[CmdletBinding()]
param(
    [ValidateSet(
        "all",
        "quality-gates",
        "router",
        "compliance",
        "rust-workspace",
        "policy-stress",
        "audit-stress",
        "release-policy",
        "release-audit",
        "python-adapters",
        "python-ipc",
        "python-trace-sim",
        "config-parse",
        "burn-in"
    )]
    [string]$Suite = "all",
    [string]$Output = "results/lamprey-validation"
)

$ErrorActionPreference = "Continue"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RepoRoot

New-Item -ItemType Directory -Force -Path $Output -ErrorAction Stop | Out-Null
$TempRoot = Join-Path $Output "tmp"
New-Item -ItemType Directory -Force -Path $TempRoot -ErrorAction Stop | Out-Null

$results = New-Object System.Collections.Generic.List[object]

function Invoke-LampreyStep {
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
    $exitCode = if ($LASTEXITCODE -ne $null) { $LASTEXITCODE } else { 0 }
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

$runQuality = $Suite -eq "all" -or $Suite -eq "quality-gates"
$runRouter = $Suite -eq "all" -or $Suite -eq "router"
$runCompliance = $Suite -eq "all" -or $Suite -eq "compliance"
$runRust = $Suite -eq "all" -or $Suite -eq "rust-workspace"
$runPolicyStress = $Suite -eq "all" -or $Suite -eq "policy-stress"
$runAuditStress = $Suite -eq "all" -or $Suite -eq "audit-stress"
$runReleasePolicy = $Suite -eq "all" -or $Suite -eq "release-policy"
$runReleaseAudit = $Suite -eq "all" -or $Suite -eq "release-audit"
$runPythonAdapters = $Suite -eq "all" -or $Suite -eq "python-adapters"
$runPythonIpc = $Suite -eq "all" -or $Suite -eq "python-ipc"
$runPythonTrace = $Suite -eq "all" -or $Suite -eq "python-trace-sim"
$runConfigParse = $Suite -eq "all" -or $Suite -eq "config-parse"
$runBurnIn = $Suite -eq "burn-in"

if ($runQuality) {
    Invoke-LampreyStep "format-check" "cargo fmt --check" {
        cargo fmt --check
    }

    Invoke-LampreyStep "workspace-check" "cargo check --workspace" {
        cargo check --workspace
    }

    Invoke-LampreyStep "compliance-clippy" "cargo clippy -p mai-compliance --all-targets -- -D warnings -A clippy::pedantic" {
        cargo clippy -p mai-compliance --all-targets -- -D warnings -A clippy::pedantic
    }
}

if ($runRouter) {
    Invoke-LampreyStep "router" "cargo test -p mai-router" {
        cargo test -p mai-router
    }
}

if ($runCompliance) {
    Invoke-LampreyStep "compliance" "cargo test -p mai-compliance" {
        cargo test -p mai-compliance
    }
}

if ($runPolicyStress) {
    Invoke-LampreyStep "policy-stress" "cargo test -p mai-compliance --lib policy:: --quiet x5" {
        for ($i = 1; $i -le 5; $i++) {
            cargo test -p mai-compliance --lib policy:: --quiet
            if ($LASTEXITCODE -ne 0) { return }
        }
    }
}

if ($runAuditStress) {
    Invoke-LampreyStep "audit-stress" "cargo test -p mai-compliance --lib audit:: --quiet x5" {
        for ($i = 1; $i -le 5; $i++) {
            cargo test -p mai-compliance --lib audit:: --quiet
            if ($LASTEXITCODE -ne 0) { return }
        }
    }
}

if ($runReleasePolicy) {
    Invoke-LampreyStep "release-policy" "cargo test -p mai-compliance --release --lib policy::" {
        cargo test -p mai-compliance --release --lib policy::
    }
}

if ($runReleaseAudit) {
    Invoke-LampreyStep "release-audit" "cargo test -p mai-compliance --release --lib audit::" {
        cargo test -p mai-compliance --release --lib audit::
    }
}

if ($runRust) {
    Invoke-LampreyStep "rust-workspace" "cargo test --workspace" {
        cargo test --workspace
    }
}

if ($runPythonAdapters) {
    Invoke-LampreyStep "python-adapters" "python -m pytest adapters -q" {
        python -m pytest adapters -q
    }
}

if ($runPythonIpc) {
    Invoke-LampreyStep "python-ipc" "python -m pytest adapters/tests/test_ipc_protocol.py -q" {
        python -m pytest adapters/tests/test_ipc_protocol.py -q
    }
}

if ($runPythonTrace) {
    Invoke-LampreyStep "python-trace-sim" "python -m pytest tools/trace-tools/tests tools/simulator/tests -q" {
        $env:TEMP = $TempRoot
        $env:TMP = $TempRoot
        $env:MAI_PYTEST_TMP = $TempRoot
        python -m pytest tools/trace-tools/tests tools/simulator/tests -q
    }
}

if ($runConfigParse) {
    Invoke-LampreyStep "config-parse" "python -c parse compliance TOML" {
        python -c "import pathlib, tomllib; files=['config/compliance/policy.toml','config/compliance/audit.toml']; [tomllib.loads(pathlib.Path(f).read_text(encoding='utf-8')) for f in files]; print('parsed ' + ', '.join(files))"
    }
}

if ($runBurnIn) {
    Invoke-LampreyStep "burn-in" "scripts\burn-in.ps1 -Output $Output\burn-in" {
        scripts\burn-in.ps1 -Output (Join-Path $Output "burn-in")
    }
}

$summaryPath = Join-Path $Output "summary.json"
$results | ConvertTo-Json -Depth 5 | Set-Content -Path $summaryPath -Encoding utf8 -ErrorAction Stop

$markdownPath = Join-Path $Output "summary.md"
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# Lamprey MAI Validation")
$lines.Add("")
$lines.Add("| Suite | Status | Seconds | Command |")
$lines.Add("|---|---:|---:|---|")
foreach ($result in $results) {
    $lines.Add("| $($result.name) | $($result.status) | $($result.elapsed_seconds) | ``$($result.command)`` |")
}
$lines | Set-Content -Path $markdownPath -Encoding utf8 -ErrorAction Stop

$failed = @($results | Where-Object { $_.status -ne "passed" })
if ($failed.Count -gt 0) {
    Write-Host "Lamprey validation completed with failures. See $Output."
    exit 1
}

Write-Host "Lamprey validation completed successfully. See $Output."
exit 0
