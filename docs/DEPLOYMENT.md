# MAI Deployment Guide (Session 35)

Operator-facing guide for launching, validating, and running the MAI API
server. For build prerequisites and developer workflows, see
[`BUILD.md`](BUILD.md).

## Quick Start

```bash
# From the repo root
scripts/launch.sh
```

Or on Windows / PowerShell:

```powershell
scripts\launch.ps1
```

That's it. The launcher prefers an existing release binary at
`target/release/mai-api` (or `mai-api.exe`); otherwise it falls back to
`cargo run -p mai-api`. First boot prints a one-time admin API key to
stdout — **save it before the log noise starts.**

```text
========================================
  MAI FIRST-BOOT: Admin API Key
========================================
  Key:  im-<64 hex chars>
  Hash: <64 hex chars>
...
========================================
```

Persist the hash to `config/auth_keys.toml` as documented in
[`SECURITY.md`](SECURITY.md), then restart.

## Configuration

The server reads TOML configs from `config/` and `configs/`:

| File | Purpose | Reference |
|------|---------|-----------|
| `config/auth_keys.toml` | API keys + rate limits | [SECURITY.md](SECURITY.md) |
| `config/kv.toml` | KV cache budget + eviction weights | inline comments |
| `config/scoring.toml` | Multi-factor scorer weights | inline comments |
| `config/metrics.toml` | Telemetry windows + anomaly thresholds | inline comments |
| `config/power.toml` | Power-state timing thresholds | inline comments |
| `config/sentinel.toml` | Sentinel model + promotion guards | inline comments |
| `config/topology.toml` | GPU graph link weights | inline comments |
| `configs/scout.toml` | Single-GPU product tier overlay | tier preset |
| `configs/ranger.toml` | Dual-GPU tier overlay | tier preset |
| `configs/pack-leader.toml` | 8x H100 tier overlay | tier preset |

Tier overlays select between hardware profiles:

```bash
scripts/launch.sh --tier scout
```

The launcher exports `MAI_TIER_CONFIG=<absolute path>`; the server reads
that before loading the base configs.

## Health Verification

After launch, in a second terminal:

```bash
scripts/health-check.sh                       # default localhost:8420
scripts/health-check.sh http://mai.local
```

Output format:

```text
OK   /v1/health
OK   /v1/health/adapters
OK   /v1/health/hardware
OK   /v1/health/system
```

Exit codes: `0` healthy, `1` degraded or failing, `2` unreachable.

## SDK Smoke Test

After launch, verify the deployment is reachable through the SDK boundary:

```bash
MAI_API_KEY=im-... python tools/smoke/smoke_client.py
```

The smoke client probes health, model list, and scheduler metrics using
only the standard library — no SDK install required. This is the Gate C
"SDK runs against packaged deployment" evidence.

## Burn-In

```bash
scripts/burn-in.sh                # full suite: cargo test + pytest + replay
scripts/burn-in.sh --quick        # cargo test only
scripts/burn-in.sh --output results/2026-05-22
```

Outputs land in a timestamped directory under `results/`:

- `cargo-test.log` — full workspace test run
- `pytest.log` — Python regression suite
- `policy-comparison.json` — trace replay across all KV policies (Session 32)
- `phase1-deferred.txt` — explicit list of hardware-dependent criteria
  that this burn-in does not execute

See [`INTEGRATION-COVERAGE.md`](INTEGRATION-COVERAGE.md) for the full
coverage map.

## Operator Lifecycle

| Action | Command |
|--------|---------|
| Start  | `scripts/launch.sh` |
| Stop   | `Ctrl+C` (sends SIGINT; the server drains in-flight requests) |
| Inspect health | `scripts/health-check.sh` |
| Inspect models | `curl -H "X-IM-Auth-Token: $MAI_API_KEY" $URL/v1/models` |
| Power state | `curl -H "X-IM-Auth-Token: $MAI_API_KEY" $URL/v1/power` |
| Audit log | `curl -H "X-IM-Auth-Token: $MAI_API_KEY" $URL/v1/audit/log` |
| Rotate API key | Edit `config/auth_keys.toml`, restart |

## Troubleshooting

### Server prints admin key then crashes

The admin key is printed before the server tries to bind a port. If
binding fails (port already in use, permissions issue), the server exits
after the print. Save the key — it is still valid — then resolve the
bind issue and restart.

### `health-check.sh` returns 1 with `degraded`

One subsystem is degraded but the API is up. Inspect the JSON body for
the offending component. Common causes: no adapter processes registered
(start one), hardware monitoring offline (GPU not visible), or KV cache
near budget (raise `config/kv.toml` or wait for eviction).

### `cargo run` hangs at startup

Usually a port conflict on 8420 (REST) or 50051 (gRPC). Set
`MAI_REST_PORT` / `MAI_GRPC_PORT` to free ports or stop the conflicting
process.

### Smoke client returns 401

The server is in strict auth mode but `MAI_API_KEY` was not set, or the
key in the environment does not match any entry in
`config/auth_keys.toml`. See [SECURITY.md](SECURITY.md) for key
generation and rotation.

### Burn-in `replay.log` says no input trace

The default burn-in runs the policy comparison harness, which requires
an NDJSON trace as input. Capture a trace from a running deployment with
the Session 32 capture module enabled (`TraceConfig.enabled = true`),
then point the replay tool at the resulting file:

```bash
python tools/simulator/replay_compare.py path/to/trace.ndjson \
    --out results/comparison.json
python tools/simulator/report.py results/comparison.json --format markdown
```

## Log Collection

The server emits structured logs via `tracing-subscriber` to stderr.
Capture them with:

```bash
scripts/launch.sh 2>>logs/mai-$(date +%Y%m%d).log
```

JSON-formatted logs (for ingestion) are enabled by setting
`MAI_LOG_FORMAT=json`.

The audit log is separate and lives in the writer configured at startup;
the default `MemoryAuditWriter` is in-process and lost on shutdown.
Production deployments wire a persistent writer.

## What This Guide Does Not Cover

- Production deployment to managed cloud (out of scope; MAI is local-
  first and air-gap-capable by design)
- Backup and disaster recovery for the vault (Session 27 deliverable)
- Multi-host clustering (not on the roster; single-host by design)
- TLS termination (assume a reverse proxy in front of the API server)
