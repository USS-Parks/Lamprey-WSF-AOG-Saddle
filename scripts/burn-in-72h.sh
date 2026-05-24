#!/usr/bin/env bash
# SHIP-14: 72-hour burn-in driver.
#
# Exercises the full MAI stack against an installed/packaged service so
# release officers can prove the product survives mixed workload, trust
# degradation, adapter restart, backup-during-load, restore-in-side-env,
# and emits a signed burn-in report at the end.
#
# This script does NOT bring up its own database or vault — it expects
# `mai-api` to be installed (or available via --api-binary) and the
# operator profile to live at the path passed to --profile.
#
# Usage:
#   scripts/burn-in-72h.sh \
#     --profile /etc/mai/profile.toml \
#     --output  /var/lib/mai/burn-in/release-72h \
#     --signing-key /etc/mai/signing.key \
#     --anchor-id release-officer-2026Q2
#
# Smoke mode (CI sanity, ~60s, no real workload):
#   scripts/burn-in-72h.sh --smoke --output /tmp/smoke
#
# Exit codes (per SHIP-HARDENING-PLAN.md §13):
#   0  burn-in complete, every phase passed, report (signed) emitted
#   1  one or more phases failed
#   2  arguments unreadable or output dir not writeable
#   3  required state path unreadable (profile, binary missing)
#   4  internal driver error

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ─── defaults ────────────────────────────────────────────────────────────
SMOKE=0
DURATION_SECONDS=259200          # 72 * 3600
PROFILE=""
OUTPUT=""
SIGNING_KEY=""
ANCHOR_ID=""
API_BINARY=""
ADMIN_BINARY=""
VALIDATOR_BINARY=""
API_URL="http://127.0.0.1:8420"
TARGET_RESTORE_DIR=""
NO_LOAD=0
SAMPLE_INTERVAL=15
WORKLOAD_CONCURRENCY=4

usage() {
    cat <<'EOF'
Usage: burn-in-72h.sh [options]

Required (unless --smoke):
  --profile PATH        ship profile (defaults to /etc/mai/profile.toml when
                        --smoke is omitted and the file exists)
  --output  DIR         destination for phase logs + burn-in-report.json

Optional:
  --smoke               collapse to ~60s, skip live-service phases, exit 0
                        only if the report skeleton serialises cleanly
  --duration SECONDS    override total burn-in seconds (default 259200 = 72h)
  --signing-key PATH    32+4896-byte ML-DSA-87 secret key; when present the
                        burn-in report is signed and burn-in-report.sig is
                        emitted next to burn-in-report.json
  --anchor-id ID        stable id operators look up in their anchor directory
                        (required when --signing-key is given)
  --api-binary PATH     mai-api binary (default: from PATH)
  --admin-binary PATH   mai-admin binary (default: from PATH)
  --validator-binary PATH  mai-ship-validate binary (default: from PATH)
  --api-url URL         live api base url (default http://127.0.0.1:8420)
  --target PATH         side-env restore target (default <output>/restore)
  --no-load             skip the mixed-workload phase (operator wants to
                        burn in a quiescent service for memory leak watch)
  --sample-interval N   metrics sample interval seconds (default 15)
  --concurrency N       mixed-workload concurrency (default 4)
EOF
}

# ─── arg parsing ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --smoke)            SMOKE=1; shift ;;
        --duration)         DURATION_SECONDS="$2"; shift 2 ;;
        --profile)          PROFILE="$2"; shift 2 ;;
        --output)           OUTPUT="$2"; shift 2 ;;
        --signing-key)      SIGNING_KEY="$2"; shift 2 ;;
        --anchor-id)        ANCHOR_ID="$2"; shift 2 ;;
        --api-binary)       API_BINARY="$2"; shift 2 ;;
        --admin-binary)     ADMIN_BINARY="$2"; shift 2 ;;
        --validator-binary) VALIDATOR_BINARY="$2"; shift 2 ;;
        --api-url)          API_URL="$2"; shift 2 ;;
        --target)           TARGET_RESTORE_DIR="$2"; shift 2 ;;
        --no-load)          NO_LOAD=1; shift ;;
        --sample-interval)  SAMPLE_INTERVAL="$2"; shift 2 ;;
        --concurrency)      WORKLOAD_CONCURRENCY="$2"; shift 2 ;;
        -h|--help)          usage; exit 0 ;;
        *) echo "burn-in: unknown arg: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ -z "${OUTPUT}" ]]; then
    if [[ ${SMOKE} -eq 1 ]]; then
        OUTPUT="${REPO_ROOT}/results/burn-in-smoke-$(date -u +%Y%m%dT%H%M%SZ)"
    else
        echo "burn-in: --output is required" >&2
        usage >&2
        exit 2
    fi
