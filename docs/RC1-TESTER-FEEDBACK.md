# RC1 Tester Feedback

**Project:** Island Mountain MAI + Lamprey
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

Produced 2026-05-23 at the close of RC-08 packaging.

| Artefact | Size | SHA-256 |
|---|---|---|
| `MAI-Lamprey-RC1/` (uncompressed folder, 667 file entries) | 19 MB | per `MAI-Lamprey-RC1/CHECKSUMS.txt` |
| `MAI-Lamprey-RC1.tar.gz` | 5.7 MB | `22a0a4fe7adedccad309a5aaa06ca431015e2c8ae7518fd9eb004a99cfce60f2` |
| `MAI-Lamprey-RC1.zip` | 6.0 MB | `9a2f95eed44a86782a9f43df734511b0f9b2f7e6f89d51cb04ff5e6a54462a4c` |

Bundle and archives live at `C:/Users/17076/Documents/Claude/Island-Mountain-RC1-release/`
on the build host. Both archives carry the same 668 file entries;
the zip also includes 6 explicit empty-directory markers
(`source/.github/`, `source/apps/`, `source/mai-sdk-python/src/`,
`source/proto/`, `source/proto/mai/`, `test-evidence/`), which is
the normal POSIX-tar vs PKZip metadata difference, not a content
difference.

Pick **tar.gz** for Unix recipients, **zip** for Windows recipients
who do not have a tar implementation.

## 3. Current Status

| Field | Value |
|---|---|
| Track planned for first tester | **C** (security/compliance review) — selected 2026-05-23 |
| Transfer mechanism | Handled by user out-of-band; both archive variants ready |
| Testers invited | **0** |
| Testers responded | **0** |
| Findings filed | **0** |
| Blockers open | **0** |
| RC-09 acceptance met | **NO** — waiting on first tester |

This field block is the source of truth. Update it whenever a
tester is invited, responds, or files a finding.

## 4. Tester Roster

| # | Tester | Role / why invited | Track | Bundle variant | Invited (date) | Responded (date) | Status |
|---|---|---|---|---|---|---|---|
| _none yet_ | | | | | | | |

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
~3 hr] testing the Island Mountain MAI + Lamprey RC1 tester bundle
next week?

It's a self-contained release-candidate for our local-AI-with-
compliance-governance stack, frozen at commit dceaabc. The
[smoke / build+test / security] track is what I'd ask of you.

I'll send you [MAI-Lamprey-RC1.zip / .tar.gz] (~6 MB). After
download, verify SHA-256:

  [22a0a4fe7adedccad309a5aaa06ca431015e2c8ae7518fd9eb004a99cfce60f2 for .tar.gz]
  [9a2f95eed44a86782a9f43df734511b0f9b2f7e6f89d51cb04ff5e6a54462a4c for .zip]

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
Subject: RC1 tester ask — Island Mountain MAI + Lamprey, ~[30 min / 90 min / 3 hr]

Hi [Name],

I'm at Session RC-09 of the release plan for our local AI +
compliance stack (Island Mountain MAI + Lamprey), and the
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

I'll send you [MAI-Lamprey-RC1.zip / MAI-Lamprey-RC1.tar.gz] via
[mechanism]. After download, please verify the SHA-256:

  .tar.gz: 22a0a4fe7adedccad309a5aaa06ca431015e2c8ae7518fd9eb004a99cfce60f2
  .zip:    9a2f95eed44a86782a9f43df734511b0f9b2f7e6f89d51cb04ff5e6a54462a4c

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

### 6.1 _Tester 1_ (placeholder)

_To be populated when the first tester replies. Each subsection
should include the tester's environment block from the issue form,
each finding numbered, and the raw reply (or a link to it) for
audit._

## 7. Triage Matrix

Each finding from §6 gets one row. Categorise into one of the
roadmap's four buckets and assign disposition.

| ID | Tester | Track | Severity | Bucket | Summary | Disposition |
|---|---|---|---|---|---|---|
| _none yet_ | | | | | | |

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
| _none yet_ | | | |

The roadmap's RC-09 acceptance includes "blockers are known
before wider sharing." This table is the answer to that.

## 9. Acceptance vs RC-09 Criteria

| Criterion | Status |
|---|---|
| At least one person besides the original builder has tried RC1 | **NO** — §3 |
| Feedback is captured in `RC1-TESTER-FEEDBACK.md` | **PARTIAL** — this doc exists and is wired up; no entries yet |
| Blockers are known before wider sharing | **NO** — §8 |

RC-09 is open. When the first tester reports, update §3 (status
counters), §4 (roster status), §6 (intake), §7 (triage), §8
(blockers), and this table. RC-09 closes when at least one row in
§7 has a final disposition.
