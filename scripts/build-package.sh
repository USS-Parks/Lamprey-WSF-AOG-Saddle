#!/usr/bin/env bash
# Build or validate the standalone Saddle package staging tree.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

STAGING_DIR="${REPO_ROOT}/build/package-staging"
BUILD_DEB=0
VALIDATE_ONLY=0
PACKAGE_VERSION="$(awk '/^\[workspace.package\]/{in_package=1;next} /^\[/{in_package=0} in_package && /^version[[:space:]]*=/{gsub(/.*"|".*/, ""); print; exit}' Cargo.toml)"
GIT_COMMIT="$(git rev-parse --short=12 HEAD 2>/dev/null || printf unknown)"
BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
BINARIES=(saddled saddle-noded saddlectl wsf-api wsf-seed aog-gateway)

log() { printf '[build-package] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit "${2:-1}"; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --deb) BUILD_DEB=1; shift ;;
        --validate-only) VALIDATE_ONLY=1; shift ;;
        --staging)
            [[ $# -ge 2 ]] || die "--staging requires a path"
            STAGING_DIR="$2"
            shift 2
            ;;
        -h|--help)
            sed -n '2,14p' "$0"
            exit 0
            ;;
        *) die "unknown argument: $1" ;;
    esac
done

command -v git >/dev/null 2>&1 || die "missing required tool: git" 3
if [[ "${VALIDATE_ONLY}" -eq 0 ]]; then
    command -v cargo >/dev/null 2>&1 || die "missing required tool: cargo" 3
fi

rm -rf "${STAGING_DIR}"
mkdir -p \
    "${STAGING_DIR}/usr/bin" \
    "${STAGING_DIR}/usr/share/doc/saddle" \
    "${STAGING_DIR}/etc/saddle/config"

if [[ "${VALIDATE_ONLY}" -eq 0 ]]; then
    log "building release binaries"
    cargo build --release --locked \
        -p saddled \
        -p saddle-noded \
        -p saddlectl \
        -p wsf-api --bins \
        -p aog-gateway
fi

for binary in "${BINARIES[@]}"; do
    destination="${STAGING_DIR}/usr/bin/${binary}"
    if [[ "${VALIDATE_ONLY}" -eq 1 ]]; then
        install -m 0755 /dev/null "${destination}"
    else
        install -m 0755 "target/release/${binary}" "${destination}"
    fi
done

cp -R config/. "${STAGING_DIR}/etc/saddle/config/"
install -m 0644 deployment/saddle-harness/k3s/saddle.yaml \
    "${STAGING_DIR}/etc/saddle/saddle.yaml"

for document in \
    README.md \
    PLANNING/SADDLE-ARCHITECTURE-AND-CONFORMANCE-CONTRACT.md \
    packaging/README.md; do
    install -m 0644 "${document}" \
        "${STAGING_DIR}/usr/share/doc/saddle/$(basename "${document}")"
done

cat > "${STAGING_DIR}/usr/share/doc/saddle/PACKAGE_BUILD_INFO" <<EOF
name=saddle
version=${PACKAGE_VERSION}
git_commit=${GIT_COMMIT}
build_time=${BUILD_TIME}
validation_only=$([[ "${VALIDATE_ONLY}" -eq 1 ]] && printf true || printf false)
EOF

if [[ "${BUILD_DEB}" -eq 1 ]]; then
    [[ "${VALIDATE_ONLY}" -eq 0 ]] || die "--deb cannot be combined with --validate-only"
    command -v dpkg-buildpackage >/dev/null 2>&1 || die "missing required tool: dpkg-buildpackage" 3
    rm -rf "${REPO_ROOT}/debian"
    cp -R packaging/debian "${REPO_ROOT}/debian"
    STAGING_DIR="${STAGING_DIR}" dpkg-buildpackage -us -uc -b
fi

log "staging tree ready at ${STAGING_DIR}"