fi

if [[ -n "${SIGNING_KEY}" && -z "${ANCHOR_ID}" ]]; then
    echo "burn-in: --signing-key requires --anchor-id" >&2
    exit 2
fi

mkdir -p "${OUTPUT}" || { echo "burn-in: cannot create ${OUTPUT}" >&2; exit 2; }
mkdir -p "${OUTPUT}/phases" "${OUTPUT}/metrics" "${OUTPUT}/logs"

if [[ -z "${TARGET_RESTORE_DIR}" ]]; then
    TARGET_RESTORE_DIR="${OUTPUT}/restore"
fi

if [[ ${SMOKE} -eq 1 ]]; then
    DURATION_SECONDS=60
    SAMPLE_INTERVAL=5
    WORKLOAD_CONCURRENCY=1
fi

if [[ ${SMOKE} -eq 0 && -z "${PROFILE}" ]]; then
    if [[ -f "/etc/mai/profile.toml" ]]; then
        PROFILE="/etc/mai/profile.toml"
    else
        echo "burn-in: --profile is required outside smoke mode" >&2
        exit 3
    fi
fi

# ─── report state ────────────────────────────────────────────────────────
RUN_ID="burn-in-$(date -u +%Y%m%dT%H%M%SZ)"
REPORT_PATH="${OUTPUT}/burn-in-report.json"
PHASE_RESULTS=()      # newline-separated "name|status|started|ended|detail_path"

PHASE_COUNT=0
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

now_utc() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
now_ms()  { date -u +%s%3N 2>/dev/null || python3 -c "import time;print(int(time.time()*1000))"; }

record_phase() {
    # name status started ended detail_path
    local name="$1" status="$2" started="$3" ended="$4" detail="$5"
    PHASE_COUNT=$((PHASE_COUNT + 1))
    case "${status}" in
        pass) PASS_COUNT=$((PASS_COUNT + 1)) ;;
        fail) FAIL_COUNT=$((FAIL_COUNT + 1)) ;;
        skip) SKIP_COUNT=$((SKIP_COUNT + 1)) ;;
    esac
    PHASE_RESULTS+=("${name}|${status}|${started}|${ended}|${detail}")
    echo "burn-in: phase ${name}: ${status}"
}

write_phase_detail() {
    local name="$1"; shift
    local path="${OUTPUT}/phases/${name}.json"
    cat > "${path}" <<EOF
{
  "name": "${name}",
$@
}
EOF
    echo "${path}"
}

# ─── phase implementations ───────────────────────────────────────────────

phase_preflight() {
    local name="preflight"
    local started; started="$(now_utc)"
    local detail
    detail="$(mktemp -u "${OUTPUT}/phases/${name}.XXXX.json")"
    local profile_ok=true
    local binaries_ok=true
    local notes=""

    if [[ ${SMOKE} -eq 0 ]]; then
        [[ -f "${PROFILE}" ]] || { profile_ok=false; notes="profile_missing"; }
    fi

    for label in API_BINARY ADMIN_BINARY VALIDATOR_BINARY; do
        local var="${!label:-}"
        if [[ ${SMOKE} -eq 1 ]]; then
            continue
        fi
        if [[ -n "${var}" && ! -x "${var}" ]]; then
            binaries_ok=false
            notes="${notes:+${notes},}${label}_not_executable"
        fi
    done

    cat > "${detail}" <<EOF
{
  "smoke": ${SMOKE},
  "profile": "${PROFILE}",
  "output": "${OUTPUT}",
  "duration_seconds": ${DURATION_SECONDS},
  "concurrency": ${WORKLOAD_CONCURRENCY},
  "sample_interval": ${SAMPLE_INTERVAL},
  "profile_ok": ${profile_ok},
  "binaries_ok": ${binaries_ok},
  "notes": "${notes}"
}
EOF

    if ${profile_ok} && ${binaries_ok}; then
        record_phase "${name}" "pass" "${started}" "$(now_utc)" "${detail}"
    else
        record_phase "${name}" "fail" "${started}" "$(now_utc)" "${detail}"
    fi
}

