# Saddle — Founding Direction

**Product:** Lamprey WSF/AOG Saddle — the client/org-facing agentic harness; the first-party governed seat for WSF + AOG.
**Decided by:** Basho Parks, exploration session 2026-07-11 (run against the Lamprey Harness and Mighty Eel OS working copies).
**Status:** **SUPERSEDED IN PART on 2026-07-16.** This remains an honest record of the 2026-07-11 founding session. Its artifact-only WSF/AOG rule, “Loom parked” decision, and seat-only project boundary are superseded by `SADDLE-INDEPENDENCE-DECISION-2026-07-16.md` and the canonical `SADDLE-WSF-AOG-INDEPENDENT-PROJECT-PSPR.md`. Unchanged decisions—Lamprey Harness separation, protocol-first client behavior, staged identity, seamless cloud/local routing, and independent versioning—remain in force.

---

## 1. The two parents, as they stood on 2026-07-11

**Lamprey Harness** (open source, `USS-Parks/lamprey`, local `C:\Users\17076\Documents\Claude\Lamprey Harness`, v0.16.0): Electron + React 19 single-agent coding harness mirroring Claude Code in the Opus 4.5 era. Five cloud providers (DeepSeek, Google, DashScope, OpenRouter, Zhipu); native + fallback tool calling with descriptor risk metadata and an approval-chip flow; RAG, Deep Research, Snip token filter, Skills/Connectors/Plugins, reasoning-trace viewer, loops (hard-ceilinged, off by default); `events`/`tool_calls` audit tables; change-contract DB schema retained from the deleted proof-harness era. Era-locked, community-facing, **stays untouched by this product**.

**MAI / WSF / AOG** (`USS-Parks/im-mighty-eel-mai`, local `C:\Users\17076\Documents\Claude\Mighty Eel OS\mai`; M1+M2 complete 2026-07-04, remediation pushed through 2026-07-10):

- **WSF — Woven Sovereignty Fabric (trust plane):** eight `fabric-*` crates (contracts, crypto, proof, token, identity, envelope, cache, revocation) plus `wsf-bridge/broker/seal/ledger/api/tenants`. ML-DSA-87-signed **trust tokens** with budget strands (`token_cap`, `usd_cap_cents`, `tool_call_cap`) and biscuit-style attenuation (child caveats ⊆ parent, fails closed on widening); sealed/labeled/threaded envelopes; BLAKE3 receipt chains verifiable off-host with the public key only; OpenBao trust core; AWS/GCP/Azure ephemeral-credential brokering; Ring-3 offline cache (connected → degraded → stale → expired → air-gapped, collapsing to most-restrictive); signed, offline-applicable revocation.
- **AOG — Agentic Orchestration Governance (control plane):** `aog-gateway` (OpenAI **and** Anthropic compatible surfaces; shadow/report/enforce modes; deny-wins HIPAA/ITAR/OCAP policy composer; metering; budget + revocation **kill switch**; egress tokenization) and `aog-toolproxy` + `aog-approvals` (MCP proxy, per-call credential minting, provenance tagging as the agentjacking defense, egress PHI/secret scanning, **mission contracts**, session record/replay, fail-closed guardrails). Loom orchestration crates (`aogd`, `aog-node`, `aog-scheduler`, `aog-estate`, `aog-federation`, …) in-tree from the M3 addendum.
- **Proof posture:** 15/15 live integration gates green against live OpenBao + Moto; HIPAA pack v1 wired end-to-end (PHI → local-only route → receipts → signed §164.312 evidence pack verifying off-host); signed supply chain (cosign + syft SBOM + a no-phone-home static gate).
- Key external docs: the sovereignty P-SPR at `C:\Users\17076\Documents\Claude\Mighty Eel OS\PLANNING\AOG-WSF-SOVEREIGNTY-STACK-PSPR.md`; the build DEVLOG and the canonical threat model (Agentic Security Map) inside the mai repo.

