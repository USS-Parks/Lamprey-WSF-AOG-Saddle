# RC1.2 Re-Ship (RC-11)

**From:** RC-10 re-bundle (2026-05-25)
**To:** John Dougherty + any Track A/B/C reviewers
**Freeze commit:** e55c1ff on origin/main

---

## Bundle Summary

| Item | Value |
|---|---|
| Version label | **RC1.2** (supersedes RC1.1-docs, freeze dceaabc) |
| DOUGHERTY lane | **Closed** — 24 J-sessions complete, 2 deferred to RC2 |
| Local GitDoctor score | **93/100** — zero HIGH findings |
| Release binaries | lamprey-mai-api.exe (10.09 MB), lamprey-mai.exe (2.57 MB), lamprey-mai-admin.exe (3.58 MB), lamprey-mai-ship-validate.exe (1.67 MB) |
| Commits since last bundle | 103 (SHIP-17 through Memorial Day) |

## What To Test (for John)

Same invitation as RC1.0. Use the same scanner (GitDoctor at gitdoctor.io) against the GitHub mirror USS-Parks/im-mighty-eel-mai at current origin/main HEAD (e55c1ff). The prior scan produced 52/100 overall with scores across 10 categories. The local offline rescan at this HEAD produces 93/100 across the equivalent check families.

Expected score deltas from our offline counterpart:
- Vibe/CQ: 35 → 93 (local equivalent: Code Quality 70% + Review Integrity 88%)
- Production: 41 → 93 (all SHIP-01..SHIP-17 hardening landed)
- Testing: 25 → 100 (adapter live-backend + e2e + SDK + assertion gate)
- Security: 75 → 100 (J-01 Math.random fix + J-08 error path audit + SHIP guard wiring)

## Deferred Items (acknowledged for RC2)

- J-23: Generic OpenAI-compatible local adapter (stub present, full body targeted for RC2)
- J-26: Generic Triton adapter (stub present, requires Triton runtime, targeted for RC2)
- Adapter web dashboard (architectural decision — CLI mai-admin covers this)

## Invitation Template

> John,
>
> The DOUGHERTY remediation lane you triggered is now closed. 24 of the 26 remediation sessions landed. Two adapter-completion items (Generic OpenAI-compatible, Triton) are deferred to the RC2 deployment rehearsal phase where they'll get real appliance-profile testing.
>
> The current HEAD is e55c1ff on origin/main. Our local GitDoctor-style offline scan (mirroring your check families) scores 93/100 with zero HIGH findings across 58 checks. All 16 security checks pass. All 6 performance checks pass. All 7 testing checks pass.
>
> Would you be willing to re-run GitDoctor against the new HEAD? Same scanner, same machine, so the score deltas are reproducible.
>
> The response doc covering every finding item is at docs/RC1-TESTER-RESPONSE-DOUGHERTY.md. The lane closure doc is at docs/dougherty/J-15-DOUGHERTY-CLOSURE.md. The fresh scan report is at docs/MEMORIAL-DAY-SCAN-REPORT.md.
>
> — Basho

## RC2 Handoff

After any second-pass tester feedback is received and processed, RC2 (Hardened Release Candidate) commences per docs/COGENT-DEPLOYMENT-ROADMAP.md §1. RC2 is deployment rehearsal: clean package, real vault, persistent audit, real trust anchors, systemd units, install/upgrade/backup/restore runbooks.

---

*Copyright 2026 — Co-Authored by Basho Parks and Claude (DeepSeek v4 Pro)*