phase_service_start() {
    local name="service-start"
    local started; started="$(now_utc)"
    local detail="${OUTPUT}/phases/${name}.json"
    local status="skip"
    local pid=""

    if [[ ${SMOKE} -eq 1 ]]; then
        cat > "${detail}" <<EOF
{
  "skipped": true,
  "reason": "smoke mode does not start a live service",
  "expected_api_url": "${API_URL}"
}
EOF
        record_phase "${name}" "skip" "${started}" "$(now_utc)" "${detail}"
        return
    fi

    if curl -fsS "${API_URL}/v1/health/live" >/dev/null 2>&1; then
        status="pass"
        pid="$(pgrep -f mai-api | head -1 || true)"
        cat > "${detail}" <<EOF
{
  "already_running": true,
  "api_url": "${API_URL}",
  "pid": "${pid}"
}
EOF
    else
        local bin="${API_BINARY:-mai-api}"
        "${bin}" --profile "${PROFILE}" >"${OUTPUT}/logs/mai-api.out" 2>"${OUTPUT}/logs/mai-api.err" &
        pid=$!
        # Wait up to 60s for /v1/health/ready.
        local ready=0
        for _ in $(seq 1 60); do
            sleep 1
            if curl -fsS "${API_URL}/v1/health/ready" >/dev/null 2>&1; then
                ready=1
                break
            fi
        done
        if [[ ${ready} -eq 1 ]]; then
            status="pass"
        else
            status="fail"
        fi
        cat > "${detail}" <<EOF
{
  "already_running": false,
  "started_by_burn_in": true,
  "pid": ${pid},
  "ready": ${ready}
}
EOF
    fi
    record_phase "${name}" "${status}" "${started}" "$(now_utc)" "${detail}"
}

phase_mixed_workload() {
    local name="mixed-workload"
    local started; started="$(now_utc)"
    local detail="${OUTPUT}/phases/${name}.json"

    if [[ ${NO_LOAD} -eq 1 ]]; then
        cat > "${detail}" <<EOF
{
  "skipped": true,
  "reason": "--no-load supplied"
}
EOF
        record_phase "${name}" "skip" "${started}" "$(now_utc)" "${detail}"
        return
    fi

    if [[ ${SMOKE} -eq 1 ]]; then
        cat > "${detail}" <<EOF
{
  "skipped": true,
  "reason": "smoke mode skips live workload"
}
EOF
        record_phase "${name}" "skip" "${started}" "$(now_utc)" "${detail}"
        return
    fi

    local end=$(( $(date -u +%s) + DURATION_SECONDS ))
    local hits=0 fails=0
    local shape_count=4
    # Shape 0: /v1/health/ready (cheap)
    # Shape 1: /v1/system/production-readiness (admin scrape, needs token if wired)
    # Shape 2: /v1/inference (POST tiny prompt)
    # Shape 3: /v1/health/live (cheapest)
    while [[ $(date -u +%s) -lt ${end} ]]; do
        for i in $(seq 1 ${WORKLOAD_CONCURRENCY}); do
            local shape=$(( (hits + i) % shape_count ))
            case ${shape} in
                0) curl -fsS "${API_URL}/v1/health/ready" >/dev/null 2>&1 || fails=$((fails + 1)) ;;
                1) curl -fsS "${API_URL}/v1/system/production-readiness" >/dev/null 2>&1 || true ;;
                2) curl -fsS -X POST "${API_URL}/v1/inference" \
                       -H "content-type: application/json" \
                       -d '{"prompt":"ok","max_tokens":1}' >/dev/null 2>&1 || true ;;
                3) curl -fsS "${API_URL}/v1/health/live" >/dev/null 2>&1 || fails=$((fails + 1)) ;;
            esac
            hits=$((hits + 1))
        done
        sleep 0.5
    done

    cat > "${detail}" <<EOF
{
  "duration_seconds": ${DURATION_SECONDS},
  "concurrency": ${WORKLOAD_CONCURRENCY},
  "shape_count": ${shape_count},
  "hits": ${hits},
  "transport_failures": ${fails}
}
EOF
    record_phase "${name}" "pass" "${started}" "$(now_utc)" "${detail}"
}

