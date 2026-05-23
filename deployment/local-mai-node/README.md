# Profile: `local-mai-node`

The production MAI appliance. The actual hardware that customers buy.
Runs inference adapters, hosts the compliance dashboard, and follows
the connectivity ladder defined in `docs/LOCAL-TRUST-CACHE.md`.

## Connectivity ladder

| State              | Trigger                                       | Cloud route | Inference |
|--------------------|-----------------------------------------------|-------------|-----------|
| `connected`        | Cache fresh + live link to Trust Bridge       | yes         | yes       |
| `degraded`         | Cache fresh, link down                        | no          | yes       |
| `stale_not_expired`| Cache age > warn_after, < expire_after        | no          | yes (warn)|
| `expired`          | Cache age >= expire_after                     | no          | local-only / emergency |
| `air-gapped`       | Hardware switch on (overrides everything)     | no          | local-only |

## Verify the profile is live

```bash
# Trust cache health
curl -H "X-IM-Auth-Token: <ops-key>" https://localhost:8443/v1/trust/status
# Compliance posture
curl -H "X-IM-Auth-Token: <ops-key>" https://localhost:8443/v1/compliance/status
# Audit chain integrity
curl -H "X-IM-Auth-Token: <ops-key>" https://localhost:8443/v1/compliance/audit/verify
```

`mode` should report `connected` on a healthy appliance with a fresh
bundle. `audit_integrity.last_verify` should be `verified`.

## What lives on this node

- Every Lamprey module — HIPAA, ITAR/EAR, OCAP — under the chosen
  template.
- The S42 tamper-evident audit chain (ML-DSA-signed periodically).
- The S43 report generator + retention pruner.
- The S44 compliance dashboard (Python FastAPI app under
  `mai/compliance-dashboard/`).
- The local trust cache with the production thresholds.

## What does NOT live on this node

- OpenBao (lives on `cloud-trust-core`).
- The signing key for outgoing bundles (vault-resident on the cloud
  node).
- Any control-plane HTTP surface that exposes other tenants' data.
