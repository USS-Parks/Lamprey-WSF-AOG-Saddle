# Runbook 03 — Rotate Trust Anchor

## When to use

- Anchor approaching expiry (sites typically rotate ML-DSA-87
  signing keys annually).
- Suspected key compromise upstream of MAI (e.g. Trust Bridge
  signer key replaced).
- Adding a new signer to a multi-anchor fleet.

## Preconditions

- New anchor `.pub` is available, generated off-host, and its
  fingerprint matches the upstream key-management record.
- The next bundle to be installed will be signed by the new
  anchor (or by an anchor that is being kept). **Never** remove
  the only anchor that signs the active bundle.

## Steps (additive rotation — preferred)

1. Copy the new anchor into the trust dir:
   ```bash
   sudo install -o root -g mai -m 0640 \
        new-signer.pub /etc/mai/trust-anchors/
   ```
2. Trigger a re-verification of the cached bundle:
   ```bash
   curl -fsS -H "X-IM-Auth-Token: $MAI_ADMIN_TOKEN" \
        -X POST http://127.0.0.1:8420/v1/system/trust/reverify
   ```
   The endpoint returns `{ "anchors": N, "bundle_verified": true,
   "signer": "<id>" }`. If any anchor fails to load, the call
   returns 400 — do not proceed.
3. Reload the API service to pick up the new anchor in the active
   verifier registry:
   ```bash
   sudo systemctl reload mai-api.service
   ```
4. Confirm via `mai-ship-validate`:
   ```bash
   sudo mai-ship-validate --profile /etc/mai/profile.toml
   ```
   `PROD-TRUST-100` reports the new anchor count.
5. Once a fresh bundle signed by the new anchor has been imported
   and verified (see [04-install-policy-bundle](04-install-policy-bundle.md)),
   delete the retired anchor file from `/etc/mai/trust-anchors/`
   and reload again.

## Steps (emergency rotation — known compromise)

1. Stop the API so no further verifications run against the
   compromised anchor:
   ```bash
   sudo systemctl stop mai-api.service
   ```
2. Replace the anchor file. Do **not** keep the compromised one.
3. Re-import a bundle signed by the new anchor (operator-side; the
   bundle file must arrive over an out-of-band channel — see
   [TRUST-BRIDGE-PRODUCTION.md](../TRUST-BRIDGE-PRODUCTION.md)).
4. `mai-ship-validate` — must pass.
5. `systemctl start mai-api.service`.
6. Export the audit log covering the compromise window.

## Verification

```bash
curl -fsS -H "X-IM-Auth-Token: $MAI_ADMIN_TOKEN" \
     http://127.0.0.1:8420/v1/system/trust/status | jq .
```

Expected: `anchors >= 1`, `bundle_verified = true`,
`signer == <new id>`, and `last_verified` within the last
`bundle.refresh_interval` seconds.

## Do not

- Do not delete the last anchor that signs the active bundle —
  the daemon will fail closed on the next reload.
- Do not transport `.pub` files over the same channel that carried
  the compromised key; rotation has no value if the new key rides
  the same compromised pipe.
- Do not skip the `mai-ship-validate` step. `PROD-TRUST-100` is
  the only gate that proves the rotation is structurally sound.
