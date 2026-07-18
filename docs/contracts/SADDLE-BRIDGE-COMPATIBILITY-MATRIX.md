# Saddle Bridge Cross-Plane Compatibility Matrix

**Contract:** `saddle.bridge/v1`
**Owner:** `saddle-bridge`
**Prompt:** SAD-30

This matrix freezes the authority-bearing seams between WSF, Saddle, and AOG.
The bridge is an enforcement adapter, not a new cryptographic or policy engine:
WSF verifies tokens and monotonic revocation, AOG supplies its existing
deny-wins `AggregateDecision`, and `wsf-ledger` remains the receipt authority.

## Frozen contracts

| Contract | Trusted producer | Consumer | Wire construction | Mandatory narrowing / fence |
|---|---|---|---|---|
| `VerifiedSaddleRequest` | `GrantIssuer::verify_request` after `fabric-token::verify_in_context` and `MonotonicRevocationStore::authorize` | Saddle admission | Serialize only; private fields; no `Deserialize` or `Default` | Exact Saddle audience/operation, token/principal tenant and lineage, current bundle, signature, expiry, current monotonic revocation sequence, single-use nonce |
| `AdmissionGrant` | `GrantIssuer::issue_admission` | Saddle mutation choke point | Serialize only; private fields; no `Deserialize` or `Default` | Current revocation at transition; exact verb, object UID/name/tenant, mutation digest, capability subset, TTL no later than verified request, AOG allow with at least one applied module |
| `PlacementGrant` | `GrantIssuer::issue_placement` | Scheduler | Serialize only; private fields; no `Deserialize` or `Default` | Current revocation at transition; exact placement/workload UID and generation, non-empty eligible-node set, resource reservation, trust constraints, TTL no later than admission, AOG allow |
| `RuntimeGrant` | `GrantIssuer::issue_runtime` | Node runtime | Serialize only; private fields; no `Deserialize` or `Default` | Current revocation at transition; exact placement, eligible node, immutable workload digest/runtime class, AOG permission allowlist, budget subset, lineage/tenant continuity, TTL intersection, AOG allow |
| `ActionGrant` | `GrantIssuer::issue_action` | AOG model/tool/control sink | Serialize only; private fields; no `Deserialize` or `Default` | Current revocation at transition; one action and immutable argument/request digests, exact destination, budget subset, atomically consumed lineage-scoped nonce, TTL no later than runtime, AOG allow |
| `ReceiptIntentSpec` | Grant request after metadata validation | `wsf-ledger` adapter | Deserialize is allowed because it is intent, not proof | Non-empty receipt ID and request digest; it never represents an appended ledger receipt |
| `BridgeError` | `saddle-bridge` | API/controller/node adapters | Not a grant | Fail-closed stable variants distinguish replay, tenant/lineage isolation, scope/budget/expiry widening, ineligible node/action, policy deny, and no-module fence |

## Reuse ledger

| Concern | Reused authority | Bridge behavior | Explicit non-ownership |
|---|---|---|---|
| Token signature, issuer key, tenant, bundle, time, caveats | `fabric-token` + `fabric-contracts::TrustToken` | Calls `verify_in_context`; derives a narrowing ceiling from verified fields | No signing, signature parsing, or ad-hoc token format |
| Revocation freshness and rollback resistance | `fabric-revocation::MonotonicRevocationStore` | Requires a current sequenced snapshot and stamps its sequence into every grant | No snapshot verification algorithm or second revocation store |
| Deny-wins policy | `mai-compliance::AggregateDecision` supplied through `AogPolicy` | Denies `allowed == false`; fences the vacuous/no-module case | No HIPAA, ITAR, OCAP, route, or policy composition logic |
| Receipts | `fabric-contracts` receipt schema + `wsf-ledger` append/proof | Carries metadata-only `ReceiptIntentSpec` | No receipt signing, append, chain, or proof implementation |
| Request identity and canonical resource | `VerifiedRequestContext`, `WsfPrincipal`, `CanonicalResource` | Adds the `Saddle` audience and exact cross-plane operations | No request-body identity or public-field construction |
| Replay persistence | `ReplayStore` adapter with `InMemoryReplayStore` only for tests/local use | Atomically consumes request and action nonces in separate namespaces; storage error fences | No second persistence protocol; production adapters use the Saddle durable store |

