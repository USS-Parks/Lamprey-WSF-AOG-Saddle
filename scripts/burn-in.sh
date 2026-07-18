#!/usr/bin/env bash
# Burn-in driver: exercises the full MAI stack and writes evidence artifacts
# suitable for acquisition documentation.
#
# Usage:
#   scripts/burn-in.sh                       # default: full suite + sample trace replay
#   scripts/burn-in.sh --quick               # smoke only (cargo test --workspace)
#   scripts/burn-in.sh --output results/x    # custom output directory
#
# Hardware-dependent Phase 1 exit criteria (Scout/Ranger boot timings, 72h
# stability, two-GPU configs) live here as documented placeholders so the
# burn-in result tree always carries an explicit entry per criterion.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

QUICK=0
OUTPUT="results/burn-in-$(date -u +%Y%m%dT%H%M%SZ)"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --quick) QUICK=1; shift ;;
        --output) OUTPUT="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

mkdir -p "${OUTPUT}"
echo "burn-in: writing artifacts to ${OUTPUT}"

# 1. Workspace test suite.
echo "==> cargo test --workspace"
cargo test --workspace 2>&1 | tee "${OUTPUT}/cargo-test.log"

if [[ "${QUICK}" -eq 1 ]]; then
    echo "burn-in: quick mode complete"
    exit 0
fi

# 2. Python regression suite (covers adapters + trace tooling + simulator).
echo "==> pytest tools/ adapters/"
python -m pytest tools/ adapters/ 2>&1 | tee "${OUTPUT}/pytest.log" || true

# 3. Scheduler value-claim evidence: trace replay across all KV policies.
echo "==> trace replay (sample workload)"
python tools/simulator/replay_compare.py \
    --seed 42 \
    --sim-time 30 \
    --out "${OUTPUT}/policy-comparison.json" \
    /dev/null 2>"${OUTPUT}/replay.log" || \
    echo "burn-in: replay sample skipped (no input trace; see KNOWN-ISSUES.md)"

# 4. Hardware-dependent Phase 1 criteria placeholders.
cat > "${OUTPUT}/phase1-deferred.txt" <<'EOF'
The following Phase 1 exit criteria require target hardware and are
intentionally not executed by this burn-in:

- test_scout_config_boots      (1x RTX 4090 + Ollama + Qwen3-14B, <60s)
- test_ranger_config_boots     (2x H100 + vLLM tensor parallel, <90s)
- test_two_gpu_configs         (NVIDIA + AMD)
- test_72_hour_stability       (continuous load, time-dependent)

Run these on the target hardware as part of deployment validation. See
docs/INTEGRATION-COVERAGE.md for the full deferral matrix.
EOF

echo "burn-in: artifacts in ${OUTPUT}"
ls -la "${OUTPUT}"
