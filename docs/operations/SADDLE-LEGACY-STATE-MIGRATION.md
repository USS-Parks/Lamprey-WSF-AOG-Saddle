# Saddle versioned legacy-state migration

This runbook covers persisted estate resources created before the Saddle
runtime-identity cutover. `saddlectl migrate` is an offline, version-preserving
transform: it reads a complete versioned estate snapshot and writes a separate
migrated snapshot plus a rollback journal. It never performs normal API CRUD,
so migration does not mint new authority, advance resource versions, or append
receipts.

## Safety contract

- Quiesce control-plane writes and capture a verified backup before exporting
  the estate. Do not edit a live Raft or redb file.
- Export the exact `Store::range("")` entries through
  `EstateSnapshot::from_versioned_entries`. The inverse
  `EstateSnapshot::into_versioned_entries` is the input to `Store::restore` in
  the maintenance/restore path.
- Keep input, migrated output, and journal on distinct paths. `apply` resolves
  aliases and refuses to overwrite any existing output or its input.
- Keep the journal until the migrated estate has passed verification and the
  operational rollback window has closed. It contains the full original
  versioned snapshot and is sensitive operational state.
- Restore into a quiesced estate through the normal maintenance path. For a
  Raft estate, restore consistently at the cluster recovery boundary; never
  patch one running replica behind Raft.

The versioned snapshot schema is `saddle-versioned-estate/v1`. Each entry has a
key plus the stored value bytes, `create_revision`, `mod_revision`, and
per-key `version`; entries are in strict ascending key order, matching
`Store::range("")`. The journal schema is
`saddle-legacy-state-migration/v1`.

## What changes

The transformer recognizes only three structural identities:

1. the retired estate API group/version becomes
   `saddle.islandmountain.io/v1`;
2. retired controller finalizers keep their suffix and move to the
   `saddle.islandmountain.io/` namespace; and
3. the retired cordon label key becomes
   `saddle.islandmountain.io/unschedulable`.

Everything else is opaque. In particular, keys, UIDs, tenants, generations,
resource versions, owner references, token references, receipt IDs/chains,
annotations, specs, statuses, OpenBao references, and non-JSON values are not
renamed. A resource containing both old and new cordon keys with different
values fails closed.

## Inspect and dry-run

```text
saddlectl migrate inspect -f estate-versioned.json
saddlectl migrate dry-run -f estate-versioned.json
```

Both commands validate schema/revisions and emit the same deterministic report:
entry counts, every proposed JSON-pointer rewrite, and protected-payload,
receipt-chain, and version-metadata digests. Neither writes a file.

## Apply

```text
saddlectl migrate apply \
  -f estate-versioned.json \
  --out estate-saddle.json \
  --journal estate-saddle.journal.json
```

Apply rechecks the protected digests before writing. The journal binds the
original and migrated snapshot digests, expected change list, all preservation
digests, and the complete original snapshot.

## Verify before restore

```text
saddlectl migrate verify \
  -f estate-saddle.json \
  --journal estate-saddle.journal.json
```

Verification fails unless deterministic replay exactly reproduces the supplied
migrated snapshot, no recognized legacy structural identity remains, all
authority/payload and receipt/version digests match, and rollback material is
complete. Install only a verified output through the quiesced
`Store::restore` maintenance seam.

## Rollback

```text
saddlectl migrate rollback \
  -f estate-saddle.json \
  --journal estate-saddle.journal.json \
  --out estate-restored.json
```

Rollback first verifies that the current input is exactly the journal-bound
migration result. It then writes the complete original keys, value bytes, and
revision tuples to a new file. Drifted or tampered migrated state is rejected;
the tool does not produce a best-effort rollback.

After restoring the rollback output through the same quiesced maintenance seam,
compare the estate export digest to the original and verify the independent
receipt ledger at its unchanged pre-migration head.

## Deterministic gate

The repository gate exercises all five modes over a representative estate,
including a JSON resource, an opaque non-JSON entry, old words deliberately
embedded in authority/receipt/opaque fields, exact `Store::range`/`restore`
adaptation, exact rollback, and rejection of a tampered receipt chain:

```text
cargo test --locked -p saddlectl
python tools/verify_saddle_legacy_state_migration.py \
  --root . \
  --evidence-output test-evidence/saddle/SAD-22/legacy-state-migration-gate.json \
  --verify
```
