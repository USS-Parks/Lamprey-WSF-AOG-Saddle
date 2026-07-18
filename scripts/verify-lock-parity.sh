#!/usr/bin/env bash
# Verify that the committed lock files describe the repository's active graphs.

set -euo pipefail

ROOT="${1:-.}"
cd "${ROOT}"

for required in Cargo.toml Cargo.lock; do
    if [[ ! -f "${required}" ]]; then
        echo "error: ${required} not found in ${ROOT}" >&2
        exit 2
    fi
done

command -v cargo >/dev/null 2>&1 || {
    echo "error: cargo is required" >&2
    exit 2
}

# Cargo.lock describes the resolved active graph, not every optional entry in
# [workspace.dependencies]. Cargo's locked metadata command is authoritative
# and refuses to rewrite a stale lock file.
cargo metadata --locked --format-version 1 --no-deps >/dev/null

if [[ -f requirements.txt || -f requirements-lock.txt ]]; then
    if [[ ! -f requirements.txt || ! -f requirements-lock.txt ]]; then
        echo "error: requirements.txt and requirements-lock.txt must be committed together" >&2
        exit 1
    fi

    while IFS= read -r dependency; do
        normalized="$(printf '%s' "${dependency}" | tr '[:upper:]_' '[:lower:]-')"
        if ! grep -qi "^${normalized}==" requirements-lock.txt; then
            echo "MISS-PY: ${dependency} is not pinned in requirements-lock.txt" >&2
            exit 1
        fi
        if ! grep -A1 -i "^${normalized}==" requirements-lock.txt | grep -q -- '--hash='; then
            echo "MISS-HASH: ${dependency} has no locked hash" >&2
            exit 1
        fi
    done < <(
        sed -E '/^[[:space:]]*(#|$)/d; s/[<>=!~].*$//; s/[[:space:]]+$//' requirements.txt | sort -u
    )
fi

echo "OK: active dependency graphs match committed lock files"
