# Profile: `airgap-demo`

The Session 46 demo posture. Fully offline. Air-gap switch is forced
on by policy (not driven by hardware). The trust cache loads a signed
bundle from disk at boot and never reaches out to a Trust Bridge.

## What this profile proves

- **Disconnected operation:** every Lamprey decision succeeds with no
  network. The audit chain links the local credential event id to the
  policy decision to the routing outcome (BF-5).
- **Hard air-gap:** the cloud transport is disabled at the server level
  (`disable_cloud_transport = true`), so even a misconfigured policy
  cannot leak.
- **Local verification:** the production `MlDsaBundleVerifier` runs
  against the pre-loaded bundle, exercising the BF-3 signature path
  without needing the cloud key material.

## Verify the profile is live

```bash
curl -H "X-IM-Auth-Token: <demo-key>" http://127.0.0.1:8443/v1/trust/status
# Expected: mode = "air-gapped", bundle_version = "<demo bundle id>"
curl -H "X-IM-Auth-Token: <demo-key>" http://127.0.0.1:8443/v1/system/airgap
# Expected: is_air_gapped = true, permits_cloud_route = false
```

## How to issue the pre-loaded bundle

Run on the `cloud-trust-core` node:

```bash
mai-trust mint-bundle \
  --tenant demo-tenant \
  --template defense \
  --ttl 7d \
  --output /tmp/airgap-demo.bundle
```

Copy `/tmp/airgap-demo.bundle` to the demo appliance's
`/var/mai/bundles/airgap-demo.bundle`. The path is configurable via
`trust.preloaded_bundle_path` in `profile.toml`.

## Demo scenarios this profile unlocks (BF-7)

1. Authenticate locally → mint claim → run restricted query →
   `local-only` route enforced → audit row links the three.
2. Pull the air-gap switch (already on) → cloud route blocked at three
   layers (cache age, switch policy, server transport).
3. Roll the system clock forward past `expire_after_secs` → cache
   moves to `expired` → emergency-only mode → audit row records the
   transition.