**The reunion fact:** AOG's own plan cites Lamprey Harness patterns — its approval inbox echoes the harness approval chips, its mission contracts echo the harness change contracts, its console inherits the panels aesthetic. AOG's settled doctrine is "govern from outside first, AND ship our own runtime." Saddle is the third thing: **the first-party governed seat** — a real daily-driver harness that proves the control plane end to end. No gateway competitor has one.

---

## 2. Decisions locked (Basho, 2026-07-11)

1. **Topology: protocol-first, both.** The seat always speaks the WSF/AOG client protocol (tokens, gateway, toolproxy, receipts) with Ring-3 offline semantics. Deployment chooses: bundled localhost sidecar (single-seat standalone) or org appliance/server (fleet). One client codebase, two install stories.
2. **Packaging: separate software, its own repo (this one).** Revised the same day from a same-repo-edition recommendation. Complete separation from the OSS harness: own version timeline, own naming convention, possible rename later. The OSS harness stays online and free for its community.
3. **Identity: staged.** v1: admin-issued enrollment token binds the seat to a tenant (fabric-identity mint, PKI leaf on the device); the user claim rides the OS login. v1.5: OIDC/SSO against the client org's IdP mints per-user tokens with role-scoped policy.
4. **Model routes: both, with seamless cloud⇄local flip** (Basho, verbatim: "This needs to flip between cloud and local seamlessly."). No configured posture — per-request policy + connectivity decide.

---

## 3. What the seamless flip implies

- The seat never asks "local or cloud?" It sends to the gateway; classify-and-route decides; the fabric-cache connectivity state machine sets the route ceiling. Air-gap is sticky and deny-wins.
- **The route is a first-class UX fact, not a setting:** a trust pill in the status line shows the live connectivity mode; each assistant turn carries a route chip — LOCAL with the `model_weights_digest` from the receipt, or CLOUD with the provider. Provable, not asserted.
- Mid-session flips are non-disruptive: network drops mid-conversation → pill flips to air-gapped → next turn routes to local inference → receipts continue unbroken → cloud routes resume when connectivity and policy allow.
- Research/web-search egress are tool calls, so under air-gap they are denied cleanly and research degrades to RAG/local corpus. Correct behavior, not a gap.
- **The sales demo:** pull the network cable in front of the client and keep working.

---

## 4. Seam map (harness ⇄ WSF/AOG)

| Harness seam | Becomes | WSF/AOG counterpart |
|---|---|---|
| Provider registry (5 direct providers, keychain keys) | All model traffic exits via one governed route; no standing provider keys on the seat | Gateway virtual keys; OpenAI-compatible surface; budget pre-flight + kill switch |
| Tool dispatch + tool registry | Policy decision before every call, receipt after; fail-closed on unknown tools | Policy composer + destination policy; toolproxy; guardrails |
| Permissions store + approval chips | Same UX, backed by the org approval inbox; approver identity receipted | aog-approvals |
| Tool results entering model context | Tagged untrusted; untrusted content cannot trigger a mutating tool without approval; PHI/secrets redacted pre-context | Provenance tagging + egress scanning (wires into the existing sanitizer/spill seams) |
| Conversation / turn / `multi_agent_run` sub-agents | Session identity → per-turn Task identity → attenuated child tokens for sub-agents (budgets divide) | fabric-identity + fabric-token attenuation |
| Loops (existing hard ceilings) | Ceilings stay; org adds USD/tool-call budget strands; revocation stops a runaway loop at its next call | Budget strand + revocation kill switch |
| SQLite audit + reasoning trace | Local stays the UX cache; authority moves to signed receipts; sessions replay in-app and in the console | wsf-ledger + session record/replay |
| Status line, pills, tool cards | Trust pill, per-turn route chips, policy verdict chips with rule-cited "explain this denial", live budget meter, evidence-pack export | fabric-cache states; policy-studio explanation pattern; evidence packs |

---

## 5. The weave, concretely

