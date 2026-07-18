# Profile: `local-dev`

Single-process development on a laptop. No external Trust Bridge, no
hardware air-gap, no model adapter network reach beyond loopback.

## What this profile does

- Wires `AcceptAllBundleVerifier` so signed bundles do not require key
  material to round-trip.
- Mints synthetic short-lived claims via the local
  `/v1/auth/exchange_token` stub (BF-6 §A.10).
- Boots the policy runtime under the `Standard` template (HIPAA
  baseline only).
- Sets cache thresholds tight (warn = 5 min, expire = 30 min) so the
  freshness ladder is observable in a single afternoon.

## Verify the profile is live

```bash
curl -H "X-IM-Auth-Token: dev-admin-key" http://127.0.0.1:8080/v1/trust/status
curl -H "X-IM-Auth-Token: dev-admin-key" http://127.0.0.1:8080/v1/compliance/status
```

You should see `mode: "connected"` once you mint a claim and a
`Standard`-template module list under `/v1/compliance/status`.

## When NOT to use this profile

- Anything that touches real PHI / ITAR / OCAP data.
- Any benchmark that needs `MlDsaBundleVerifier`-class verification cost.
- Air-gap demos — use `airgap-demo` instead.
