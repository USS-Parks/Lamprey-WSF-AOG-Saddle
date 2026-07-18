# Saddle SAD-03 No-Secret Import Procedure

**Seed:** `Mighty-Eel-OS` commit `fedf005a30ad388ab156dc8bd693a3aa3f0702ea`
**Scope:** The tracked-only import path used before any WSF, AOG, or Saddle
source is materialized in the target repository.
**Status:** SAD-03 gate PASS; source import remains the responsibility of
`SAD-10` and `SAD-11`.

## Safety invariant

The archive is built from Git blobs at the pinned commit, never from a seed
working tree. It may contain only ledger entries with an `import`, `extract`,
or `historical-evidence` disposition that pass every path restriction. The
target repository retains metadata and hashes, not the temporary source archive
or generated runtime material.

The procedure rejects private-key-shaped filenames, non-placeholder `.env`
files, Git internals, submodules, symlinks, build output, OpenBao state, and
the pre-generated staging bundle cache. It also excludes six historical
artifacts with credential- or token-shaped fixture material. Their immutable
seed hashes remain in the SAD-02 provenance ledger.

## Executable proof

`tools/prove_saddle_no_secret_import.py` performs the gate:

1. requires a clean seed checkout at the exact SHA;
2. verifies every selected Git blob's object ID, mode, byte size, and SHA-256
   against the SAD-02 ledger;
3. creates a deterministic temporary archive and extracts it outside the
   target's staged tree;
4. stages raw source blobs into a temporary Git index, bypassing checkout
   filters and proving that the index exactly matches the verified source
   objects; and
5. runs strict default-rule Gitleaks plus the dependency-free Saddle static
   detector before emitting only safe metadata.

The 49 `hashed_secret` values in `.secrets.baseline` are validated as exact
SHA-1 detector digests before that metadata file is narrowly omitted from the
Gitleaks input. This is validation of a detector baseline, not an unchecked
suppression. All remaining suppressions are exact path/rule/line/fingerprint
records with reviewed synthetic-fixture reasons:

- `test-evidence/saddle/SAD-03/gitleaks-reviewed-exceptions.json`; and
- `test-evidence/saddle/SAD-03/secondary-reviewed-exceptions.json`.

The gate result is 898 allowlisted paths, zero unsuppressed findings from both
detectors, and staged tree
`6f963caa9c5cdf44fe07f53cf48af4798ba21065`.

| Artifact | SHA-256 |
|---|---|
| allowlist | `d1b4106a3ee2e883a1807836b714bb823b97270de05e9a9cf60692dd872886b8` |
| temporary archive | `e07a17ab4ab682aa912aa7fb4e15ca748788e8dfaa26523578f9ca963790d117` |
| no-secret proof | `a00a15cbe9ddd3de48e7ac97f55bda77a8613478f102cb9c5e102ebdd78a9f1c` |

## Runtime-only replacement material

`tools/generate_saddle_ephemeral_test_material.py` creates a disposable test
CA plus server/client certificates, three private keys, and empty state
directories for OpenBao, Saddle store, Raft, audit, and receipts. It refuses to
overwrite an existing output directory. The private material is generated only
at a caller-selected runtime path, verified against the generated CA, and then
removed after use. It is never archived, allowlisted, staged, or committed.

The verified generator source hash is
`ad93938d32f9ad49a6980fd322f877365414530e6ae6a60713b7ed743a5f6f3b`.

## Operator command

Run from a clean Saddle checkout with a clean seed worktree at the pinned SHA:

```text
python -B tools/prove_saddle_no_secret_import.py \
  --seed-repo <clean-mighty-eel-os-checkout> \
  --seed-sha fedf005a30ad388ab156dc8bd693a3aa3f0702ea \
  --source-manifest test-evidence/saddle/SAD-02/source-manifest.json \
  --allowlist-output test-evidence/saddle/SAD-03/import-allowlist.json \
  --evidence-output test-evidence/saddle/SAD-03/no-secret-import-proof.json \
  --scratch-root <short-disposable-directory> \
  --runtime-generator tools/generate_saddle_ephemeral_test_material.py \
  --gitleaks-exceptions test-evidence/saddle/SAD-03/gitleaks-reviewed-exceptions.json \
  --static-exceptions test-evidence/saddle/SAD-03/secondary-reviewed-exceptions.json
```

On Windows, the scratch directory must be short enough for the longest source
path; the tool fails before materialization when the staged simulation would
exceed its safe path-length budget.
