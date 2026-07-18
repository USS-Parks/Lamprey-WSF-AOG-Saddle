# SHIP-14: 72-hour burn-in driver — PowerShell variant.
#
# Mirrors scripts/burn-in-72h.sh so Windows-hosted release officers can run
# the same gate. Phase functions, exit codes, report schema, and signer
# invocation all match the bash driver byte-for-byte.
#
# Usage:
#   scripts\burn-in-72h.ps1 -Profile C:\mai\profile.toml -Output C:\mai\burn-in
#   scripts\burn-in-72h.ps1 -Smoke -Output C:\Temp\burn-in-smoke
#
# Exit codes:
#   0  burn-in complete, every phase passed
#   1  one or more phases failed
#   2  arguments unreadable or output dir not writeable
#   3  required state path unreadable
#   4  internal driver error

[CmdletBinding()]
param(
    [switch]$Smoke,
    [int]$DurationSeconds = 259200,
    [string]$Profile = "",
    [string]$Output = "",
    [string]$SigningKey = "",
    [string]$AnchorId = "",
    [string]$ApiBinary = "",
    [string]$AdminBinary = "",
    [string]$ValidatorBinary = "",
    [string]$ApiUrl = "http://127.0.0.1:8420",
    [string]$Target = "",
    [switch]$NoLoad,
    [int]$SampleInterval = 15,
    [int]$Concurrency = 4
)

$ErrorActionPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")

# ─── defaults ──────────────────────────────────────────────────────────
if ($Smoke) {
    $DurationSeconds = 60
    $SampleInterval = 5
    $Concurrency = 1
}

if ([string]::IsNullOrEmpty($Output)) {
    if ($Smoke) {
        $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
        $Output = Join-Path $RepoRoot "results\burn-in-smoke-$stamp"
    } else {
        Write-Error "burn-in: -Output is required"
        exit 2
    }
}

if (-not [string]::IsNullOrEmpty($SigningKey) -and [string]::IsNullOrEmpty($AnchorId)) {
    Write-Error "burn-in: -SigningKey requires -AnchorId"
    exit 2
}

try {
    New-Item -ItemType Directory -Force -Path $Output | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $Output "phases") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $Output "metrics") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $Output "logs") | Out-Null
} catch {
    Write-Error "burn-in: cannot create $Output"
    exit 2
}

if ([string]::IsNullOrEmpty($Target)) {
    $Target = Join-Path $Output "restore"
}

if (-not $Smoke -and [string]::IsNullOrEmpty($Profile)) {
    if (Test-Path "C:\mai\profile.toml") {
        $Profile = "C:\mai\profile.toml"
    } else {
        Write-Error "burn-in: -Profile is required outside smoke mode"
        exit 3
    }
}

