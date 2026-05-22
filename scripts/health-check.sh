#!/usr/bin/env bash
# Health check for a running MAI server.
#
# Usage:
#   scripts/health-check.sh                       # localhost:8420
#   scripts/health-check.sh https://mai.local     # custom base URL
#   scripts/health-check.sh -- --max-time 2       # extra curl args
#
# Exit codes:
#   0 — all endpoints respond and report a non-degraded status
#   1 — at least one endpoint failed or returned a non-OK body
#   2 — server unreachable

set -euo pipefail

BASE_URL="${1:-http://localhost:8420}"
shift || true
CURL_ARGS=("$@")

ENDPOINTS=(
    "/v1/health"
    "/v1/health/adapters"
    "/v1/health/hardware"
    "/v1/health/system"
)

FAILED=0

for path in "${ENDPOINTS[@]}"; do
    url="${BASE_URL}${path}"
    if ! body="$(curl -fsS "${url}" "${CURL_ARGS[@]}" 2>&1)"; then
        echo "FAIL ${path}: unreachable"
        FAILED=1
        continue
    fi
    if echo "${body}" | grep -qi '"status"[[:space:]]*:[[:space:]]*"degraded"'; then
        echo "WARN ${path}: degraded"
        FAILED=1
        continue
    fi
    echo "OK   ${path}"
done

if [[ "${FAILED}" -ne 0 ]]; then
    exit 1
fi
