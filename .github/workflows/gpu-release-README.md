# SHIP-13: GPU Release Workflow

This directory's `gpu-release.yml` is the self-hosted GPU release path.
Mainline `ci.yml` runs the GitHub-hosted no-GPU lane on every PR. This
workflow runs the GPU-required acceptance suite only, and only on
release-worthy triggers.

## Triggers

| Trigger              | When                                              |
|----------------------|---------------------------------------------------|
| `push` tag `v*.*.*`  | Cutting a real release (also `v*.*.*-rc*`, etc.)  |
| `workflow_dispatch`  | Manual release-officer dry-run with input knobs   |
| `schedule` Sun 04 UTC| Weekly burn-in; pairs with the SHIP-14 slot       |

## Runner requirements

Labels: `[self-hosted, gpu, mai-release]`

- NVIDIA driver + `nvidia-smi` reachable
- protoc, dpkg-buildpackage, debhelper
- Optional: Ollama listening on `localhost:11434` for the adapter
  integration step (the step warns and continues if absent)

## Jobs (DAG)

```
gpu-build ─┬─> gpu-integration ─┐
           ├─> gpu-benchmarks ──┼─> gpu-package ─> gpu-bundle
           └────────────────────┘
```

- **gpu-build**: `cargo build --workspace --release`, then
  `mai-api validate --json` against `deployment/ship/profile.toml`
  to emit `readiness-report.json`.
- **gpu-integration**: GPU-required Rust integration suites.
- **gpu-benchmarks**: full `mai-adapters --features benchmark` run,
  `bench_compare.py store`, advisory `compare`, and the hard
  `bench_compare.py gate` against `config/gpu-release-thresholds.toml`.
- **gpu-package**: `scripts/build-package.sh --version <resolved>`.
  Skipped via the `skip_package` dispatch input for fast iteration.
- **gpu-bundle**: `scripts/gpu-release-bundle.sh` collects every
  uploaded artifact + writes a signed-shaped `release-manifest.json`
  (`signature: null` until the release officer signs).

## Published artifacts

| Artifact                                | Job              | Retention |
|-----------------------------------------|------------------|-----------|
| `readiness-report-<run>.json`           | gpu-build        | 30 days   |
| `benchmark-results-<run>.tar.gz`        | gpu-benchmarks   | 90 days   |
| `mai-deb-<run>.deb`                     | gpu-package      | 90 days   |
| `release-bundle-<commit>.tar.gz`        | gpu-bundle       | 365 days  |

## Threshold gate

`config/gpu-release-thresholds.toml` is the source of truth. Each
`[[benchmark]]` declares `max_us` (hard ceiling), `min_us`
(informational floor), and `required` (gate fails on absence).

`[policy]` settings:

- `regression_pct`: max % slower than the previous stored run. The
  workflow exposes a `regression_threshold_pct` dispatch input to
  override per-run.
- `allow_zero_target`: when `true`, benchmarks with `max_us=0`
  (informational only) are required to run but do not gate.
- `fail_on_missing`: when `true`, a required benchmark absent from the
  latest run fails the gate.
- `fail_on_unknown`: when `true`, a benchmark in the run but not in
  the thresholds file fails the gate (default `false`).

Gate exit codes:

| Exit | Meaning                                              |
|------|------------------------------------------------------|
| 0    | pass                                                 |
| 1    | regression beyond `regression_pct`                   |
| 2    | per-iter latency exceeded `max_us`                   |
| 3    | required benchmark missing                           |
| 4    | unknown benchmark + `fail_on_unknown`                |
| 5    | thresholds file missing / malformed                  |

## Release bundle manifest schema

```json
{
  "schema_version": 1,
  "ship_session": "SHIP-13",
  "release": {
    "version": "0.1.0",
    "commit": "<full-sha>",
    "short_commit": "<12-char>",
    "build_time_utc": "YYYY-MM-DDTHH:MM:SSZ"
  },
  "totals": { "file_count": N, "total_bytes": N },
  "signature": null,
  "signature_alg": null,
  "artifacts": [
    { "path": "...", "size_bytes": N, "sha256": "<64-hex>" }
  ]
}
```

The release officer fills `signature` + `signature_alg` after running
the bundle through the SHIP-05 AEAD sealer (or an external HSM).
Downstream SHIP-14 burn-in tooling will assert that field is non-null
before promoting the bundle to "shippable."

## Local dry-run

```bash
# Linux / WSL
scripts/gpu-release-bundle.sh \
  --version 0.0.0-dev \
  --commit  $(git rev-parse HEAD) \
  --input   bundle-input/ \
  --output  build/release-bundle/

# Windows
pwsh scripts/gpu-release-bundle.ps1 `
  -Version 0.0.0-dev `
  -Commit  (git rev-parse HEAD) `
  -Input   bundle-input/ `
  -Output  build/release-bundle/
```

## Test coverage

`tools/gpu_release_tests/` — 84 pytest cases (73 cross-platform +
11 POSIX-only execution tests gated by `@posix_only`):

- `test_workflow_yaml.py`: workflow structure, runner labels, action
  pinning, artifact uploads, gate invocation.
- `test_thresholds.py`: thresholds parse, every Rust source benchmark
  has a threshold, no phantom entries, bounds well-formed.
- `test_gate_command.py`: end-to-end exit-code matrix for every gate
  failure mode using synthetic stored runs.
- `test_bundle_scripts.py`: bash assembly + manifest schema + sh/ps1
  parity at the contract layer.