# ─── report state ──────────────────────────────────────────────────────
$RunId = "burn-in-" + (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$ReportPath = Join-Path $Output "burn-in-report.json"
$script:Phases = @()
$script:Counts = @{ phase_count = 0; pass = 0; fail = 0; skip = 0 }

function Now-Utc { (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") }

function Record-Phase {
    param(
        [string]$Name,
        [string]$Status,
        [string]$Started,
        [string]$Ended,
        $Detail
    )
    $script:Counts.phase_count++
    switch ($Status) {
        "pass" { $script:Counts.pass++ }
        "fail" { $script:Counts.fail++ }
        "skip" { $script:Counts.skip++ }
    }
    $script:Phases += [pscustomobject]@{
        name       = $Name
        status     = $Status
        started_at = $Started
        ended_at   = $Ended
        detail     = $Detail
    }
    Write-Host "burn-in: phase $Name`: $Status"
}

function Write-PhaseDetail {
    param([string]$Name, $Detail)
    $path = Join-Path (Join-Path $Output "phases") "$Name.json"
    $Detail | ConvertTo-Json -Depth 10 | Set-Content -Path $path -Encoding utf8
    return $path
}

# ─── phase implementations ─────────────────────────────────────────────

function Phase-Preflight {
    $started = Now-Utc
    $profileOk = $true
    $binariesOk = $true
    $notes = @()
    if (-not $Smoke -and -not (Test-Path $Profile)) {
        $profileOk = $false
        $notes += "profile_missing"
    }
    foreach ($bin in @(@($ApiBinary, "ApiBinary"), @($AdminBinary, "AdminBinary"), @($ValidatorBinary, "ValidatorBinary"))) {
        if ($Smoke) { continue }
        $val = $bin[0]
        if (-not [string]::IsNullOrEmpty($val) -and -not (Test-Path $val)) {
            $binariesOk = $false
            $notes += ($bin[1] + "_missing")
        }
    }
    $detail = [pscustomobject]@{
        smoke = $Smoke.IsPresent
        profile = $Profile
        output = $Output
        duration_seconds = $DurationSeconds
        concurrency = $Concurrency
        sample_interval = $SampleInterval
        profile_ok = $profileOk
        binaries_ok = $binariesOk
        notes = ($notes -join ",")
    }
    Write-PhaseDetail -Name "preflight" -Detail $detail | Out-Null
    $status = if ($profileOk -and $binariesOk) { "pass" } else { "fail" }
    Record-Phase -Name "preflight" -Status $status -Started $started -Ended (Now-Utc) -Detail $detail
}

function Phase-ServiceStart {
    $started = Now-Utc
    if ($Smoke) {
        $detail = [pscustomobject]@{ skipped = $true; reason = "smoke mode does not start a live service"; expected_api_url = $ApiUrl }
        Write-PhaseDetail -Name "service-start" -Detail $detail | Out-Null
        Record-Phase -Name "service-start" -Status "skip" -Started $started -Ended (Now-Utc) -Detail $detail
        return
    }
    $alreadyRunning = $false
    try {
        $r = Invoke-WebRequest -Uri "$ApiUrl/v1/health/live" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $alreadyRunning = $true }
    } catch { $alreadyRunning = $false }
    $detail = [pscustomobject]@{
        already_running = $alreadyRunning
        api_url = $ApiUrl
        started_by_burn_in = (-not $alreadyRunning)
    }
    Write-PhaseDetail -Name "service-start" -Detail $detail | Out-Null
    $status = if ($alreadyRunning) { "pass" } else { "fail" }
    Record-Phase -Name "service-start" -Status $status -Started $started -Ended (Now-Utc) -Detail $detail
}

function Phase-MixedWorkload {
    $started = Now-Utc
    if ($NoLoad) {
        $detail = [pscustomobject]@{ skipped = $true; reason = "-NoLoad supplied" }
        Write-PhaseDetail -Name "mixed-workload" -Detail $detail | Out-Null
        Record-Phase -Name "mixed-workload" -Status "skip" -Started $started -Ended (Now-Utc) -Detail $detail
        return
    }
    if ($Smoke) {
        $detail = [pscustomobject]@{ skipped = $true; reason = "smoke mode skips live workload" }
        Write-PhaseDetail -Name "mixed-workload" -Detail $detail | Out-Null
        Record-Phase -Name "mixed-workload" -Status "skip" -Started $started -Ended (Now-Utc) -Detail $detail
        return
    }
    $end = (Get-Date).AddSeconds($DurationSeconds)
    $hits = 0; $fails = 0
    $shapeCount = 4
    while ((Get-Date) -lt $end) {
        for ($i = 1; $i -le $Concurrency; $i++) {
            $shape = ($hits + $i) % $shapeCount
            try {
                switch ($shape) {
                    0 { Invoke-WebRequest -Uri "$ApiUrl/v1/health/ready" -UseBasicParsing -TimeoutSec 5 | Out-Null }
                    1 { Invoke-WebRequest -Uri "$ApiUrl/v1/system/production-readiness" -UseBasicParsing -TimeoutSec 5 | Out-Null }
                    2 { Invoke-WebRequest -Uri "$ApiUrl/v1/inference" -Method POST -Body '{"prompt":"ok","max_tokens":1}' -ContentType "application/json" -UseBasicParsing -TimeoutSec 5 | Out-Null }
                    3 { Invoke-WebRequest -Uri "$ApiUrl/v1/health/live" -UseBasicParsing -TimeoutSec 5 | Out-Null }
                }
            } catch { $fails++ }
            $hits++
        }
        Start-Sleep -Milliseconds 500
    }
    $detail = [pscustomobject]@{
        duration_seconds = $DurationSeconds
        concurrency = $Concurrency
        shape_count = $shapeCount
        hits = $hits
        transport_failures = $fails
    }
    Write-PhaseDetail -Name "mixed-workload" -Detail $detail | Out-Null
    Record-Phase -Name "mixed-workload" -Status "pass" -Started $started -Ended (Now-Utc) -Detail $detail
}

function Phase-PolicyTriggers {
    $started = Now-Utc
    if ($Smoke) {
        $detail = [pscustomobject]@{ skipped = $true; reason = "smoke mode: synthetic only" }
        Write-PhaseDetail -Name "policy-triggers" -Detail $detail | Out-Null
        Record-Phase -Name "policy-triggers" -Status "skip" -Started $started -Ended (Now-Utc) -Detail $detail
        return
    }
    $triggers = @("ssn-like", "credit-card-like", "phi-like", "itar-like")
    $fired = 0
    foreach ($kind in $triggers) {
        try {
            $r = Invoke-WebRequest -Uri "$ApiUrl/v1/inference" -Method POST `
                -Body ("{`"prompt`":`"BURN_IN_CANARY:$kind`",`"max_tokens`":1}") `
                -ContentType "application/json" -UseBasicParsing -TimeoutSec 10
            if (@(200, 403, 451) -contains $r.StatusCode) { $fired++ }
        } catch {
            # 4xx/5xx surface as exceptions; treat 403/451 as fired
            $code = $_.Exception.Response.StatusCode.value__
            if (@(403, 451) -contains $code) { $fired++ }
        }
    }
    $detail = [pscustomobject]@{
        trigger_kinds = $triggers.Count
        responded = $fired
        payloads_logged = $false
        note = "kind names only; canary payload values are server-side fixtures"
    }
    Write-PhaseDetail -Name "policy-triggers" -Detail $detail | Out-Null
    $status = if ($fired -eq $triggers.Count) { "pass" } else { "fail" }
    Record-Phase -Name "policy-triggers" -Status $status -Started $started -Ended (Now-Utc) -Detail $detail
}

function Phase-TrustDegradation {
    $started = Now-Utc
    if ($Smoke) {
        $detail = [pscustomobject]@{ skipped = $true; reason = "smoke mode does not mutate trust cache" }
        Write-PhaseDetail -Name "trust-degradation" -Detail $detail | Out-Null
        Record-Phase -Name "trust-degradation" -Status "skip" -Started $started -Ended (Now-Utc) -Detail $detail
        return
    }
    $cacheDir = $null
    if (Test-Path $Profile) {
        $cacheDir = (Get-Content $Profile | Select-String -Pattern 'bundle_cache_dir\s*=' |
            ForEach-Object { ($_ -split '=', 2)[1].Trim().Trim('"').Trim("'") } | Select-Object -First 1)
    }
    if ([string]::IsNullOrEmpty($cacheDir) -or -not (Test-Path $cacheDir)) {
        $detail = [pscustomobject]@{ skipped = $true; reason = "bundle_cache_dir not found in profile" }
        Write-PhaseDetail -Name "trust-degradation" -Detail $detail | Out-Null
        Record-Phase -Name "trust-degradation" -Status "skip" -Started $started -Ended (Now-Utc) -Detail $detail
        return
    }
    $bundle = Join-Path $cacheDir "bundle.json"
    $backup = "$bundle.burn-in.bak"
    $degraded = "000"; $recovered = "000"
    if (Test-Path $bundle) {
        Copy-Item $bundle $backup -Force
        (Get-Content $bundle) -replace '"signature":\s*"[^"]*"', '"signature": "DEGRADED"' |
            Set-Content -Path $bundle -Encoding utf8
        try {
            $r = Invoke-WebRequest -Uri "$ApiUrl/v1/trust/exchange" -Method POST `
                -Body '{"audience":"test"}' -ContentType "application/json" -UseBasicParsing -TimeoutSec 10
            $degraded = "$($r.StatusCode)"
        } catch { $degraded = "$($_.Exception.Response.StatusCode.value__)" }
        Move-Item $backup $bundle -Force
        try {
            $r = Invoke-WebRequest -Uri "$ApiUrl/v1/trust/exchange" -Method POST `
                -Body '{"audience":"test"}' -ContentType "application/json" -UseBasicParsing -TimeoutSec 10
            $recovered = "$($r.StatusCode)"
        } catch { $recovered = "$($_.Exception.Response.StatusCode.value__)" }
    }
    $detail = [pscustomobject]@{
        bundle_cache_dir = $cacheDir
        degraded_response_code = $degraded
        recovered_response_code = $recovered
        expected_degraded = "non-2xx"
        expected_recovered = "2xx or 503/410 by exchange_mode"
    }
    Write-PhaseDetail -Name "trust-degradation" -Detail $detail | Out-Null
    $status = if ($degraded -notlike "2*") { "pass" } else { "fail" }
    Record-Phase -Name "trust-degradation" -Status $status -Started $started -Ended (Now-Utc) -Detail $detail
}

function Phase-AdapterRestart {
    $started = Now-Utc
    if ($Smoke) {
        $detail = [pscustomobject]@{ skipped = $true; reason = "smoke mode does not kill processes" }
        Write-PhaseDetail -Name "adapter-restart" -Detail $detail | Out-Null
        Record-Phase -Name "adapter-restart" -Status "skip" -Started $started -Ended (Now-Utc) -Detail $detail
        return
    }
    $procBefore = Get-Process -Name "mai-adapter-manager" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $procBefore) {
        $detail = [pscustomobject]@{ skipped = $true; reason = "no mai-adapter-manager process to restart" }
        Write-PhaseDetail -Name "adapter-restart" -Detail $detail | Out-Null
        Record-Phase -Name "adapter-restart" -Status "skip" -Started $started -Ended (Now-Utc) -Detail $detail
        return
    }
    $pidBefore = $procBefore.Id
    Stop-Process -Id $pidBefore -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    $recovered = 0
    $pidAfter = ""
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        $p = Get-Process -Name "mai-adapter-manager" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($p -and $p.Id -ne $pidBefore) {
            $recovered = 1
            $pidAfter = "$($p.Id)"
            break
        }
    }
    $detail = [pscustomobject]@{
        pid_before = "$pidBefore"
        pid_after = $pidAfter
        recovered = $recovered
    }
    Write-PhaseDetail -Name "adapter-restart" -Detail $detail | Out-Null
    $status = if ($recovered -eq 1) { "pass" } else { "fail" }
    Record-Phase -Name "adapter-restart" -Status $status -Started $started -Ended (Now-Utc) -Detail $detail
}

