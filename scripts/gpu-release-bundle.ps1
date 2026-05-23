# SHIP-13: assemble a signed release bundle (Windows local-validation port).
#
# Mirrors scripts/gpu-release-bundle.sh exactly: walks an input artifact
# tree, computes SHA-256 per file, writes release-manifest.json, and
# produces a release-bundle-<commit>.tar.gz. Used for local dry-runs on
# Windows dev boxes; the real release path runs the .sh on the
# self-hosted GPU runner.
#
# Usage:
#   pwsh scripts/gpu-release-bundle.ps1 `
#     -Version 0.1.0 `
#     -Commit  abc1234deadbeef `
#     -Input   bundle-input `
#     -Output  build/release-bundle
#
# Exit codes match the bash script:
#   0 ok, 1 bad args, 2 input missing/empty, 3 assembly failed.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Version,
    [Parameter(Mandatory = $true)][string]$Commit,
    [Parameter(Mandatory = $true)][string]$Input,
    [Parameter(Mandatory = $true)][string]$Output
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Input)) {
    Write-Error "input dir not found: $Input"
    exit 2
}

$inputFiles = Get-ChildItem -LiteralPath $Input -Recurse -File -ErrorAction SilentlyContinue
if (-not $inputFiles -or $inputFiles.Count -eq 0) {
    Write-Error "input dir is empty: $Input"
    exit 2
}

New-Item -ItemType Directory -Force -Path $Output | Out-Null

$shortCommit = $Commit.Substring(0, [Math]::Min(12, $Commit.Length))
$tarPath = Join-Path $Output ("release-bundle-{0}.tar.gz" -f $shortCommit)
$manifestPath = Join-Path $Output "release-manifest.json"
$buildTime = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

$inputResolved = (Resolve-Path -LiteralPath $Input).Path
$sortedFiles = $inputFiles | Sort-Object FullName

$artifacts = New-Object System.Collections.ArrayList
$totalBytes = [int64]0
$fileCount = 0
foreach ($file in $sortedFiles) {
    $rel = $file.FullName.Substring($inputResolved.Length).TrimStart('\', '/').Replace('\', '/')
    $size = $file.Length
    $sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLower()
    $entry = [ordered]@{
        path       = $rel
        size_bytes = $size
        sha256     = $sha
    }
    [void]$artifacts.Add($entry)
    $totalBytes += $size
    $fileCount += 1
}

$manifest = [ordered]@{
    schema_version  = 1
    ship_session    = "SHIP-13"
    release         = [ordered]@{
        version        = $Version
        commit         = $Commit
        short_commit   = $shortCommit
        build_time_utc = $buildTime
    }
    totals          = [ordered]@{
        file_count  = $fileCount
        total_bytes = $totalBytes
    }
    signature       = $null
    signature_alg   = $null
    artifacts       = $artifacts
}

$json = $manifest | ConvertTo-Json -Depth 6
Set-Content -LiteralPath $manifestPath -Value $json -Encoding utf8

# Copy the manifest into the input tree so the tar includes it.
Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $Input "release-manifest.json") -Force

# Use system tar (Windows 10+ ships bsdtar at C:\Windows\System32\tar.exe).
$tarExe = Get-Command tar -ErrorAction SilentlyContinue
if (-not $tarExe) {
    Write-Error "tar executable not found in PATH; bundle assembly failed"
    exit 3
}

& tar.exe -czf $tarPath -C $Input .
if ($LASTEXITCODE -ne 0) {
    Write-Error "tar assembly failed with exit $LASTEXITCODE"
    exit 3
}

$bundleHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $tarPath).Hash.ToLower()
$bundleBytes = (Get-Item -LiteralPath $tarPath).Length
Set-Content -LiteralPath "$tarPath.sha256" -Value ("{0}  {1}" -f $bundleHash, (Split-Path -Leaf $tarPath)) -Encoding utf8

Write-Host "SHIP-13 release bundle assembled (Windows port)"
Write-Host ("  version       : {0}" -f $Version)
Write-Host ("  commit        : {0}" -f $shortCommit)
Write-Host ("  artifacts     : {0} files ({1} bytes)" -f $fileCount, $totalBytes)
Write-Host ("  manifest      : {0}" -f $manifestPath)
Write-Host ("  bundle        : {0}" -f $tarPath)
Write-Host ("  bundle_bytes  : {0}" -f $bundleBytes)
Write-Host ("  bundle_sha256 : {0}" -f $bundleHash)
