# Runbook 04 — Install a New Policy Bundle

## When to use

- Lamprey policy update (new module, new rule, threshold change).
- Site enforcement profile change (HIPAA-only -> HIPAA+ITAR, etc.).
- Scheduled bundle refresh after upstream sign-off.

## Preconditions

- Signed bundle file delivered out-of-band, signed by an anchor
  currently installed under `/etc/mai/trust-anchors/`.
- Bundle filename ends in `.bundle.cbor` and ships with a
  `.sig` next to it.
- Operator has read the bundle's change-log and the upstream
  approval is recorded in the operator's own change record.

## Steps

1. Stage the bundle in a temp dir owned by `mai:mai`:
   ```bash
   sudo install -o mai -g mai -m 0640 \
        2026-05-23.bundle.cbor /tmp/staging/
   sudo install -o mai -g mai -m 0640 \
        2026-05-23.bundle.cbor.sig /tmp/staging/
   ```
2. Dry-run import — verifies signature + schema without
   activating:
   ```bash
   sudo -u mai mai-admin policy import \
        --bundle /tmp/staging/2026-05-23.bundle.cbor \
        --signature /tmp/staging/2026-05-23.bundle.cbor.sig \
        --dry-run
   ```
   Output: `verifier_id`, `module_count`, `effective_at`,
   `differs_from_current`.
3. If the dry-run reports clean, activate:
   ```bash
   sudo -u mai mai-admin policy import \
        --bundle /tmp/staging/2026-05-23.bundle.cbor \
        --signature /tmp/staging/2026-05-23.bundle.cbor.sig
   ```
   The daemon refreshes the policy runtime atomically; in-flight
   requests finish under the old bundle, new requests use the
   new bundle.
4. Confirm:
   ```bash
   curl -fsS -H "X-IM-Auth-Token: $MAI_ADMIN_TOKEN" \
        http://127.0.0.1:8420/v1/compliance/policy/status | jq .
   ```
   The `bundle_id` should match the imported `effective_at`.

## Rollback

The previous bundle is kept under
`/var/lib/mai/trust/bundles/<bundle_id>.cbor` with a sidecar
`.sig`. To roll back:

```bash
sudo -u mai mai-admin policy import \
     --bundle /var/lib/mai/trust/bundles/<old>.cbor \
     --signature /var/lib/mai/trust/bundles/<old>.cbor.sig
```

The rollback is itself an import event in the audit chain. Roll
back only against a previously-active bundle; rolling forward to
an arbitrary archive is not supported.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `signature_failed` on dry-run | Bundle not signed by an installed anchor | Verify chain of custody; do **not** install a new anchor just to make this pass |
| `schema_invalid` | Bundle from an unsupported version | Confirm bundle version matches `mai-compliance` policy schema |
| `module_conflict` | Two modules both claim a rule ID | Upstream bundle bug; reject and report |
| API returns 503 after import | Composer rebuild took longer than the readiness probe | Wait 60 s, re-check; if persistent, see [10-adapter-crash-loop](10-adapter-crash-loop.md) |

## Do not

- Do not unpack and re-sign a bundle on the appliance. The
  signing key must live off-host.
- Do not run `policy import` with `--force`. There is no such
  flag; if the dry-run fails, the bundle is rejected.
- Do not delete the previous bundle until the new one has been
  observed working through a full burn-in window.
