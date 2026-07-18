# Build or validate the standalone Saddle package staging tree on Windows.

[CmdletBinding()]
param(
    [switch]$ValidateOnly,
    [string]$Staging = "build/package-staging"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot
$StagingPath = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Staging))
$Binaries = @("saddled", "saddle-noded", "saddlectl", "wsf-api", "wsf-seed", "aog-gateway")

if (Test-Path -LiteralPath $StagingPath) {
    Remove-Item -Recurse -Force -LiteralPath $StagingPath
}

$BinDir = Join-Path $StagingPath "usr/bin"
$DocDir = Join-Path $StagingPath "usr/share/doc/saddle"
$ConfigDir = Join-Path $StagingPath "etc/saddle/config"
New-Item -ItemType Directory -Force -Path $BinDir, $DocDir, $ConfigDir | Out-Null

if (-not $ValidateOnly) {
    cargo build --release --locked -p saddled -p saddle-noded -p saddlectl -p wsf-api --bins -p aog-gateway
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

foreach ($Binary in $Binaries) {
    $Destination = Join-Path $BinDir "$Binary.exe"
    if ($ValidateOnly) {
        New-Item -ItemType File -Force -Path $Destination | Out-Null
    } else {
        Copy-Item -LiteralPath (Join-Path $RepoRoot "target/release/$Binary.exe") -Destination $Destination
    }
}

Copy-Item -Recurse -Force -Path (Join-Path $RepoRoot "config/*") -Destination $ConfigDir
Copy-Item -LiteralPath (Join-Path $RepoRoot "deployment/saddle-harness/k3s/saddle.yaml") `
    -Destination (Join-Path $StagingPath "etc/saddle/saddle.yaml")

foreach ($Document in @(
    "README.md",
    "PLANNING/SADDLE-ARCHITECTURE-AND-CONFORMANCE-CONTRACT.md",
    "packaging/README.md"
)) {
    Copy-Item -LiteralPath (Join-Path $RepoRoot $Document) -Destination $DocDir
}

$Version = (Select-String -LiteralPath "Cargo.toml" -Pattern '^version\s*=\s*"([^\"]+)"' | Select-Object -First 1).Matches.Groups[1].Value
$Commit = (git rev-parse --short=12 HEAD).Trim()
$BuildTime = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
@"
name=saddle
version=$Version
git_commit=$Commit
build_time=$BuildTime
validation_only=$($ValidateOnly.IsPresent.ToString().ToLowerInvariant())
"@ | Set-Content -LiteralPath (Join-Path $DocDir "PACKAGE_BUILD_INFO") -Encoding utf8

Write-Host "Saddle staging tree ready at $StagingPath"