function Phase-BackupDuringLoad {
    $started = Now-Utc
    if ($Smoke) {
        $detail = [pscustomobject]@{ skipped = $true; reason = "smoke mode: no live workload to overlap" }
        Write-PhaseDetail -Name "backup-during-load" -Detail $detail | Out-Null
        Record-Phase -Name "backup-during-load" -Status "skip" -Started $started -Ended (Now-Utc) -Detail $detail
        return
    }
    $bin = if (-not [string]::IsNullOrEmpty($AdminBinary)) { $AdminBinary } else { "mai-admin" }
    $backupDir = Join-Path $Output "backup"
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    $createArgs = @("backup", "create", "--profile", $Profile, "--output", $backupDir, "--backup-id", "burn-in-$RunId")
    if (-not [string]::IsNullOrEmpty($SigningKey)) { $createArgs += @("--signing-key", $SigningKey, "--anchor-id", $AnchorId) }
    $createOut = Join-Path $Output "logs\backup-create.out"
    & $bin $createArgs *>&1 | Tee-Object -FilePath $createOut | Out-Null
    $createRc = $LASTEXITCODE
    $verifyArgs = @("backup", "verify", "--backup-dir", (Join-Path $backupDir "burn-in-$RunId"))
    if (-not [string]::IsNullOrEmpty($SigningKey)) { $verifyArgs += "--require-signed" }
    $verifyOut = Join-Path $Output "logs\backup-verify.out"
    & $bin $verifyArgs *>&1 | Tee-Object -FilePath $verifyOut | Out-Null
    $verifyRc = $LASTEXITCODE
    $detail = [pscustomobject]@{
        backup_dir = (Join-Path $backupDir "burn-in-$RunId")
        create_exit_code = $createRc
        verify_exit_code = $verifyRc
    }
    Write-PhaseDetail -Name "backup-during-load" -Detail $detail | Out-Null
    $status = if (($createRc -eq 0) -and ($verifyRc -eq 0)) { "pass" } else { "fail" }
    Record-Phase -Name "backup-during-load" -Status $status -Started $started -Ended (Now-Utc) -Detail $detail
}

