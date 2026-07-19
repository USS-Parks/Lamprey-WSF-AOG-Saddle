# SAD-HIST-04 Archive Publication

**Repository:** `USS-Parks/Lamprey-WSF-AOG-Saddle`

**Namespace:** `refs/heads/history/mighty-eel/...`

**Result:** the 38 approved sanitized history refs are published and protected;
active Saddle history remains separate

## Published boundary

SAD-HIST-04 reproduced the SAD-HIST-02 sanitized archive byte-for-byte from
the 38 frozen Mighty Eel heads. Gitleaks 8.30.1 and TruffleHog 3.95.9 rescanned
the exact original and sanitized closures. The complete proof passed before
any archive ref was created.

The refs were then pushed individually from the isolated bare archive. No
mirror push, source-history merge, replacement ref, graft, tag, or active
Saddle branch update was used. The remote namespace contains exactly the 38
approved refs and tips recorded in
`test-evidence/saddle/SAD-HIST-04/archive-publication.json`.

The published graph contains 762 commits and 10,444 reachable objects: 4,885
blobs, 4,797 trees, and 762 commits. Its deterministic object-metadata digest
is `dc5ce6d06965c2e3bcef43826101d9ee669cdbb1f4a29131edd5ff071aae996d`.
The remote ref digest is
`0ee1e6f6ec666f4a5e9e61f81e5584cc881be6942e1bb0ac1ded60ac35133b26`.

## Sanitization and provenance

The original secret-bearing blob
`ffb2ea027f2a965cdad277c1ebbde291d3314a36` and commit
`c75e95f15256b929e382ec58658348502e6a5f83` are absent from the sanitized
archive. One blob, ten trees, and 456 commits changed. The rewrite removed 235
stored signatures that could not remain valid after their signed objects
changed; the original signed SHAs remain cited as external provenance.

The immutable old-to-new ledger contains all 10,444 objects. Every published
ref record binds its source ref, original tip, sanitized tip, and observed
remote tip. The source safety, scanner, object-map, and SAD-HIST-03
reconciliation digests are also bound into the final evidence.

## Protection

GitHub repository ruleset `19173522`, **Immutable Mighty Eel history archive**,
is active for `refs/heads/history/mighty-eel/**`. It prohibits deletion,
updates, and non-fast-forward changes. It has no bypass actors, and the
publication verifier recorded that the current user cannot bypass it.

## Active Saddle invariants

`origin/main` checkpoint `f66134ef4b3b36c1506f277dbbb9bf61c7d82d7c`
was already an ancestor of the reviewed lane before publication. The only
active product changes in the complete history lane are the reviewed
SAD-HIST-03 WSF OpenAPI adaptation and its bounded no-phone-home scanner
repair. `Cargo.toml` and `Cargo.lock` are byte-identical to the reconciled
base, so the active dependency graph did not change. Archive refs are not
parents of Saddle `main` and were not fetched into its active history.

## Evidence and reproduction

- `test-evidence/saddle/SAD-HIST-04/archive-publication.json`, SHA-256
  `22d9f939d11d90697b9d2a87e8b6c34fe424fd28baa9f262a7d4e38699e8d1b7`;
- `tools/verify_saddle_history_publication.py`, SHA-256
  `b6ca51b4e253a178d86262baf553d262cc2e31d30085645619d293b0f05033e2`;
- SAD-HIST-02 object map, SHA-256
  `146a43b93caa86538e1ec70c53dabc2622b774a86a92384d1fb683f2b36499fe`;
- SAD-HIST-02 normalized scanner findings, SHA-256
  `404ac5048b8d538a76480fbf16d934b3edd84473ee4756d1852baba1fa7369d7`;
  and
- SAD-HIST-03 reconciliation ledger, SHA-256
  `22999fdf63a08989887f97fe78fcff1ef4da0b0636ed32a8f51f085b47bfab7c`.

Live deterministic verification uses the isolated sanitized bare repository:

```powershell
python tools\verify_saddle_history_publication.py `
  --root . `
  --archive-repo '<sanitized-archive.git>' `
  --ruleset-id 19173522 `
  --verify
```

CI and clean checkouts can verify the recorded proof without importing archive
objects or requiring repository-administration credentials:

```powershell
python tools\verify_saddle_history_publication.py --root . --verify-recorded
```

Archive publication is complete. Integration and canonical-plan closeout
remain separate until the reviewed lane passes its full applicable workflow
stack and is merged without squashing.
