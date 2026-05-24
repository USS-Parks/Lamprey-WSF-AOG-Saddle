#!/usr/bin/env bash
# SHIP-13: assemble a signed release bundle from GPU workflow artifacts.
#
# Reads a directory tree of artifact_name/ subdirs (the layout produced
# by actions/download-artifact@v4 with `path: bundle-input/`), computes
# a deterministic SHA-256 over every file, writes a release manifest as
# JSON, and tars the whole tree to release-bundle-<commit>.tar.gz.
#
# This script does NOT sign with a private key here — signing is the job
# of the release officer running it against the SHIP-05 AEAD sealer or
# an external HSM. We emit `signature: null` and `signature_alg: null`
# fields in the manifest; downstream tooling (mai-ship-validate, future
# SHIP-14 burn-in report) fills them in.
#
# Usage:
#   scripts/gpu-release-bundle.sh \
#     --version 0.1.0 \
#     --commit  abc1234deadbeef \
#     --input   bundle-input \
#     --output  build/release-bundle
#
# Exit codes:
#   0  bundle produced
#   1  bad arguments
#   2  input directory missing or empty
#   3  bundle assembly failed (tar/sha256 error)

set -euo pipefail

VERSION=""
COMMIT=""
INPUT_DIR=""
OUTPUT_DIR=""

usage() {
    cat <<'EOF'
Usage: gpu-release-bundle.sh --version V --commit C --input DIR --output DIR

Required:
  --version V    release semver (e.g. 0.1.0)
  --commit  C    git commit (full 40-char SHA, or short)
  --input   DIR  path to artifact tree (one subdir per artifact)
  --output  DIR  destination for manifest + tar.gz
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --version)  VERSION="$2"; shift 2 ;;
        --commit)   COMMIT="$2"; shift 2 ;;
        --input)    INPUT_DIR="$2"; shift 2 ;;
        --output)   OUTPUT_DIR="$2"; shift 2 ;;
        -h|--help)  usage; exit 0 ;;
        *)          echo "unknown arg: $1" >&2; usage >&2; exit 1 ;;
    esac
done

if [[ -z "$VERSION" || -z "$COMMIT" || -z "$INPUT_DIR" || -z "$OUTPUT_DIR" ]]; then
    echo "error: --version --commit --input --output are required" >&2
    usage >&2
    exit 1
fi

if [[ ! -d "$INPUT_DIR" ]]; then
    echo "error: input dir not found: $INPUT_DIR" >&2
    exit 2
fi

if [[ -z "$(ls -A "$INPUT_DIR" 2>/dev/null || true)" ]]; then
    echo "error: input dir is empty: $INPUT_DIR" >&2
    exit 2
fi

mkdir -p "$OUTPUT_DIR"
SHORT_COMMIT="${COMMIT:0:12}"
TAR_PATH="${OUTPUT_DIR}/release-bundle-${SHORT_COMMIT}.tar.gz"
MANIFEST_PATH="${OUTPUT_DIR}/release-manifest.json"
BUILD_TIME="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# Collect every regular file under INPUT_DIR (sorted, deterministic).
TMP_LIST="$(mktemp)"
trap 'rm -f "$TMP_LIST"' EXIT

(cd "$INPUT_DIR" && find . -type f | LC_ALL=C sort) > "$TMP_LIST"

if [[ ! -s "$TMP_LIST" ]]; then
    echo "error: input dir contains no files: $INPUT_DIR" >&2
    exit 2
fi

# Build the artifacts array as JSON. We hand-assemble JSON to avoid
# pulling jq into the runner toolchain.
ARTIFACTS_JSON=""
TOTAL_BYTES=0
FILE_COUNT=0
while IFS= read -r rel; do
    abs="${INPUT_DIR}/${rel#./}"
    size=$(stat -c%s "$abs" 2>/dev/null || stat -f%z "$abs")
    sha=$(sha256sum "$abs" | awk '{print $1}')
    TOTAL_BYTES=$((TOTAL_BYTES + size))
    FILE_COUNT=$((FILE_COUNT + 1))
    entry=$(printf '    {"path": "%s", "size_bytes": %d, "sha256": "%s"}' \
        "${rel#./}" "$size" "$sha")
    if [[ -z "$ARTIFACTS_JSON" ]]; then
        ARTIFACTS_JSON="$entry"
    else
        ARTIFACTS_JSON="${ARTIFACTS_JSON},
${entry}"
    fi
done < "$TMP_LIST"

cat > "$MANIFEST_PATH" <<EOF
{
  "schema_version": 1,
  "ship_session": "SHIP-13",
  "release": {
    "version": "${VERSION}",
    "commit": "${COMMIT}",
    "short_commit": "${SHORT_COMMIT}",
    "build_time_utc": "${BUILD_TIME}"
  },
  "totals": {
    "file_count": ${FILE_COUNT},
    "total_bytes": ${TOTAL_BYTES}
  },
  "signature": null,
  "signature_alg": null,
  "artifacts": [
${ARTIFACTS_JSON}
  ]
}
EOF

# Copy the manifest into the tar so it travels with the bundle.
cp "$MANIFEST_PATH" "${INPUT_DIR}/release-manifest.json"

# Deterministic tar: sort by name, fixed mtime, no owner/group preservation.
tar --sort=name \
    --mtime="${BUILD_TIME}" \
    --owner=0 --group=0 --numeric-owner \
    -czf "$TAR_PATH" \
    -C "$INPUT_DIR" \
    . 2>/dev/null || {
        # Fallback for non-GNU tar (BSD on macOS self-hosted boxes).
        tar -czf "$TAR_PATH" -C "$INPUT_DIR" . || {
            echo "error: tar assembly failed" >&2
            exit 3
        }
    }

BUNDLE_SHA=$(sha256sum "$TAR_PATH" | awk '{print $1}')
BUNDLE_BYTES=$(stat -c%s "$TAR_PATH" 2>/dev/null || stat -f%z "$TAR_PATH")

# Emit a bundle-level checksum file next to the tar.
echo "${BUNDLE_SHA}  $(basename "$TAR_PATH")" > "${TAR_PATH}.sha256"

cat <<EOF
SHIP-13 release bundle assembled
  version       : ${VERSION}
  commit        : ${SHORT_COMMIT}
  artifacts     : ${FILE_COUNT} files (${TOTAL_BYTES} bytes)
  manifest      : ${MANIFEST_PATH}
  bundle        : ${TAR_PATH}
  bundle_bytes  : ${BUNDLE_BYTES}
  bundle_sha256 : ${BUNDLE_SHA}
EOF
