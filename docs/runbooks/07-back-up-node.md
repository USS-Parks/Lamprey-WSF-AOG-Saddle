# Runbook 07 — Back Up a Node

## When to use

- Scheduled (`mai-healthcheck.timer` can drive this nightly; sites
  often add their own offsite mirror).
- Pre-upgrade — always, even for "small" upgrades.
- Pre-rotation of a trust anchor or compliance signing key.
- Whenever the operator changes anything under `/etc/mai/`.

## What gets backed up

`mai-admin backup` captures ten components by sha3-256, wrapped
in a manifest signed by the backup signing key (separate from
the compliance signing key). See `packaging/README.md` for the
on-disk layout and `tools/mai-admin/src/backup.rs` for the
authoritative component list.

Auth keys are stored as **hashes**, never plaintext. Vault
contents are captured by snapshot reference, not by re-export —
the ZFS dataset is the source of truth.

## Steps

1. Stage an output dir under `/var/backups/mai/`:
   ```bash
   OUT=/var/backups/mai/$(date +%Y%m%d-%H%M)
   sudo install -d -o mai -g mai -m 0750 "$OUT"
   ```
2. Run the backup:
   ```bash
   sudo -u mai mai-admin backup create --out "$OUT"
   ```
   The daemon does not need to be stopped; the WAL is captured
   under a frozen tail and the ZFS vault is snapshotted before
   read.
3. Verify the backup against itself before trusting it:
   ```bash
   sudo -u mai mai-admin backup verify "$OUT"
   ```
   Exit `0` is required. Non-zero: do **not** delete the prior
   good backup. Investigate.
4. (Optional but recommended) mirror offsite:
   ```bash
   rsync -av --delete-after \
        "$OUT" mirror:/srv/mai-backups/<host>/
   ```
   Mirrors must use an out-of-band trust channel and must verify
   the manifest signature on receipt; do not trust raw rsync
   completion as integrity evidence.

## Retention

Default: keep nightly for 14 days, weekly for 8 weeks, monthly
for 12 months. The `mai-healthcheck.timer` job that drives
backups also runs the pruner; configure under
`/etc/mai/backup-retention.toml`.

Backups outside the retention window are removed by the pruner
only after they are verified to not be the most recent valid
backup. Defense-in-depth: even a corrupt pruner will not remove
the freshest known-good backup.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `vault_snapshot_failed` | ZFS dataset not the configured one | Confirm `vault.zfs.dataset` in `profile.toml`; do not silently fall back to a file copy |
| `signature_failed` on verify | Manifest signed by the wrong key, disk corruption mid-write | Re-run; if persistent, treat as an integrity incident |
| Out of disk | `/var/backups/mai/` partition full | See [14-disk-almost-full](14-disk-almost-full.md); never resolve by deleting backups arbitrarily |

## Do not

- Do not `tar` `/var/lib/mai/` by hand and call it a backup. The
  WAL must be captured under the documented freeze, and the
  vault must be captured by ZFS snapshot reference. Hand-rolled
  tarballs lose both guarantees.
- Do not encrypt the backup with a key that lives only on this
  host. The point of a backup is to survive this host.
- Do not skip `backup verify`. The verify step is the **only**
  thing that proves the backup is restorable.
