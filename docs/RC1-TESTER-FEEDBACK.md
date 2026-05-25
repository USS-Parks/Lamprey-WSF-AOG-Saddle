# RC1 Tester Feedback

**Project:** Lamprey MAI
**Release:** RC1 v2 (Tester Bundle — source + binaries)
**Freeze commit:** `dceaabc` (SHIP-17 hotfix on `main`)
**Plan reference:** `docs/COGENT-DEPLOYMENT-ROADMAP.md` Session RC-09
**Companion docs:** `README-FIRST.md`, `TESTER-INSTRUCTIONS.md`, `RC1-BUNDLE-NOTES.md`

This document is the audit trail for the RC-09 outside-tester pass.
It records who was sent the bundle, what they ran, what they found,
and how each finding was triaged. It is updated as feedback arrives;
the current §3 status field is the source of truth for whether
RC-09's acceptance criteria have been met.

Per the project's test-evidence-literalism rule
(`feedback_test_evidence_literalism`), nothing in this document is
forward-looking promise — every entry is a record of something that
actually happened on a specific date with a specific tester.

---

## 1. Scope

RC-09's acceptance is "at least one person besides the original
builder has tried RC1." This document captures:

- which testers were invited and which actually ran the bundle
- their environment (per the issue form in `TESTER-INSTRUCTIONS.md` §5)
- each finding, classified by track (A/B/C) and severity
- triage into the four buckets from the roadmap (docs / packaging
  / code / environment)
- the blocker list that gates RC-10 (RC1 Fix Pass)

What this document does **not** capture:

- The author's own runs. RC-05 and RC-06 are the author's pre-flight
  test evidence; RC-09 is specifically the "someone else tried it"
  evidence.
- Speculative issues. Every entry must trace to a real run by a
  real tester.

## 2. Bundle Artefacts Available For Distribution

Re-assembled 2026-05-24 after the RC-10 RC1.1-docs patch pass
(commit `b0fcdee`). Binary freeze unchanged at `dceaabc`; binary
hashes unchanged from RC-03; only the source/docs/ tree differs
from the RC-08 assembly. **Use the hashes below when sending to a
tester — the original RC-08 hashes are stale.**

**Authoritative source for archive hashes:** the `SHA256SUMS` file
at the release directory (`Island-Mountain-RC1-release/SHA256SUMS`,
177 bytes). The hashes inline in the table below are a snapshot at
the time of this commit; if the bundle is re-rolled,
`SHA256SUMS` wins. (Embedding hashes inside the bundle hits a
classic self-reference: each rebuild changes a file inside, which
changes the archive hash, which would need a new commit, which
would change the file again. The external SHA256SUMS is the
fixed point.)

| Artefact | Size | SHA-256 (snapshot) |
|---|---|---|
| `Lamprey-MAI-RC1/` (uncompressed folder, 670 file entries) | 19 MB | per `Lamprey-MAI-RC1/CHECKSUMS.txt` (internal) |
| `Lamprey-MAI-RC1.3.tar.gz` | 5.7 MB | `35ada78f66f57901c1c3a438709712cbf0e8f43f60e5b8383eb2343c4a66c76a` |
| `Lamprey-MAI-RC1.3.zip` | 6.1 MB | `6200c1ccfcd25132e417c03f465eef474ccf35cbd9a8e063256f0089d3ccee84` |
| `SHA256SUMS` | 177 B | (covers the two archives above) |

Bundle and archives live at `C:/Users/17076/Documents/Claude/Island-Mountain-RC1-release/`
on the build host. Both archives carry the same 671 file entries
(670 in CHECKSUMS.txt + CHECKSUMS.txt itself); the zip also
includes a small number of explicit empty-directory markers, which
is the normal POSIX-tar vs PKZip metadata difference, not a content
difference.

Pick **tar.gz** for Unix recipients, **zip** for Windows recipients
who do not have a tar implementation.

**Self-reference note for testers reading this inside the bundle:**
If you opened this doc *inside* the archive you just downloaded,
the snapshot hashes in the table above were the latest as of the
commit that built your archive. The archive you actually downloaded
may carry slightly different file hashes inside (this doc was the
*last* thing updated before the archive was rolled). To verify
your download integrity, compare your `sha256sum` against the
external `SHA256SUMS` file your sender provided alongside the
archive — that file is the contract.

