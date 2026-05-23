# MAI Profile Modes

This document is the operator-facing reference for the four MAI
deployment profiles. It lives next to the execution plan
([SHIP-HARDENING-PLAN.md](SHIP-HARDENING-PLAN.md)) and the code that
parses the new `ship` profile (`mai-api/src/ship_profile.rs`,
introduced in SHIP-01).

## Profile matrix

| Profile             | Audience            | Trust verifier              | Audit storage      | Vault backend | Demo defaults | Bind     |
|---------------------|---------------------|-----------------------------|--------------------|---------------|---------------|----------|
| `local-dev`         | laptop development  | `AcceptAllBundleVerifier`   | in-memory          | `StubVault`   | allowed       | loopback |
| `airgap-demo`       | offline demos       | `MlDsaBundleVerifier`       | local WAL          | `StubVault`*  | demo-scoped   | loopback |
| `cloud-trust-core`  | central Trust Bridge| `MlDsaBundleVerifier`       | central WAL        | OpenBao       | none          | listed   |
| `local-mai-node`    | integration appliance | `MlDsaBundleVerifier`     | local WAL          | local vault   | none          | listed   |
| `ship`              | regulated customer  | `MlDsaBundleVerifier`       | persistent WAL + PQC | real vault   | rejected      | loopback |

\* `airgap-demo` historically used a stub vault for portability. The
hardening plan does not change `airgap-demo` semantics — it adds a
strictly stricter posture (`ship`) above it.

## `ship` — the only customer-facing profile

`ship` is the profile installed on appliances delivered to customers.
The hardening plan describes the full set of guarantees; the short
version is:

- `[profile] mode = "production"`, `fail_closed = true`,
  `allow_demo_defaults = false`. Parser rejects any deviation.
- Real vault backend (the reference deployment uses ZFS). `StubVault`
  is rejected.
- Persistent WAL for both API audit and compliance audit, with hash
  chain verification, PQC checkpoint signing, and AEAD encryption at
  rest. `MemoryAuditWriter` and `NullSealer` are rejected.
- ML-DSA trust verifier with anchors on disk and a verified bundle on
  boot. `AcceptAllBundleVerifier` and synthetic local-dev token
  exchange are rejected.
- Non-empty API key store and no internal-profile-header bypass.
- Dashboard enabled but `dashboard-dev` and any default admin token
  are rejected.
- Loopback bind with reverse-proxy TLS termination.
- JSON logs + log rotation + Prometheus metrics + alert rules wired.

The full contract — including the runtime check IDs the production
guard will emit — is in
[SHIP-HARDENING-PLAN.md §1.1](SHIP-HARDENING-PLAN.md) and §3.

## SHIP-01 scope

SHIP-01 introduced parsing only:

- `deployment/ship/profile.toml` — canonical profile.
- `deployment/ship/README.md` — operator-facing summary.
- `config/production.example.toml` — annotated operator template.
- `config/ship-validator.toml` — placeholder for the SHIP-07 CLI.
- `mai-api/src/ship_profile.rs` — typed schema, loader,
  parse-time validator.
- `mai-api/tests/ship_profile.rs` — integration test against the
  on-disk profile.

SHIP-01 explicitly does **not**:

- Wire the parsed profile into `ServerConfig` or `MaiServer` startup.
  That work belongs to SHIP-02..SHIP-05.
- Check that the configured paths exist on disk. That's a runtime
  guard responsibility (SHIP-02).
- Ship the `mai-ship-validate` CLI. That lands in SHIP-07.

## Running the parser locally

```bash
# Verify the on-disk file parses + validates.
cargo test -p mai-api ship_profile
```

The test target name is `ship_profile`; both the unit tests in
`mai-api/src/ship_profile.rs` and the integration tests in
`mai-api/tests/ship_profile.rs` run under that filter.

## What changes after SHIP-01

| Session  | Adds to `ship` enforcement                                                |
|----------|----------------------------------------------------------------------------|
| SHIP-02  | Centralised `production_guard.rs` with PROD-* check IDs.                  |
| SHIP-03  | `build_vault` selects a real backend; ship rejects `StubVault` at boot.   |
| SHIP-04  | Persistent API audit writer; ship rejects `MemoryAuditWriter` at boot.    |
| SHIP-05  | Compliance audit sealer; ship replaces `NullSealer` with vault-backed AEAD. |
| SHIP-06  | Trust production mode; ship rejects synthetic exchange + accept-all verifier. |
| SHIP-07  | `/v1/system/production-readiness` endpoint + `mai-ship-validate` CLI.     |
| SHIP-08+ | Packaging, backup/restore, observability, burn-in, docs, final gate.      |

## Related docs

- [SHIP-HARDENING-PLAN.md](SHIP-HARDENING-PLAN.md) — the full execution plan.
- [`mai/deployment/README.md`](../deployment/README.md) — top-level profile index.
- [`mai/deployment/ship/README.md`](../deployment/ship/README.md) — ship profile operator notes.
- `mai/docs/KNOWN-ISSUES.md` — current production-path caveats; SHIP-02..SHIP-16 close these out.
