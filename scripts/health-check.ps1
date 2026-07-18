# Health check for a running MAI server (PowerShell variant).
#
# Usage:
#   scripts\health-check.ps1                       # localhost:8420
#   scripts\health-check.ps1 -BaseUrl http://mai.local
#
# Exit codes:
#   0 — all endpoints respond and report a non-degraded status
#   1 — at least one endpoint failed or returned a non-OK body

[CmdletBinding()]
param(
    [string]$BaseUrl = "http://localhost:8420"
)

$Endpoints = @(
    "/v1/health",
    "/v1/health/adapters",
    "/v1/health/hardware",
    "/v1/health/system"
)

$Failed = $false

foreach ($path in $Endpoints) {
    $url = "$BaseUrl$path"
    try {
        $response = Invoke-WebRequest -Uri $url -Method Get -TimeoutSec 5 -ErrorAction Stop
        if ($response.Content -match '"status"\s*:\s*"degraded"') {
            Write-Host "WARN $path : degraded"
            $Failed = $true
        } else {
            Write-Host "OK   $path"
        }
    } catch {
        Write-Host "FAIL $path : $($_.Exception.Message)"
        $Failed = $true
    }
}

if ($Failed) { exit 1 }
