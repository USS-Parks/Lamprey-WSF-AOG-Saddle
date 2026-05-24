# Runbook 14 — Disk Almost Full

## When to use

- `mai-healthcheck.timer` raised a `disk_low` alert.
- Any partition under `/var/lib/mai`, `/var/backups/mai`,
  `/var/log/mai`, or `/var/lib/mai/vault` is at >85% usage.
- The daemon emitted `audit.write.short` or
  `vault.write.short` entries.

## Why this is urgent

A full disk corrupts in flight:

- WAL appends partially complete; the next verify will find a
  truncated tail.
- Vault writes can leave the dataset in a state that requires
  the snapshot to roll back.
- Logs rotate to size 0 but applications keep their old `fd`
  open, dropping data silently.

None of those are recoverable without a verified backup.

## Immediate steps

1. Confirm scope:
   ```bash
   df -h /var/lib/mai /var/backups/mai /var/log/mai \
         /var/lib/mai/vault 2>/dev/null
   ```
2. Identify the worst offender. Most often:
   - `/var/log/mai/` — log rotation misconfigured.
   - `/var/lib/mai/models/` — a model import filled the pool.
   - `/var/backups/mai/` — the pruner stopped running.
3. If `/var/lib/mai/audit/` itself is the offender, stop the
   API immediately to prevent the WAL truncation case above:
   ```bash
   sudo systemctl stop mai-api.service
   ```

## Reclaim, by partition

### `/var/log/mai/` full
```bash
sudo journalctl --vacuum-time=14d
sudo logrotate -f /etc/logrotate.d/mai
```
If the logs are growing because the daemon is in a noisy
failure loop, fix that first; rotating faster does not address
the cause.

### `/var/backups/mai/` full
```bash
sudo -u mai mai-admin backup prune \
     --retention /etc/mai/backup-retention.toml --dry-run
sudo -u mai mai-admin backup prune \
     --retention /etc/mai/backup-retention.toml
```
The pruner refuses to remove the most recent verified backup
even if retention says to; that is intentional.

### `/var/lib/mai/models/` full
List models by size and age:
```bash
sudo -u mai mai-admin model list --by-size
```
Unload + remove models that are no longer in use **via the
model pipeline**, not via `rm`. See
[10-adapter-crash-loop](10-adapter-crash-loop.md) for why
manual removal corrupts state.

### `/var/lib/mai/vault/` (ZFS) full
```bash
sudo zpool list
sudo zfs list -o name,used,refer,quota,available
```
Vault expansion is a host-layer decision (add a vdev, raise a
quota). MAI does not write a vault-resize tool because the
underlying ZFS commands are the source of truth.

### `/var/lib/mai/audit/` full — special case
Do **not** truncate, rotate, or delete WAL segments to make
space. The chain is integrity-bearing. Options:

1. Add a new mount under `/var/lib/mai/audit/` and migrate
   segments forward (offline, with `audit verify` before and
   after).
2. Move the WAL dir to a larger filesystem entirely, update
   `profile.toml` `audit.wal_dir`, re-run
   `mai-ship-validate`.
3. If neither is possible immediately, the appliance is down
   — better than a corrupt chain.

## Verification

After reclaim:

```bash
df -h /var/lib/mai /var/backups/mai /var/log/mai
sudo mai-ship-validate --profile /etc/mai/profile.toml
sudo -u mai mai-admin audit verify --wal-dir /var/lib/mai/audit
sudo systemctl start mai-api.service
```

## Do not

- Do not delete WAL segments. See above.
- Do not delete the latest verified backup, even if the pruner
  refuses to.
- Do not move the audit dir while the daemon is running. The
  WAL writer holds open file descriptors; moving the directory
  out from under it produces exactly the corruption this
  runbook tries to prevent.
- Do not symlink `/var/lib/mai/<thing>` to free space. The
  profile validator and the WAL writer both follow symlinks
  but the audit chain assumes a single stable inode space; the
  combination is fragile.