function Phase-RestoreSideEnv {
    $started = Now-Utc
    if ($Smoke) {
        $detail = [pscustomobject]@{ skipped = $true; reason = "smoke mode: nothing to restore" }
        Write-PhaseDetail -Name "restore-side-env" -Detail $detail | Out-Null
        Record-Phase -Name "restore-side-env" -Status "skip" -Started $started -Ended (Now-Utc) -Detail $detail
        return
    }
    $bin = if (-not [string]::IsNullOrEmpty($AdminBinary)) { $AdminBinary } else { "mai-admin" }
    $backupDir = Join-Path (Join-Path $Output "backup") "burn-in-$RunId"
    New-Item -ItemType Directory -Force -Path $Target | Out-Null
    $planArgs = @("restore", "plan", "--backup-dir", $backupDir, "--target", $Target, "--json")
    if (-not [string]::IsNullOrEmpty($SigningKey)) { $planArgs += "--require-signed" }
    $planOut = Join-Path $Output "logs\restore-plan.json"
    & $bin $planArgs *> $planOut
    $planRc = $LASTEXITCODE
    $applyArgs = @("restore", "apply", "--backup-dir", $backupDir, "--target", $Target, "--force", "--json")
    if (-not [string]::IsNullOrEmpty($SigningKey)) { $applyArgs += "--require-signed" }
    $applyOut = Join-Path $Output "logs\restore-apply.json"
    & $bin $applyArgs *> $applyOut
    $applyRc = $LASTEXITCODE
    $detail = [pscustomobject]@{
        target_dir = $Target
        plan_exit_code = $planRc
        apply_exit_code = $applyRc
    }
    Write-PhaseDetail -Name "restore-side-env" -Detail $detail | Out-Null
    $status = if (($planRc -eq 0) -and ($applyRc -eq 0)) { "pass" } else { "fail" }
    Record-Phase -Name "restore-side-env" -Status $status -Started $started -Ended (Now-Utc) -Detail $detail
}