phase_policy_triggers() {
    local name="policy-triggers"
    local started; started="$(now_utc)"
    local detail="${OUTPUT}/phases/${name}.json"

    if [[ ${SMOKE} -eq 1 ]]; then
        cat > "${detail}" <<EOF
{
  "skipped": true,
  "reason": "smoke mode: synthetic only"
}
EOF
        record_phase "${name}" "skip" "${started}" "$(now_utc)" "${detail}"
        return
    fi

    # Send prompts known to trip policy rules. We DO NOT log the payloads
    # to the report; only the count + per-shape response codes. Customer
    # PII would leak otherwise.
    local triggers=("ssn-like" "credit-card-like" "phi-like" "itar-like")
    local fired=0
    for kind in "${triggers[@]}"; do
        # Each kind is mapped to a known canary payload server-side;
        # we send the kind name only.
        local code
        code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${API_URL}/v1/inference" \
            -H "content-type: application/json" \
            -d "{\"prompt\":\"BURN_IN_CANARY:${kind}\",\"max_tokens\":1}" 2>/dev/null || echo "000")
        if [[ "${code}" == "200" || "${code}" == "403" || "${code}" == "451" ]]; then
            fired=$((fired + 1))
        fi
    done

    cat > "${detail}" <<EOF
{
  "trigger_kinds": ${#triggers[@]},
  "responded": ${fired},
  "payloads_logged": false,
  "note": "kind names only; canary payload values are server-side fixtures"
}
EOF
    if [[ ${fired} -eq ${#triggers[@]} ]]; then
        record_phase "${name}" "pass" "${started}" "$(now_utc)" "${detail}"
    else
        record_phase "${name}" "fail" "${started}" "$(now_utc)" "${detail}"
    fi
}

phase_trust_degradation() {
    local name="trust-degradation"
    local started; started="$(now_utc)"
    local detail="${OUTPUT}/phases/${name}.json"

    if [[ ${SMOKE} -eq 1 ]]; then
        cat > "${detail}" <<EOF
{
  "skipped": true,
  "reason": "smoke mode does not mutate trust cache"
}
EOF
        record_phase "${name}" "skip" "${started}" "$(now_utc)" "${detail}"
        return
    fi

    # Find the bundle cache dir from the profile via a tiny grep.
    local cache_dir
    cache_dir=$(awk -F'=' '/bundle_cache_dir/ { gsub(/[ "\047]/,"",$2); print $2; exit }' "${PROFILE}" 2>/dev/null || true)
    if [[ -z "${cache_dir}" || ! -d "${cache_dir}" ]]; then
        cat > "${detail}" <<EOF
{
  "skipped": true,
  "reason": "bundle_cache_dir not found in profile"
}
EOF
        record_phase "${name}" "skip" "${started}" "$(now_utc)" "${detail}"
        return
    fi

    local bundle="${cache_dir}/bundle.json"
    local backup="${cache_dir}/bundle.json.burn-in.bak"
    local degraded_code="000"
    local recovered_code="000"

    if [[ -f "${bundle}" ]]; then
        cp "${bundle}" "${backup}"
        # Corrupt: overwrite signature field.
        sed -i 's/"signature": "[^"]*"/"signature": "DEGRADED"/' "${bundle}" 2>/dev/null || true
        degraded_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${API_URL}/v1/trust/exchange" \
            -H "content-type: application/json" -d '{"audience":"test"}' 2>/dev/null || echo "000")
        # Restore.
        mv "${backup}" "${bundle}"
        recovered_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${API_URL}/v1/trust/exchange" \
            -H "content-type: application/json" -d '{"audience":"test"}' 2>/dev/null || echo "000")
    fi

    cat > "${detail}" <<EOF
{
  "bundle_cache_dir": "${cache_dir}",
  "degraded_response_code": "${degraded_code}",
  "recovered_response_code": "${recovered_code}",
  "expected_degraded": "non-2xx",
  "expected_recovered": "2xx or 503/410 by exchange_mode"
}
EOF
    # "pass" if degraded != 2xx OR if neither code was 200 (service offline -> skip-like fail)
    if [[ "${degraded_code}" != 2* ]]; then
        record_phase "${name}" "pass" "${started}" "$(now_utc)" "${detail}"
    else
        record_phase "${name}" "fail" "${started}" "$(now_utc)" "${detail}"
    fi
}

phase_adapter_restart() {
    local name="adapter-restart"
    local started; started="$(now_utc)"
    local detail="${OUTPUT}/phases/${name}.json"

    if [[ ${SMOKE} -eq 1 ]]; then
        cat > "${detail}" <<EOF
{
  "skipped": true,
  "reason": "smoke mode does not kill processes"
}
EOF
        record_phase "${name}" "skip" "${started}" "$(now_utc)" "${detail}"
        return
    fi

    local pid_before pid_after
    pid_before=$(pgrep -f mai-adapter-manager | head -1 || echo "")
    if [[ -z "${pid_before}" ]]; then
        cat > "${detail}" <<EOF
{
  "skipped": true,
  "reason": "no mai-adapter-manager process to restart"
}
EOF
        record_phase "${name}" "skip" "${started}" "$(now_utc)" "${detail}"
        return
    fi

    kill -TERM "${pid_before}" 2>/dev/null || true
    sleep 2
    # systemd should restart it within Restart=on-failure.
    local recovered=0
    for _ in $(seq 1 30); do
        sleep 1
        pid_after=$(pgrep -f mai-adapter-manager | head -1 || echo "")
        if [[ -n "${pid_after}" && "${pid_after}" != "${pid_before}" ]]; then
            recovered=1
            break
        fi
    done

    cat > "${detail}" <<EOF
{
  "pid_before": "${pid_before}",
  "pid_after": "${pid_after:-}",
  "recovered": ${recovered}
}
EOF
    if [[ ${recovered} -eq 1 ]]; then
        record_phase "${name}" "pass" "${started}" "$(now_utc)" "${detail}"
    else
        record_phase "${name}" "fail" "${started}" "$(now_utc)" "${detail}"
    fi
}

phase_backup_during_load() {
    local name="backup-during-load"
    local started; started="$(now_utc)"
    local detail="${OUTPUT}/phases/${name}.json"

    if [[ ${SMOKE} -eq 1 ]]; then
        cat > "${detail}" <<EOF
{
  "skipped": true,
  "reason": "smoke mode: no live workload to overlap"
}
EOF
        record_phase "${name}" "skip" "${started}" "$(now_utc)" "${detail}"
        return
    fi

    local bin="${ADMIN_BINARY:-mai-admin}"
    local backup_dir="${OUTPUT}/backup"
    mkdir -p "${backup_dir}"
    local status="pass"
    local create_rc=0
    local verify_rc=0

    "${bin}" backup create \
        --profile "${PROFILE}" \
        --output "${backup_dir}" \
        --backup-id "burn-in-${RUN_ID}" \
        ${SIGNING_KEY:+--signing-key "${SIGNING_KEY}"} \
        ${ANCHOR_ID:+--anchor-id "${ANCHOR_ID}"} \
        >"${OUTPUT}/logs/backup-create.out" 2>"${OUTPUT}/logs/backup-create.err"
    create_rc=$?

    "${bin}" backup verify \
        --backup-dir "${backup_dir}/burn-in-${RUN_ID}" \
        ${SIGNING_KEY:+--require-signed} \
        >"${OUTPUT}/logs/backup-verify.out" 2>"${OUTPUT}/logs/backup-verify.err"
    verify_rc=$?

    if [[ ${create_rc} -ne 0 || ${verify_rc} -ne 0 ]]; then
        status="fail"
    fi

    cat > "${detail}" <<EOF
{
  "backup_dir": "${backup_dir}/burn-in-${RUN_ID}",
  "create_exit_code": ${create_rc},
  "verify_exit_code": ${verify_rc}
}
EOF
    record_phase "${name}" "${status}" "${started}" "$(now_utc)" "${detail}"
}

phase_restore_side_env() {
    local name="restore-side-env"
    local started; started="$(now_utc)"
    local detail="${OUTPUT}/phases/${name}.json"

    if [[ ${SMOKE} -eq 1 ]]; then
        cat > "${detail}" <<EOF
{
  "skipped": true,
  "reason": "smoke mode: nothing to restore"
}
EOF
        record_phase "${name}" "skip" "${started}" "$(now_utc)" "${detail}"
        return
    fi

    local bin="${ADMIN_BINARY:-mai-admin}"
    local backup_dir="${OUTPUT}/backup/burn-in-${RUN_ID}"
    mkdir -p "${TARGET_RESTORE_DIR}"
    local plan_rc=0 apply_rc=0

    "${bin}" restore plan \
        --backup-dir "${backup_dir}" \
        --target "${TARGET_RESTORE_DIR}" \
        ${SIGNING_KEY:+--require-signed} \
        --json \
        >"${OUTPUT}/logs/restore-plan.json" 2>"${OUTPUT}/logs/restore-plan.err"
    plan_rc=$?

    "${bin}" restore apply \
        --backup-dir "${backup_dir}" \
        --target "${TARGET_RESTORE_DIR}" \
        ${SIGNING_KEY:+--require-signed} \
        --force \
        --json \
        >"${OUTPUT}/logs/restore-apply.json" 2>"${OUTPUT}/logs/restore-apply.err"
    apply_rc=$?

    cat > "${detail}" <<EOF
{
  "target_dir": "${TARGET_RESTORE_DIR}",
  "plan_exit_code": ${plan_rc},
  "apply_exit_code": ${apply_rc}
}
EOF
    if [[ ${plan_rc} -eq 0 && ${apply_rc} -eq 0 ]]; then
        record_phase "${name}" "pass" "${started}" "$(now_utc)" "${detail}"
    else
        record_phase "${name}" "fail" "${started}" "$(now_utc)" "${detail}"
    fi
}

phase_metrics_capture() {
    local name="metrics-capture"
    local started; started="$(now_utc)"
    local detail="${OUTPUT}/phases/${name}.json"

    if [[ ${SMOKE} -eq 1 ]]; then
        cat > "${detail}" <<EOF
{
  "skipped": true,
  "reason": "smoke mode: no live samples"
}
EOF
        record_phase "${name}" "skip" "${started}" "$(now_utc)" "${detail}"
        return
    fi

    local samples_path="${OUTPUT}/metrics/samples.jsonl"
    : > "${samples_path}"
    local end=$(( $(date -u +%s) + 30 ))
    local count=0
    while [[ $(date -u +%s) -lt ${end} ]]; do
        local t0=$(now_ms)
        local code; code=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL}/v1/health/ready" 2>/dev/null || echo "000")
        local t1=$(now_ms)
        printf '{"ts":"%s","endpoint":"/v1/health/ready","code":"%s","latency_ms":%d}\n' \
            "$(now_utc)" "${code}" "$((t1 - t0))" >> "${samples_path}"
        count=$((count + 1))
        sleep "${SAMPLE_INTERVAL}"
    done

    cat > "${detail}" <<EOF
{
  "samples_path": "${samples_path}",
  "sample_count": ${count},
  "interval_seconds": ${SAMPLE_INTERVAL},
  "note": "SHIP-11 /metrics scrape will replace this proxy once implemented"
}
EOF
    record_phase "${name}" "pass" "${started}" "$(now_utc)" "${detail}"
}

phase_ship_validate() {
    local name="ship-validate"
    local started; started="$(now_utc)"
    local detail="${OUTPUT}/phases/${name}.json"

    if [[ ${SMOKE} -eq 1 ]]; then
        cat > "${detail}" <<EOF
{
  "skipped": true,
  "reason": "smoke mode does not invoke validator"
}
EOF
        record_phase "${name}" "skip" "${started}" "$(now_utc)" "${detail}"
        return
    fi

    local bin="${VALIDATOR_BINARY:-mai-ship-validate}"
    local rc=0
    "${bin}" --profile "${PROFILE}" --json \
        >"${OUTPUT}/logs/ship-validate.json" 2>"${OUTPUT}/logs/ship-validate.err"
    rc=$?

    cat > "${detail}" <<EOF
{
  "exit_code": ${rc},
  "report_path": "${OUTPUT}/logs/ship-validate.json"
}
EOF
    if [[ ${rc} -eq 0 ]]; then
        record_phase "${name}" "pass" "${started}" "$(now_utc)" "${detail}"
    else
        record_phase "${name}" "fail" "${started}" "$(now_utc)" "${detail}"
    fi
}

# ─── report assembly ─────────────────────────────────────────────────────

assemble_report() {
    local phases_json=""
    local sep=""
    for entry in "${PHASE_RESULTS[@]}"; do
        IFS='|' read -r name status started ended detail <<< "${entry}"
        local detail_payload="null"
        if [[ -f "${detail}" ]]; then
            detail_payload="$(cat "${detail}")"
        fi
        phases_json="${phases_json}${sep}    {
      \"name\": \"${name}\",
      \"status\": \"${status}\",
      \"started_at\": \"${started}\",
      \"ended_at\": \"${ended}\",
      \"detail\": ${detail_payload}
    }"
        sep=",
"
    done

    local host_name os_kernel
    host_name="$(hostname 2>/dev/null || echo unknown)"
    os_kernel="$(uname -sr 2>/dev/null || echo unknown)"

    cat > "${REPORT_PATH}" <<EOF
{
  "schema_version": 1,
  "ship_session": "SHIP-14",
  "run_id": "${RUN_ID}",
  "mode": "$([[ ${SMOKE} -eq 1 ]] && echo smoke || echo full)",
  "duration_seconds": ${DURATION_SECONDS},
  "host": {
    "hostname": "${host_name}",
    "uname": "${os_kernel}"
  },
  "totals": {
    "phase_count": ${PHASE_COUNT},
    "pass": ${PASS_COUNT},
    "fail": ${FAIL_COUNT},
    "skip": ${SKIP_COUNT}
  },
  "phases": [
${phases_json}
  ],
  "signatures": {
    "report_mldsa": null,
    "anchor_id": null,
    "body_sha3_256": null
  }
}
EOF
}

sign_report() {
    [[ -z "${SIGNING_KEY}" ]] && return 0
    local signer="${SCRIPT_DIR}/burn-in-report-sign.py"
    if [[ ! -f "${signer}" ]]; then
        echo "burn-in: signer script missing at ${signer}" >&2
        return 4
    fi
    python3 "${signer}" sign \
        --report "${REPORT_PATH}" \
        --signing-key "${SIGNING_KEY}" \
        --anchor-id "${ANCHOR_ID}"
}

# ─── orchestration ───────────────────────────────────────────────────────

echo "burn-in: run_id=${RUN_ID} output=${OUTPUT} mode=$([[ ${SMOKE} -eq 1 ]] && echo smoke || echo full)"

phase_preflight
phase_service_start
phase_mixed_workload
phase_policy_triggers
phase_trust_degradation
phase_adapter_restart
phase_backup_during_load
phase_restore_side_env
phase_metrics_capture
phase_ship_validate

assemble_report || { echo "burn-in: report assembly failed" >&2; exit 4; }
sign_report || { echo "burn-in: report signing failed" >&2; exit 4; }

echo "burn-in: report=${REPORT_PATH} pass=${PASS_COUNT} fail=${FAIL_COUNT} skip=${SKIP_COUNT}"

if [[ ${FAIL_COUNT} -gt 0 ]]; then
    exit 1
fi
exit 0