## Compatibility and property gate

`crates/saddle-bridge/tests/contract_properties.rs` is the executable gate:

1. compile-fail documentation proves wire JSON cannot construct verified
   requests or grants;
2. a full verified-request → admission → placement → runtime → action chain
   preserves tenant, lineage, and monotonic revocation sequence;
3. table-driven properties reject widening on scope, expiry, and every budget
   counter;
4. cross-tenant contexts, replayed request/action nonces, and replay-store
   failures deny;
5. absent, stale, expired, matching, or newly advanced revocation state denies
   at request verification and every grant transition; and
6. any AOG deny wins, while an aggregate with no applied module fences rather
   than treating a vacuous allow as authority.

The wire version is intentionally stable. Adding fields must be backward
compatible; changing an invariant or construction path requires a new contract
version and an explicit migration gate.

## SAD-31 real admission binding

`saddle-apiserver` now consumes the frozen request and admission contracts on
every HTTP mutation. The front door derives the principal only from a verified
WSF token; the handler binds `SaddleAdmission` to the parsed kind, final object
name, and authenticated tenant; and `x-saddle-nonce` is consumed once per token
lineage. A current signed monotonic revocation snapshot, current trust bundle,
unexhausted budget, matching resource-prefix caveat, and deny-wins AOG aggregate
are required before `AdmissionGrant` issuance.

The exact grant is persisted inside the Raft-backed audit outbox before the
desired-state write and retained when the outbox is finalized with its receipt.
`crates/saddle-apiserver/tests/saddle_admission.rs` proves missing and replayed
authority, stale bundle/revocation state, wrong-anchor spoofing, out-of-scope
resources, and cross-tenant mutation all fail closed through the real API.
Node runtime and per-action consumption remain SAD-33 through SAD-35.

## SAD-32 WSF-attested scheduling binding

The real `SchedulerController` now accepts a node snapshot only after verifying
an anchor-signed `saddle.node-attestation/v1` statement over its exact name,
ring, classification floor, platform, measurement, issuance time, and expiry.
Changing any covered field invalidates the signature. Missing, malformed,
attacker-signed, or expired evidence clears the trusted marker before the hard
filter chain evaluates the node.

`SchedulingConstraints` carries minimum CPU, memory, GPU, and slot capacity;
connectivity/air-gap posture; required provider models; and an optional exact
measurement. Readiness now parses and ages the heartbeat inside the scheduling
decision itself. Provider/model state is independently timestamped, resolved
from `ProviderPool` health, and fenced when missing, stale, or unhealthy. Ring,
classification, attestation, connectivity, provider, and capacity plugins all
run as deny-wins filters before scoring, so pressure, failover, stale cache, or
a favorable score cannot resurrect an ineligible node.

`crates/saddle-scheduler/tests/sad32_hard_placement.rs` and the signed node
registration tests are the adversarial gate. SAD-33 replaces the production
system seam and binds a signed child capability into the node start path.

## SAD-33 governed AOG workload binding

`Gateway`, `Toolproxy`, `Approvals`, and `Agent` are first-class managed
workload kinds. The scheduler derives one fixed AOG role per kind and attenuates
the declared, same-tenant `Capability` into a short-lived child bound to the
tenant, workload UID and immutable runtime digest, placement UID, exact node,
budget, caveats, routes/models, and lineage. Missing, terminating, or
cross-tenant roots revoke every placement and child rather than minting a
minimal ambient token.

`NodeRuntime` locally verifies signature, expiry, revocation, tenant, workload,
digest, placement, node, and exact role immediately before the process or
container driver starts. Changed digests stop/restart the ordinal; scale changes
only add/remove ordinals; deleted roots stop every child. A sibling placement's
otherwise-valid token cannot start the assignment.

Production controller writes now require a private `ControllerGrant` with an
exact profile, tenant, TTL, and revocable epoch. The SAD-33 live scheduler uses
a field-constrained Placement profile; release builds do not expose
`admit_system` or the fixture `EstateClient::new` path. Other controllers still
need equally narrow profiles. The typed serialize-only `PlacementGrant` and
`RuntimeGrant` values remain an explicit compatibility gap: the working signed
child capability is not represented as those proof types on the persisted
handoff yet. That binding must close before the SAD-35 live bridge gate; SAD-34
adds the action-grant/receipt layer above it.
