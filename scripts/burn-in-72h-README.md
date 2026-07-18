# SHIP-14: 72-Hour Burn-In

`burn-in-72h.sh` / `burn-in-72h.ps1` are the release-gate drivers. They
exercise an installed MAI stack for 72 hours (or `--smoke` ~60s),
emit a structured burn-in report, and ML-DSA-87 sign it via
`burn-in-report-sign.py`.

Required by SHIP-HARDENING-PLAN.md §11 ("72-Hour Burn-In") and listed
in §16 as the final pre-release gate run on the target hardware.

## Quick start

Full 72-hour run:

```bash
scripts/burn-in-72h.sh \
  --profile /etc/mai/profile.toml \
  --output  /var/lib/mai/burn-in/release-72h \
  --signing-key /etc/mai/signing.key \
  --anchor-id   release-officer-2026Q2
```

Smoke (CI sanity, no live service required):

```bash
scripts/burn-in-72h.sh --smoke --output /tmp/burn-in-smoke
```

Windows release officers:

```powershell
scripts\burn-in-72h.ps1 -Profile C:\mai\profile.toml -Output C:\mai\burn-in -SigningKey C:\mai\signing.key -AnchorId release-officer-2026Q2
scripts\burn-in-72h.ps1 -Smoke -Output C:\Temp\burn-in-smoke
```

## Phases

The driver runs ten phases in order. Each phase emits
`<output>/phases/<name>.json` with phase-specific detail.

| #  | Name                  | Smoke   | Plan ref                            |
|----|-----------------------|---------|-------------------------------------|
| 1  | preflight             | run     | §11 "burn-in should start packaged" |
| 2  | service-start         | skip    | §11.1                               |
| 3  | mixed-workload        | skip    | §11.2                               |
| 4  | policy-triggers       | skip    | §11.3 (no payloads logged)          |
| 5  | trust-degradation     | skip    | §11.4                               |
| 6  | adapter-restart       | skip    | §11.5                               |
| 7  | backup-during-load    | skip    | §11.6 (calls SHIP-09 mai-admin)     |
| 8  | restore-side-env      | skip    | §11.7 (calls SHIP-10 mai-admin)     |
| 9  | metrics-capture       | skip    | §11.8 (SHIP-11 will swap to /metrics) |
| 10 | ship-validate         | skip    | §11.9 (SHIP-07-endpoint-and-cli)    |

Smoke mode keeps phase 1 live (the script must always validate its own
arguments and emit a parseable report) and marks every other phase
`skip`. That way CI exercises the report assembly + signing path
without needing a running service.

### Policy-triggers and PII

Phase 4 sends prompts of the form `BURN_IN_CANARY:<kind>` where `<kind>`
is one of `ssn-like`, `credit-card-like`, `phi-like`, `itar-like`. The
canary payloads are server-side fixtures the policy engine knows how
to trip; the burn-in report contains only kind names + response codes,
never the payload text. This satisfies SHIP-HARDENING-PLAN.md §11.3
("include policy-triggering prompts without logging payload content").

## Report schema

`<output>/burn-in-report.json` is the canonical artifact. Schema (v1):

```json
{
  "schema_version": 1,
  "ship_session": "SHIP-14",
  "run_id": "burn-in-20260523T120000Z",
  "mode": "full" | "smoke",
  "duration_seconds": 259200,
  "host": { "hostname": "...", "uname": "..." },
  "totals": { "phase_count": 10, "pass": 10, "fail": 0, "skip": 0 },
  "phases": [
    {
      "name": "preflight",
      "status": "pass" | "fail" | "skip",
      "started_at": "2026-05-23T12:00:00Z",
      "ended_at":   "2026-05-23T12:00:00Z",
      "detail":     { ... phase-specific ... }
    }
  ],
  "signatures": {
    "report_mldsa":   null,    // hex(ML-DSA-87 sig), 9254 hex chars when signed
    "anchor_id":      null,    // operator id string
    "body_sha3_256":  null     // hex(sha3_256(canonical_body)), 64 hex chars
  }
}
```

