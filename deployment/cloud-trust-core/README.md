# Profile: `cloud-trust-core`

The central Trust Bridge. Signs policy bundles with ML-DSA-87, issues
short-lived Lamprey claims via OpenBao, and publishes revocation
snapshots that downstream `local-mai-node` deployments consume.

## What this profile does

- Wires the production `MlDsaBundleVerifier` against a vault-backed
  anchor registry.
- Marks `publish_bundles = true` so the node exposes the bundle endpoint
  (consumers verify locally; this node never reads regulated payloads).
- Disables the inference path entirely (`disable_inference = true`):
  this is a control-plane node only. Prompts, completions, embeddings,
  and PHI / ITAR / OCAP payloads never reach it (Trust Manifold hard
  rule §A.2.4).

## Verify the profile is live

```bash
curl -H "X-IM-Auth-Token: <ops-key>" https://trust.example.org/v1/trust/status
# Expected: mode = "connected", verifier = "ml-dsa", openbao reachable.
```

## What lives downstream of this node

- `deployment/local-mai-node` — the appliance. Pulls signed bundles
  from this node, verifies them locally, and falls back to degraded /
  air-gapped when this node is unreachable (BF-4 ladder).

## What does NOT live on this node

- Inference adapters (Ollama, vLLM, llama.cpp, …).
- Regulated payloads of any kind.
- The compliance dashboard (`mai/compliance-dashboard/`) — operators
  run that on the MAI node so it can see the local audit chain.