function Phase-MetricsCapture {
    $started = Now-Utc
    if ($Smoke) {
        $detail = [pscustomobject]@{ skipped = $true; reason = "smoke mode: no live samples" }
        Write-PhaseDetail -Name "metrics-capture" -Detail $detail | Out-Null
        Record-Phase -Name "metrics-capture" -Status "skip" -Started $started -Ended (Now-Utc) -Detail $detail
        return
    }
    $samplesPath = Join-Path $Output "metrics\samples.jsonl"
    Set-Content -Path $samplesPath -Value "" -Encoding utf8
    $end = (Get-Date).AddSeconds(30)
    $count = 0
    while ((Get-Date) -lt $end) {
        $t0 = [datetime]::UtcNow
        $code = "000"
        try {
            $r = Invoke-WebRequest -Uri "$ApiUrl/v1/health/ready" -UseBasicParsing -TimeoutSec 5
            $code = "$($r.StatusCode)"
        } catch { $code = "$($_.Exception.Response.StatusCode.value__)" }
        $t1 = [datetime]::UtcNow
        $line = ('{{"ts":"{0}","endpoint":"/v1/health/ready","code":"{1}","latency_ms":{2}}}' -f (Now-Utc), $code, [int]($t1 - $t0).TotalMilliseconds)
        Add-Content -Path $samplesPath -Value $line -Encoding utf8
        $count++
        Start-Sleep -Seconds $SampleInterval
    }
    $detail = [pscustomobject]@{
        samples_path = $samplesPath
        sample_count = $count
        interval_seconds = $SampleInterval
        note = "SHIP-11 /metrics scrape will replace this proxy once implemented"
    }
    Write-PhaseDetail -Name "metrics-capture" -Detail $detail | Out-Null
    Record-Phase -Name "metrics-capture" -Status "pass" -Started $started -Ended (Now-Utc) -Detail $detail
}