**Delta from the RC-08 assembly:** 3 new docs added to
`source/docs/` (RC1-CHANGES.md, RC1-SELF-REVIEW-TRACK-C.md,
RC1-TESTER-FEEDBACK.md) and 13 docs updated (README-FIRST.md
mirrored at top level and inside source/docs/,
TESTER-INSTRUCTIONS.md, RC1-PACKAGE-MANIFEST.md, the four
acquisition demos, runbooks/README.md, and five individual
runbooks). See `source/docs/RC1-CHANGES.md` for the per-file
finding-by-finding patch matrix.

## 3. Current Status

| Field | Value |
|---|---|
| Track planned for first tester | **C** (security/compliance review) — selected 2026-05-23 |
| Transfer mechanism | User sent the repo to the tester out-of-band overnight |
| Testers invited | **1** (John Dougherty, johndou.com, Colorado) |
| Testers responded | **1** (John, 2026-05-24, email + GitDoctor scan) |
| Self-reviews completed | **1** (Claude self-review 2026-05-24, see §6.1 — does NOT count toward acceptance) |
| Findings filed (self-review) | **12** (5 H / 4 M / 3 L — see §7); 9 of 12 already resolved in RC-10 RC1.1-docs (commits `b0fcdee` + `a6fa65e`) |
| Findings filed (outside tester) | **20+** from John's email + GitDoctor scan; full triage matrix in [`dougherty/JOHN-REMEDIATION-PLAN.md`](dougherty/JOHN-REMEDIATION-PLAN.md) §2; summarised in §7 below with `J-` IDs |
| Active remediation lane | **DOUGHERTY (J-01..J-26)** — 26 sessions across 10 workstreams; plan + roster at [`dougherty/`](dougherty/) |
| **RC-09 acceptance met** | **YES** — John is the outside tester; feedback captured below; blockers known and routed to the DOUGHERTY lane |

This field block is the source of truth. Update it whenever a
tester is invited, responds, or files a finding.

## 4. Tester Roster

| # | Tester | Role / why invited | Track | Bundle variant | Invited (date) | Responded (date) | Status |
|---|---|---|---|---|---|---|---|
| 1 | John Dougherty (johndou.com, CO) | Independent technical tester sourced by Basho; ran GitDoctor (gitdoctor.io) AI scan against the GitHub mirror `USS-Parks/im-mighty-eel-mai` + a manual read | Hybrid — closest to Track B/C but tool-driven (GitDoctor) rather than the README-FIRST + cargo-test walk | RC1.1-docs (sent from the repo, not the assembled archive) | 2026-05-23 (overnight) | 2026-05-24 (email + 15 scan screenshots) | **responded — awaiting tester re-test** — see §6.2; DOUGHERTY lane closed 2026-05-24; response doc at [`RC1-TESTER-RESPONSE-DOUGHERTY.md`](RC1-TESTER-RESPONSE-DOUGHERTY.md) |

Add one row per invitation. Status values: `invited` → `running` →
`reported` → `triaged`. If a tester declines or never responds,
record that — non-responses are data too.

## 5. Invitation Template

Send one of the two messages below per invitation. Customise the
**bracketed** fields, leave everything else verbatim. The hash line
is what protects the recipient from a tampered archive.

### 5.A Short version (Slack / DM / text)

```
Hi [Name] — would you be up for spending [~30 min / ~90 min /
~3 hr] testing the Lamprey MAI RC1 tester bundle
next week?

It's a self-contained release-candidate for our local-AI-with-
compliance-governance stack, frozen at commit dceaabc. The
[smoke / build+test / security] track is what I'd ask of you.

I'll send you [Lamprey-MAI-RC1.3.zip / .tar.gz] (~6 MB). After
download, verify SHA-256:

  [35ada78f66f57901c1c3a438709712cbf0e8f43f60e5b8383eb2343c4a66c76a for .tar.gz]
  [6200c1ccfcd25132e417c03f465eef474ccf35cbd9a8e063256f0089d3ccee84 for .zip]

Then unpack and open README-FIRST.md. Total reading is ~10 min;
TESTER-INSTRUCTIONS.md tells you which sections of README-FIRST
to actually execute given your track.

The bundle is not safe for real regulated data — please use a
test machine. Reply via the issue form in TESTER-INSTRUCTIONS.md
§5 (one issue per problem, even if the answer is "everything
passed").

Thanks — RC-09 of our release plan literally requires "at least
one person besides the original builder has tried it," so your
30 minutes unblocks the whole release.
```

