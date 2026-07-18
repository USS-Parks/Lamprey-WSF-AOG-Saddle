#!/usr/bin/env bash
# SCAN-1 (Configuration tighten): lock-file parity verifier.
#
# Asserts that:
#   1. Every direct Rust dependency declared in Cargo.toml has a
#      pinned entry in Cargo.lock.
#   2. Every Python requirement in requirements.txt has a matching
#      pinned entry in requirements-lock.txt with at least one
#      --hash= line.
#
# Exit codes:
#   0 — parity intact
#   1 — drift detected (one or more deps missing from a lock)
#   2 — usage / file-not-found error
#
# Designed to run from the repo root.

set -euo pipefail

ROOT="${1:-.}"
cd "$ROOT"

FAIL=0

# ─── Rust parity ──────────────────────────────────────────────────
if [[ ! -f Cargo.toml ]]; then
    echo "error: Cargo.toml not found in $ROOT" >&2
    exit 2
fi
if [[ ! -f Cargo.lock ]]; then
    echo "error: Cargo.lock not found in $ROOT" >&2
    exit 2
fi

# Crates declared as direct workspace members or dependencies.
# Pull from the [workspace.dependencies] table (most reliable surface
# in this repo) and verify each appears in Cargo.lock.
RUST_DEPS=$(awk '
    /^\[workspace\.dependencies\]/ { in_block = 1; next }
    /^\[/ { in_block = 0 }
    in_block && /^[a-zA-Z0-9_-]+\s*=/ {
        gsub(/[[:space:]]*=.*/, "")
        print
    }
' Cargo.toml | sort -u)

for dep in $RUST_DEPS; do
    if ! grep -q "^name = \"$dep\"" Cargo.lock; then
        echo "MISS-RUST: $dep declared in Cargo.toml but not in Cargo.lock"
        FAIL=1
    fi
done

# ─── Python parity ────────────────────────────────────────────────
if [[ -f requirements.txt && -f requirements-lock.txt ]]; then
    PY_DEPS=$(awk '
        /^[a-zA-Z0-9_.-]+/ {
            split($1, a, /[<>=!~]/)
            print a[1]
        }
    ' requirements.txt | sort -u)

    for dep in $PY_DEPS; do
        # Names normalize: pip lowercases + replaces _ with -.
        norm=$(echo "$dep" | tr '[:upper:]' '[:lower:]' | tr '_' '-')
        if ! grep -qi "^${norm}==" requirements-lock.txt; then
            echo "MISS-PY: $dep declared in requirements.txt but not in requirements-lock.txt"
            FAIL=1
        else
            # Every pinned line must have --hash= for supply-chain integrity.
            if ! grep -A1 -i "^${norm}==" requirements-lock.txt | grep -q -- '--hash='; then
                echo "MISS-HASH: $dep is pinned in requirements-lock.txt but has no --hash= line"
                FAIL=1
            fi
        fi
    done
fi

if [[ $FAIL -eq 0 ]]; then
    echo "OK: lock-file parity verified"
fi
exit $FAIL