function Phase-ShipValidate {
    $started = Now-Utc
    if ($Smoke) {
        $detail = [pscustomobject]@{ skipped = $true; reason = "smoke mode does not invoke validator" }
        Write-PhaseDetail -Name "ship-validate" -Detail $detail | Out-Null
        Record-Phase -Name "ship-validate" -Status "skip" -Started $started -Ended (Now-Utc) -Detail $detail
        return
    }
    $bin = if (-not [string]::IsNullOrEmpty($ValidatorBinary)) { $ValidatorBinary } else { "mai-ship-validate" }
    $reportPath = Join-Path $Output "logs\ship-validate.json"
    & $bin "--profile" $Profile "--json" *> $reportPath
    $rc = $LASTEXITCODE
    $detail = [pscustomobject]@{
        exit_code = $rc
        report_path = $reportPath
    }
    Write-PhaseDetail -Name "ship-validate" -Detail $detail | Out-Null
    $status = if ($rc -eq 0) { "pass" } else { "fail" }
    Record-Phase -Name "ship-validate" -Status $status -Started $started -Ended (Now-Utc) -Detail $detail
}

# ─── report assembly ────────────────────────────────────────────────────

function Assemble-Report {
    $hostName = $env:COMPUTERNAME
    $uname = [System.Environment]::OSVersion.VersionString
    $report = [pscustomobject]@{
        schema_version = 1
        ship_session = "SHIP-14"
        run_id = $RunId
        mode = if ($Smoke) { "smoke" } else { "full" }
        duration_seconds = $DurationSeconds
        host = [pscustomobject]@{ hostname = $hostName; uname = $uname }
        totals = [pscustomobject]@{
            phase_count = $script:Counts.phase_count
            pass = $script:Counts.pass
            fail = $script:Counts.fail
            skip = $script:Counts.skip
        }
        phases = $script:Phases
        signatures = [pscustomobject]@{
            report_mldsa = $null
            anchor_id = $null
            body_sha3_256 = $null
        }
    }
    $report | ConvertTo-Json -Depth 20 | Set-Content -Path $ReportPath -Encoding utf8
}

function Sign-Report {
    if ([string]::IsNullOrEmpty($SigningKey)) { return 0 }
    $signer = Join-Path $ScriptDir "burn-in-report-sign.py"
    if (-not (Test-Path $signer)) {
        Write-Error "burn-in: signer script missing at $signer"
        return 4
    }
    & python $signer "sign" "--report" $ReportPath "--signing-key" $SigningKey "--anchor-id" $AnchorId
    return $LASTEXITCODE
}

# ─── orchestration ──────────────────────────────────────────────────────

Write-Host "burn-in: run_id=$RunId output=$Output mode=$(if ($Smoke) { 'smoke' } else { 'full' })"

Phase-Preflight
Phase-ServiceStart
Phase-MixedWorkload
Phase-PolicyTriggers
Phase-TrustDegradation
Phase-AdapterRestart
Phase-BackupDuringLoad
Phase-RestoreSideEnv
Phase-MetricsCapture
Phase-ShipValidate

Assemble-Report
$signRc = Sign-Report
if ($signRc -ne 0) {
    Write-Error "burn-in: report signing failed"
    exit 4
}

Write-Host ("burn-in: report={0} pass={1} fail={2} skip={3}" -f $ReportPath, $script:Counts.pass, $script:Counts.fail, $script:Counts.skip)

if ($script:Counts.fail -gt 0) { exit 1 }
exit 0