- **Model egress:** the direct-provider dispatch path is compiled out; one gateway route replaces it (OpenAI-compatible SSE, so the streaming client barely changes). Model list comes from the gateway's `/v1/models`, which reflects tenant policy. The keychain holds seat identity and virtual-key material — no provider API keys, no API-key entry screen anywhere.
- **Tool calling:** every dispatch gets a pre-flight policy decision (token scope + mission contract + provenance state) and a post-flight receipt. MCP connectors re-register through the toolproxy with per-call minted credentials. Local-execution tools (shell, file edits) get the decision remotely (or from the Ring-3 cache offline), execute locally, and their results are egress-scanned before entering model context.
- **Identity, budgets, autonomy:** conversation → Session token; turn → Task token; sub-agents → attenuated grandchildren with divided budgets. Loops spend from the loop token's budget strand; revoking the token is the org-grade kill switch. The harness's retained change-contract schema becomes the local half of mission contracts.
- **UX controls:** trust pill; per-turn route chips; policy verdict chips with a rule-cited "explain this denial" rendered by the local model even when air-gapped; live budget meter; a Governance right-panel surface (session mission contract, receipt feed, evidence-pack export); reasoning-trace viewer grows receipt links. First run is enrollment-token paste → trust status green.
- **Compiled out in Saddle:** direct provider key UI and dispatch, ungoverned research egress, "always allow" persistence for fallback-parsed mutating tool calls, any settings toggle that could disable governance.

---

## 6. Enforcement doctrine (the honest claim)

In-process enforcement has a boundary: the policy client runs inside the same Electron process as the agent loop. The defensible two-tier doctrine:

1. **Everything that crosses a wire is enforced server-side.** The gateway and toolproxy verify tokens themselves; a hypothetically bypassed client check still has no credentials to spend, because the seat never holds standing creds and per-call credentials are minted by the bridge.
2. **Local execution (shell/file tools) is enforced client-side with tamper-evident receipts.** A bypass is detectable rather than impossible.

Buyer documentation states exactly this — no stronger claim.

---

## 7. Open items for the P-SPR

1. **Codebase bootstrap.** Recommended: one-time snapshot copy of the harness tree at v0.16.0 as Saddle's initial code drop (own history from that point), then weave governance through it. Alternative: fresh scaffold cherry-picking modules. The P-SPR settles this first.
2. **Naming.** "Lamprey" currently names the OSS harness, the WSF build codename (public name Aeneas), and Lamprey MAI. Saddle needs a client-facing name before buyer docs exist.
3. **Seat vs. console split.** Recommended: seat-scoped views in-app (my approvals, my receipts, my contract); estate views stay in the Sovereignty Console.
4. **[SUPERSEDED 2026-07-16] Cross-repo supply chain.** The founding recommendation was to consume version-pinned, cosign-signed service binaries and never import source. The independence decision now requires complete non-secret WSF/AOG/Saddle source ownership in this repository; signed artifacts remain release outputs.
5. **CI.** The no-mock-only rule extends to the seat: a live-stack CI leg that stands up the appliance compose and runs the governed paths against it.
6. **Skills/plugins posture.** Org-allowlisted, signed bundles only. RAG-ingest classification (envelope labels at ingest) parked for v2.
7. **[SUPERSEDED 2026-07-16] Orchestration.** The founding record parked the then-named Loom runtime. Saddle now replaces that name and the Kubernetes-level independent scheduler/orchestrator is Priority 1.
8. **Hooks + CI discipline.** Commit-msg footer, no-slop scan, and the verify gate need Layer-3 owners wired in the first scaffold phase.

---

## 8. Phase sketch (coarse — the P-SPR formalizes)

- **SE-0** Repo scaffold: code drop, hooks/CI, fabric TypeScript client (reuse the mai console's client as the starting point).
- **SE-1** Enrollment, identity, trust status.
- **SE-2** Gateway egress + the seamless route flip UX.
- **SE-3** Tool governance + approvals bridge.
- **SE-4** Budgets, attenuation, loop kill switch.
- **SE-5** Receipts, replay, evidence, UX polish.
- **SE-6** Sidecar bundle + appliance profile + the demo arc + ship v0.1.0.

**Demo arc (the sales artifact):** enrollment → governed turn → cable-pull air-gap flip → agentjacking blocked → budget kill switch → evidence-pack export.