`phases[*].detail` shape depends on phase. Stable fields:

- `preflight.detail`: `profile_ok`, `binaries_ok`, `notes`, `duration_seconds`, `concurrency`, `sample_interval`
- `service-start.detail`: `already_running`, `api_url`, `pid` (when started by driver)
- `mixed-workload.detail`: `duration_seconds`, `concurrency`, `shape_count`, `hits`, `transport_failures`
- `policy-triggers.detail`: `trigger_kinds`, `responded`, `payloads_logged: false`
- `trust-degradation.detail`: `bundle_cache_dir`, `degraded_response_code`, `recovered_response_code`
- `adapter-restart.detail`: `pid_before`, `pid_after`, `recovered`
- `backup-during-load.detail`: `backup_dir`, `create_exit_code`, `verify_exit_code`
- `restore-side-env.detail`: `target_dir`, `plan_exit_code`, `apply_exit_code`
- `metrics-capture.detail`: `samples_path`, `sample_count`, `interval_seconds`
- `ship-validate.detail`: `exit_code`, `report_path`

`phases[*].detail` for a `skip` is always `{ "skipped": true, "reason": "..." }`.

## Signing model

`burn-in-report-sign.py sign --report <PATH> --signing-key <PATH> --anchor-id <ID>`
canonicalises the report (sorted keys at every level, `signatures` cleared),
SHA3-256s the canonical bytes, ML-DSA-87 signs them, and rewrites the
report in place with the populated `signatures` block. A sidecar
`<report>.sig` carries the hex signature standalone.

The canonical-body contract matches `mai/tools/mai-admin/src/manifest.rs`
SHIP-09 backup manifest contract: same sorted-keys serialisation, same
SHA3-256, same ML-DSA-87. A release officer that can verify SHIP-09
backups can verify SHIP-14 burn-in reports with the same trust anchor.

Verify:

```bash
python scripts/burn-in-report-sign.py verify \
  --report /var/lib/mai/burn-in/release-72h/burn-in-report.json \
  --verifying-key /etc/mai/signing.pub
```

Exit codes (signer):

| code | meaning                                        |
|------|------------------------------------------------|
| 0    | success                                        |
| 1    | signature verification failed (verify only)    |
| 2    | arguments unreadable                           |
| 3    | report unreadable or schema mismatch           |
| 4    | internal error                                 |
| 5    | pqcrypto ML-DSA-87 library missing (sign only) |

When pqcrypto is not installed the signer still emits the canonical body
and writes `<report>.sha3` as a tamper-evidence witness; exit 5 makes
the un-signed state loud.

## Driver exit codes

| code | meaning                                       |
|------|-----------------------------------------------|
| 0    | every phase passed, report (signed) emitted   |
| 1    | one or more phases failed                     |
| 2    | arguments unreadable or output dir broken     |
| 3    | required state path unreadable (profile etc.) |
| 4    | internal driver error (report assembly etc.)  |

CI must run `--smoke` and require exit 0. Release officers must run
the full driver against the candidate hardware and require exit 0
plus a signed report that verifies under the published anchor.

## Anchors

- Plan: `mai/docs/SHIP-HARDENING-PLAN.md` §11 / §16 / §17
- Bash driver: `mai/scripts/burn-in-72h.sh`
- PowerShell driver: `mai/scripts/burn-in-72h.ps1`
- Signer: `mai/scripts/burn-in-report-sign.py`
- Existing short burn-in (`scripts/burn-in.sh`) is the pre-SHIP-14 smoke
  used by `cargo test --workspace`; SHIP-14 layers on top of it.
- SHIP-09 backup tooling exercised by phase 7: `mai/tools/mai-admin/`
- SHIP-10 restore tooling exercised by phase 8: `mai/tools/mai-admin/src/restore.rs`
- SHIP-07-endpoint-and-cli validator invoked by phase 10: `mai-ship-validate`
- SHIP-11 metrics endpoint will replace `metrics-capture` health-proxy once landed.
- Static tests: `mai/tools/burnin_tests/`