### 5.B Long version (email)

```
Subject: RC1 tester ask — Lamprey MAI, ~[30 min / 90 min / 3 hr]

Hi [Name],

I'm at Session RC-09 of the release plan for our local AI +
compliance stack (Lamprey MAI), and the
acceptance criterion for this session is literally "at least one
person besides the original builder has tried RC1." I'd like that
person to be you, if you have the time.

WHAT IT IS

A 19 MB self-contained tester bundle frozen at commit dceaabc.
"MAI" runs local AI inference; "Lamprey" decides what that
inference is allowed to do under HIPAA, ITAR/EAR, and OCAP
(tribal data sovereignty) rules and signs an audit chain. The
bundle ships source plus prebuilt Windows binaries.

WHAT I'M ASKING

Track [A / B / C] of TESTER-INSTRUCTIONS.md. That's about
[30 minutes / 90 minutes / 3-4 hours] of your time.

- Track A is just "does the daemon boot and respond to /v1/health"
  on any laptop with no GPU.
- Track B is "does cargo test --workspace come back green on
  your machine" — needs 4-core x86_64, 8 GB RAM, 60 GB free disk.
- Track C is a security/compliance read of the policy and audit
  layers; needs the same hardware as B plus Rust literacy.

If you only have time for one, Track A is the most valuable —
the whole release lane is gated on "did it work for someone other
than me."

HOW TO RECEIVE THE BUNDLE

I'll send you [Lamprey-MAI-RC1.3.zip / Lamprey-MAI-RC1.3.tar.gz] via
[mechanism]. After download, please verify the SHA-256:

  .tar.gz: 35ada78f66f57901c1c3a438709712cbf0e8f43f60e5b8383eb2343c4a66c76a
  .zip:    6200c1ccfcd25132e417c03f465eef474ccf35cbd9a8e063256f0089d3ccee84

If the hash does not match, do not unpack — message me and I'll
re-send.

WHAT TO READ FIRST

After unpacking, README-FIRST.md is the canonical first-run guide
(307 lines, ~10 minutes to read). TESTER-INSTRUCTIONS.md tells you
which sections to execute given your track.

CONSTRAINTS

- Do not point this at real PHI, ITAR-controlled data, or tribal
  records. The bundle is tester-only — use a test machine and
  synthetic data.
- Do not edit committed config to "fix" something during testing.
  File the issue instead (TESTER-INSTRUCTIONS.md §5). Patches to
  the freeze go in RC1.1, not on your machine.

HOW TO REPLY

Use the issue form in TESTER-INSTRUCTIONS.md §5 (track, severity,
freeze, platform, what-ran, expected, saw). One issue per problem.
If everything passed, a one-line "Track [A/B/C] pass on [your OS /
your CPU], freeze dceaabc, no findings" report is exactly what I
need.

Reply by [date]. If anything is unclear, ask before running — the
worst outcome is wasted tester-hours from a documentation gap
that's already known.

Thanks — this unblocks the whole release.

[Your name]
```

## 6. Feedback Intake

One subsection per tester. Add as feedback arrives.

### 6.1 Self-Review — Claude (NOT outside-tester evidence)

