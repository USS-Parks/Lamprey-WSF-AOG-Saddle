# Profile: `ship`

Customer-running production posture. This is the only profile that is
sold or installed on a node delivered to a regulated end-user. Use it
on every appliance the operator does not personally re-image between
debugging sessions.

If `MAI_PROFILE=ship` is active, the production guard (added in
SHIP-02) must reject every demo-safe default before the API server is
allowed to listen. SHIP-01 ships parsing only — the typed
representation, schema validation, and `deployment/ship/profile.toml`
landing on disk. Boot wiring, vault wiring, audit WAL, trust bridge,
packaging, and the final `mai-ship-validate` command land in
SHIP-02..SHIP-15.

## What this profile contracts

- `[profile] mode = "production"`, `fail_closed = true`,
  `allow_demo_defaults = false`. Any deviation is a parse-time error.
- Persistent paths for state, config, log, run, and backup directories
  must all be present.
- Vault: real backend (`zfs` is the reference; `file-dev` only with an
  explicit local-dev profile override). `StubVault` is rejected.
- Audit: persistent WAL writer for both API and compliance audit.
  `MemoryAuditWriter` and `NullSealer` are rejected. Hash chain and
  PQC checkpoint signing are required.
- Trust: ML-DSA bundle verifier with a trust-anchor directory present
  on disk and a verifiable bundle on boot. `AcceptAllBundleVerifier`
  and synthetic local-dev token exchange are rejected.
- Auth: non-empty API key store at a configured path. The internal
  profile header bypass is rejected.
- Dashboard: enabled, but `dashboard-dev` and any default admin token
  are rejected.
- Network: loopback bind, reverse-proxy TLS termination is the
  contracted shape. Public binds are guarded.
- Observability: JSON logs, rotation on, Prometheus metrics, alert
  rules wired.

## How to use this profile

```bash
# Bash
MAI_PROFILE=ship cargo run -p mai-api -- --config deployment/ship/profile.toml

# PowerShell
$env:MAI_PROFILE = "ship"; cargo run -p mai-api -- --config deployment/ship/profile.toml
```

The above invocation is the developer-side dry-run path. On a real
installed node the operator points at `/etc/mai/profile.toml` and
`mai-api` runs under systemd (SHIP-08).

## What this profile is NOT

- Not a developer convenience. Use `local-dev` for that.
- Not a demo. Use `airgap-demo` for offline demos and
  `local-mai-node` for connectivity-ladder demos.
- Not a central Trust Bridge host. Use `cloud-trust-core` for that
  role.

## Validation

SHIP-01 ships parse-time validation only. Run the unit and integration
tests:

```bash
cargo test -p mai-api ship_profile
```

A passing test run confirms the schema accepts this file and rejects
the documented unsafe shapes (missing paths, missing trust anchor,
missing audit WAL, `allow_demo_defaults = true`).

The full runtime guard (every check ID, vault wiring, audit
persistence, trust bridge production mode) is added in SHIP-02 and
onward. The `mai-ship-validate` command lands in SHIP-07.

## Where to look next

- `mai/docs/SHIP-PROFILE.md` — comparison of all four MAI profiles and
  what each guarantee means in code.
- `mai/docs/SHIP-HARDENING-PLAN.md` — full execution plan, including
  the workstreams and check-ID conventions referenced above.
- `mai/deployment/README.md` — top-level profile index.