**Type:** Self-review (parallel to RC-06's Track A+B rehearsal).
**Track:** C — security/compliance review.
**Date:** 2026-05-24.
**Bundle:** extracted from `Lamprey-MAI-RC1.3.zip` (sha256 `9a2f95ee…`)
to `C:/Users/17076/Documents/Claude/Island-Mountain-RC1-self-review/`.
**Full memo:** [`RC1-SELF-REVIEW-TRACK-C.md`](RC1-SELF-REVIEW-TRACK-C.md)
(626 lines).

**Why this does not satisfy RC-09 acceptance:** Claude was a
co-author on every session in the build lane. RC-09 specifically
requires "someone besides the original builder" — this is the
builder reviewing their own work. The findings here are still
real and several are High; the outside-reviewer slot remains
open. The self-review exists to catch what an outside Track C
reviewer would hit before they hit it, and to exercise the
triage matrix structurally.

**Environment:**
- OS: Windows 11 Home (build host)
- CPU: x86_64, 4-core laptop class
- RAM: ample (per laptop spec)
- Free disk before run: 647 GB
- rustc: 1.95.0
- Bundle integrity: 667/667 files OK against `CHECKSUMS.txt`

**Execution summary (§1.1 of full memo):**
- Track A binary path: boot 76 ms, `/v1/health` HTTP 200, status
  `healthy`, air-gap `compliant`.
- `cargo test -p mai-compliance --test compliance_demos`:
  **6 passed / 0 failed** (1m28s cold build, 0.32s test).
- `cargo test -p mai-compliance --test compliance_perf --release`:
  **3 passed / 0 failed** — composer P99 **300 ns**, audit
  **119 494/s**, report **1.687 ms**.

**Findings:** see §7 below, all 12 rows with IDs `H-1` through
`L-3`. Full file:line references in
`RC1-SELF-REVIEW-TRACK-C.md` §3-§5.

### 6.2 Tester 1 — John Dougherty (johndou.com, Colorado)

**Type:** Outside tester. **Satisfies RC-09 acceptance criterion
"at least one person besides the original builder has tried RC1."**
**Method:** GitDoctor (gitdoctor.io) AI code-scan service ran a
static analysis against `USS-Parks/im-mighty-eel-mai` (`origin/main`,
which at the scan moment was in sync with local `5be7d2b`), plus a
manual read by John. 50 checks run, 41 pass, 9 fail, 0 critical, 3
security findings, 10 tips.
**Date sent:** 2026-05-23 overnight.
**Date replied:** 2026-05-24.
**Bundle variant tested:** repo at `5be7d2b` (the RC-09 self-review
commit); not the assembled archive at `dceaabc`+RC1.1-docs. Note:
the RC1.1-docs patches in commits `b0fcdee` + `a6fa65e` landed
after John's scan; some of his findings (specifically the doc gaps
the self-review caught) are therefore already addressed in the
current bundle.

**GitDoctor score block:**

| Category | Score | Severity |
|---|---|---|
| Overall | 52/100 | Needs Work |
| Vibe Score | 35/100 | Likely Vibe-Coded (negative) |
| Production Score | 41/100 | Needs Work |
| Code Quality | 40/100 | — |
| Error Handling | 60/100 | — |
| Security | 75/100 | — |
| Testing | 25/100 | — |
| Documentation | 85/100 | — |
| Architecture | 70/100 | — |
| Scalability | 45/100 | — |
| DevOps Readiness | 65/100 | — |

**Raw email (excerpted, preserved verbatim from Basho's relay):**

> Basho, I'm going to tell you what needs to happen. These aren't
> suggestions. The project needs significant improvements before
> production. There are signs of AI-generated or vibe-coded patterns
> throughout the code on this project that indicate improper review.
> Extensive use of TODO placeholders and incomplete implementations
> throughout. […many specific findings, see plan §2 for the full
> enumeration…] These are just the things that popped up during
> testing this morning. — John

The full email is preserved in
[`dougherty/JOHN-REMEDIATION-PLAN.md`](dougherty/JOHN-REMEDIATION-PLAN.md)
§1.1 plus per-finding rows in §2. The 15 GitDoctor scan
screenshots are stored at
[`test-evidence/dougherty-scan-2026-05-24/`](../test-evidence/dougherty-scan-2026-05-24/).

**Triage authority:** Basho authored a full
[`JOHN-REMEDIATION-PLAN.md`](dougherty/JOHN-REMEDIATION-PLAN.md)
(296 lines, 10 workstreams, 26 sessions J-01..J-26) and a per-session
[`JOHN-REMEDIATION-ROSTER.md`](dougherty/JOHN-REMEDIATION-ROSTER.md)
(1 249 lines). The plan walks every line of John's email AND every
GitDoctor flag with a per-row verdict against the actual filesystem
(TRUE / FALSE / MIXED). Items judged false positive are kept in
scope as **documented refutations** rather than silently dropped —
this is W8 (Refutation Evidence Pack) in the plan.

**Spot-checks performed during the close-out** to ground-truth the
plan's triage:

| Plan claim | Spot-check command | Result |
|---|---|---|
| `mai-sdk-rs/src/lib.rs` has 17 `todo!()` sites at lines 768-887 | `grep -cn 'todo!' mai-sdk-rs/src/lib.rs` | 17 ✓; line numbers match 768-887 |
| `Math.random` in `.integrity/mcp-server/server.js` | `grep -n "Math\.random"` | line 244 (plan said 233 — drift, finding is real) ✓ |
| `.gitignore` missing `node_modules` | `grep -E node_modules .gitignore` | absent ✓ |
| No Python lock file | `ls requirements*.txt uv.lock poetry.lock` | none ✓ |

Plan triage is grounded. Findings entered into §7 below.

**Summary lines for §3 counters:** 1 invited, 1 responded, RC-09
acceptance MET, blockers routed to the DOUGHERTY lane.

## 7. Triage Matrix

Each finding from §6 gets one row. Categorise into one of the
roadmap's four buckets and assign disposition.

| ID | Tester | Track | Severity | Bucket | Summary | Disposition |
|---|---|---|---|---|---|---|
| H-1 | self-review §6.1 | C | High | docs | `mai-admin` runbook commands (`audit verify`, `compliance report/verify`, `policy inspect`, `audit tail`) are stubs or undeclared at the freeze | fix-in-RC10 |
| H-2 | self-review §6.1 | C | High | docs | All four acquisition demos reference a `mai` CLI that does not ship | fix-in-RC10 |
| H-3 | self-review §6.1 | C | High | docs | All four acquisition demos cite REST port 8080 (and dashboard 8081); actual daemon binds 8420 / 8421 | fix-in-RC10 |
| H-4 | self-review §6.1 | C | High | docs | All four acquisition demos hardcode `cd "$env:USERPROFILE\Documents\Claude\Island Mountain Mighty Eel OS\mai"` — the builder's workspace path | fix-in-RC10 |
| H-5 | self-review §6.1 | C | High | docs | TESTER-INSTRUCTIONS.md §4.C step 4 cites all five runbook numbers wrong (04/05/09/10/11 vs actual 05/06/11/12/13) | fix-in-RC10 |
| M-1 | self-review §6.1 | C | Medium | docs | TESTER-INSTRUCTIONS.md §4.C step 2 references "three layer docs (router, policy, audit)" that do not exist as separate files (they're inline in ARCHITECTURE.md) | fix-in-RC10 |
| M-2 | self-review §6.1 | C | Medium | docs OR code | README-FIRST.md §5.C documents logs on stderr; observed runtime puts all logs + banner on stdout | needs-investigation (decide doc vs runtime fix) |
| M-3 | self-review §6.1 | C | Medium | docs | Demos prescribe `cargo run --release --bin mai-api` instead of leveraging the bundled `bin/lamprey-mai-api.exe` from RC1 v2 | fix-in-RC10 |
| M-4 | self-review §6.1 | C | Medium | docs | Runbooks 05/06/11/12/13 use Linux systemd / `/var/lib/mai/...` paths exclusively; bundle is Windows MSVC tester-only. Gap is implicit — no header note tells Track C reviewer these runbooks describe production posture, not tester procedure | fix-in-RC10 |
| L-1 | self-review §6.1 | C | Low | docs | README-FIRST.md:175 "MAI server ready - REST …" uses hyphen; runtime emits em-dash. Cosmetic | dismiss-or-low-fix |
| L-2 | self-review §6.1 | C | Low | docs | ARCHITECTURE.md:318 references `mai/compliance-dashboard/` and `mai/deployment/...` — inside the bundle the path is bare (no `mai/` prefix) | dismiss |
| L-3 | self-review §6.1 | C | Low | code | Health endpoint reports `"gpus":[]` while topology log reports `gpus=1` (probably intentional layer divergence; presents as inconsistent) | needs-investigation |
| --- | --- | --- | --- | --- | **John Dougherty (§6.2) — summary; canonical per-row triage in [dougherty/JOHN-REMEDIATION-PLAN.md §2](dougherty/JOHN-REMEDIATION-PLAN.md)** | --- |
| J-1 | John §6.2 | GitDoctor + manual | High | docs+code | "TODOs and incomplete implementations throughout" (QUA-004 + Placeholder HIGH) — MIXED: TRUE for `mai-sdk-rs/src/lib.rs` (17 todo! at 768-887) and `.integrity/mcp-server/server.js`; FALSE for `adapters/*/adapter.py` (Ollama 316 LOC, llama.cpp 273, etc. — zero `NotImplementedError`, zero trailing `pass`) | fix-in-DOUGHERTY (W10 for SDK, W6 for mcp; refute adapter claim in W8) |
| J-2 | John §6.2 | GitDoctor | High | code | SEC-009 — `Math.random` in security-sensitive context (`.integrity/mcp-server/server.js:244` — drift from plan's "233" but real) | fix-in-DOUGHERTY (W1 / J-01, mechanical Edit) |
| J-3 | John §6.2 | manual | refute | n/a | "Stdlib-only restriction needs to be improved" — stdlib-only is intentional air-gap design for the inference + compliance core; pulling third-party crates is a regression | refute-in-W8 (carve-out for `mai-sdk-rs` which is consumed outside the air-gap boundary — that gets `reqwest`/`eventsource-client` in J-16/J-17) |
| J-4 | John §6.2 | GitDoctor + manual | refute | n/a | "Start with Ollama adapter and implement all methods fully" — Ollama adapter is already the Session 08 deliverable, full body, full test coverage | refute-in-W8 (cite session-08 evidence + `wc -l` + assertion counts) |
| J-5 | John §6.2 | GitDoctor | High | packaging | PRJ-004 — missing lock files (Python + Node) — `Cargo.lock` exists; no `requirements-lock.txt` / `uv.lock` / `poetry.lock`; no `package-lock.json` in `.integrity/mcp-server/` | fix-in-DOUGHERTY (W2 / J-03) |
| J-6 | John §6.2 | GitDoctor + manual | Medium | packaging | "Add Docker configuration with multi-stage builds" (CFG-007 LOW + Tip HIGH) — no Dockerfile in tree | fix-in-DOUGHERTY (W2 / J-04, CPU-only, multi-stage) |
| J-7 | John §6.2 | GitDoctor | Medium | packaging | PRJ-002 — `.gitignore` missing `node_modules/` (true; `.env` / `dist/` / `build/` already present) | fix-in-DOUGHERTY (W2 / J-02, one-line Edit) |
| J-8 | John §6.2 | GitDoctor + manual | Medium | tests | TST-001/004/005/006 — "tests are minimal stubs with mocked responses" — MIXED: Ollama has 38 assertions (real); llamacpp 14, exllamav2 13 (thin); compliance demos are real (verified in self-review §1.1: 6/6 pass) | fix-in-DOUGHERTY (W3 live-backend + W5 assertion fill) |
| J-9 | John §6.2 | manual | Medium | code | "HTTP connection pooling on adapter clients" — likely real; needs measurement | fix-in-DOUGHERTY (W3 / J-05 audit, fold into each backend's J-session) |
| J-10 | John §6.2 | manual | Medium | code | "Async context managers for adapter lifecycle" — real; adapters expose `initialize`/`shutdown` not `__aenter__`/`__aexit__` | fix-in-DOUGHERTY (W7 / J-12) |
| J-11 | John §6.2 | manual | Medium | code | "Health check aggregator for production monitoring" — per-adapter health exists; no aggregator at `/health/system` | fix-in-DOUGHERTY (W7 / J-13) |
| J-12 | John §6.2 | manual | refute | n/a | "Simple web dashboard for monitoring adapter status" — conflicts with CLAUDE.md "compliance dashboard is sole UI exception" air-gap rule | refute-in-W8 + propose CLI alternative |
| J-13 | John §6.2 | GitDoctor | Low | code | PERF-004 — JSON.stringify in loop (server.js:317) | fix-in-DOUGHERTY (W6 / J-11, alongside MCP refactor) |
| J-14 | John §6.2 | GitDoctor | Medium | code | QUA-001 — "god files >300 lines" — TRUE for `server.js` (371), `adapters/vllm/adapter.py` (332); Ollama 316 is acceptable for a full backend adapter | fix-in-DOUGHERTY (W6 splits server.js; vllm flagged for review in J-18) |
| J-15 | John §6.2 | GitDoctor | Low | code | QUA-009 — "4+ levels of nesting" at `server.js:69` | fix-in-DOUGHERTY (W6 / J-11, extract helpers + early returns) |
| J-16 | John §6.2 | GitDoctor + manual | Medium | tests | TST-005 — "no integration or e2e tests" — Partial: Rust workspace has 1539 tests + 6 compliance demos; Python adapter layer lacks live-backend integration | fix-in-DOUGHERTY (W3 live-backend matrix + W5 e2e smoke) |
| J-17 | John §6.2 | manual | refute | n/a | "Flat project structure" — FALSE; `mai/` already organises into `mai-{api,compliance,scheduler,core,…}/` crates plus `adapters/{ollama,llamacpp,…}/`, `docs/`, `tests/`, `.integrity/`. GitDoctor's PRJ-005 actually PASSED in the scan; John mis-paraphrased | refute-in-W8 with tree-output evidence |
| J-18 | John §6.2 | manual | High | code | "Error mapping designed but not consistently applied" (Error Handling 60/100) | fix-in-DOUGHERTY (W4 / J-08 — produces ERROR-PATH-AUDIT.md) |
| J-1b | direct review (Basho 2026-05-24) | manual | High | code | `mai-sdk-rs/src/lib.rs` 17 `todo!()` HTTP-client stubs (previously SHIP-17 KNOWN-ISSUES.md Issue 15, "no in-tree consumer, not lane-blocking" — true at the time but John-visible to any reviewer) | fix-in-DOUGHERTY (W10 / J-16 + J-17) |

**Bucket definitions** (per roadmap RC-09):

- **docs** — README-FIRST, TESTER-INSTRUCTIONS, runbooks, or any
  other documentation file is wrong, missing, or misleading. Fix
  in RC-10 with a doc patch.
- **packaging** — manifest exclusion missed something, the bundle
  contains a stray file, an RC1-era doc was not forwarded, or
  the archive itself is broken. Fix in RC-10 by patching
  `RC1-PACKAGE-MANIFEST.md` and rebuilding.
- **code** — the freeze itself misbehaves on a supported platform.
  Fix requires touching `mai-*/src/*` and bumps the freeze
  commit. May force an RC1.1 reissue.
- **environment** — the problem is on the tester's machine
  (wrong toolchain version, missing dependency outside our
  declared minimums, antivirus interference, etc.). Record the
  workaround in `README-FIRST.md` §3 if it's likely to recur;
  otherwise note and dismiss.

**Disposition values:** `fix-in-RC10` (mandatory before wider
sharing), `defer-to-RC2` (known limitation, explicitly out of
RC1 scope), `dismiss` (not actionable / not our bug), or
`needs-investigation`.

## 8. Blockers For Wider Sharing

A blocker is any finding whose disposition is `fix-in-RC10` and
whose severity is `Blocker` or `High`.

| Blocker | Origin (§7 ID) | Owner | Target resolution |
|---|---|---|---|
| Acquisition demos non-runnable as written (H-2 + H-3 + H-4) | H-2, H-3, H-4 | RC-10 | **RESOLVED** in commits `b0fcdee` (RC1.1-docs) + `a6fa65e` (re-assembly) — demos now use curl against `:8420` from `cd source` |
| Operator runbooks reference unimplemented CLI surfaces (H-1) | H-1 | RC-10 | **RESOLVED** in commit `b0fcdee` — header bands on runbooks 05/06/11/12/13 cite stubbed `mai-admin` subcommands and their HTTP equivalents |
| Track C reading list points at wrong runbooks (H-5) | H-5 | RC-10 | **RESOLVED** in commit `b0fcdee` — TESTER-INSTRUCTIONS.md §4.C step 4 numbers fixed |
| `Math.random` in security context (SEC-009 HIGH) | J-2 | DOUGHERTY W1 / J-01 | **RESOLVED** in commit `6621c02` — `crypto.randomUUID()` at `.integrity/mcp-server/server.js:244`; SEC-009 PASS on rescan |
| Missing dependency lock files (PRJ-004 HIGH) | J-5 | DOUGHERTY W2 / J-03 | **RESOLVED** in commit `468e0e8` — `requirements-lock.txt` + `.integrity/mcp-server/package-lock.json` + policy doc (scanner false-negative on rescan; lock files present at repo root) |
| mai-sdk-rs HTTP client 17 `todo!()` stubs | J-1, J-1b | DOUGHERTY W10 / J-16+J-17 | **RESOLVED** in commits `b281b55` (J-16 impl) + `88fa06e` (J-16b wiremock tests) + `8d412c6` (J-17 SSE+resume); `grep -c 'todo!' mai-sdk-rs/src/lib.rs` = 0; KNOWN-ISSUES.md Issue 15 CLOSED |
| Adapter test thinness (TST-001/004/005/006) | J-8 | DOUGHERTY W3 + W5 | **RESOLVED** — J-09 `d18da96` (assertion fill llamacpp 14→58, exllamav2 13→64) + `182e075` (real-HTTP streaming) + J-10 `2a7bced` (assertion gate + e2e smoke) + W3 J-18..J-26 live-backend tests across vLLM/TGI/SGLang/ExLlamaV2/TensorRT/OpenAI-compat/ONNX/MLX/Triton |
| Error path inconsistency (60/100) | J-18 | DOUGHERTY W4 / J-08 | **RESOLVED** in commit `606e821` — `docs/ERROR-PATH-AUDIT.md` covers 10 handler modules / 56 handlers (53 PASS / 3 FIX-NEEDED, all 3 fixed in same commit); Error Handling 60→85 on rescan |
| No Docker config | J-6 | DOUGHERTY W2 / J-04 | **RESOLVED** in commit `2cdc23a` (+ fix-up `e32d8fe`) — CPU-only multi-stage `Dockerfile` + `.dockerignore` + `.env.example` at repo root |

**Note:** The first three rows (self-review H-1/H-2/H-3/H-4/H-5)
were resolved by the RC-10 RC1.1-docs pass (commits `b0fcdee` +
`a6fa65e`) **before** John's review landed. The remaining rows are
the DOUGHERTY-lane blockers John identified that go into RC1.2
(post-J-lane). See [`dougherty/JOHN-REMEDIATION-PLAN.md`](dougherty/JOHN-REMEDIATION-PLAN.md)
§5 for per-workstream acceptance criteria and §6 for the lane's
Definition of Done.

The roadmap's RC-09 acceptance includes "blockers are known
before wider sharing." Both the self-review and John's outside
review have now contributed blocker lists. This table is the
answer to that.

## 9. Acceptance vs RC-09 Criteria

| Criterion | Status |
|---|---|
| At least one person besides the original builder has tried RC1 | **YES** — John Dougherty (§6.2), GitDoctor scan + manual read, 2026-05-24 |
| Feedback is captured in `RC1-TESTER-FEEDBACK.md` | **YES** — §6.1 self-review intake (12 findings, 9 already resolved) + §6.2 outside-tester intake (full email + scan score block + 15 screenshots in `test-evidence/dougherty-scan-2026-05-24/`); §7 triage matrix carries both with per-row verdicts (TRUE / FALSE / MIXED per the plan) |
| Blockers are known before wider sharing | **YES** — §8 lists self-review blockers (3 resolved in commits `b0fcdee` + `a6fa65e`) + the DOUGHERTY-lane blockers from John's review (routed to J-01..J-26) |

**RC-09 is CLOSED.** John's review satisfies the outside-tester
criterion; his findings are triaged in §7, blockers are enumerated
in §8 and routed to the DOUGHERTY remediation lane in
[`dougherty/JOHN-REMEDIATION-PLAN.md`](dougherty/JOHN-REMEDIATION-PLAN.md).
Per the plan's §1.2 sequence diagram:

```
RC-08 (bundle) → RC-09 (tester verdict: John) → [DOUGHERTY LANE: J-01..J-26] → RC-10 (re-bundle) → RC-11 (re-ship)
```

The "RC-10" in the new sequence is the post-DOUGHERTY re-bundle
(distinct from the earlier RC-10 RC1.1-docs self-review fix pass
that already shipped in `b0fcdee` / `a6fa65e`). RC-11 is the
re-ship to John for verification.

**DOUGHERTY lane CLOSED 2026-05-24.** All 26 sessions committed
(`6621c02` … `b899a84`). Outside-tester response doc at
[`RC1-TESTER-RESPONSE-DOUGHERTY.md`](RC1-TESTER-RESPONSE-DOUGHERTY.md)
with full per-row verdicts, commit hashes, and the §4 refutations of
items we believe the scan got wrong. Rescan via VibecoderHub (the
scanner provider differed from John's original GitDoctor run) shows
overall 52→75, vibe 35→80, production 41→70, testing 25→70, security
16/16 PASS; evidence at
[`test-evidence/dougherty-rescan/SUMMARY.md`](../test-evidence/dougherty-rescan/SUMMARY.md).
All 5 remaining FAILs verified as scanner false negatives against the
working tree. RC-10 (re-bundle) is now unblocked; prerequisite
checklist at [`RC1.2-REBUNDLE-CHECKLIST.md`](RC1.2-REBUNDLE-CHECKLIST.md).
