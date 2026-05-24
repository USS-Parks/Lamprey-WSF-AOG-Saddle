# Runbook 08 — Restore a Node from Backup

## When to use

- Bare-metal recovery on replacement hardware.
- Suspected corruption of `/var/lib/mai/` on the running host
  (audit chain broken, vault dataset offline, etc.).
- Post-incident rollback when in-place recovery is not safe.

## Preconditions

- A backup directory verified per
  [07-back-up-node](07-back-up-node.md). If `mai-admin backup
  verify <dir>` does not exit 0 against the chosen backup, **do
  not restore from it**.
- The replacement host has had `mai_*.deb` installed and `mai`
  user + group created (postinstall does this).
- `/etc/mai/trust-anchors/` is **already seeded** with the
  anchors that signed the backup manifest. Restoring trust
  anchors from the backup is fine, but the daemon also needs to
  verify the backup itself, which requires the anchors first.
- The target state directories are empty, or `--force` is
  explicitly justified.

## Steps

1. Plan the restore — read-only verification against the
   backup, no writes to the target:
   ```bash
   sudo -u mai mai-admin restore plan \
        /var/backups/mai/20260523-0200 \
        --target /var/lib/mai
   ```
   The plan re-verifies the manifest signature, the per-component
   sha3, and replays the WAL chain on the backup side. Exit codes
   follow the §13 ship-validation convention.
2. Apply the restore:
   ```bash
   sudo -u mai mai-admin restore apply \
        /var/backups/mai/20260523-0200 \
        --target /var/lib/mai
   ```
   `apply` recomputes the sha3 after each write, replays the WAL
   chain on the restored tree, and drops two witnesses:
   `source-manifest.json` and `restore-report.json`. If the
   target has content, the command refuses to run without
   `--force`.
3. Restore configuration if the backup included it:
   ```bash
   sudo cp -a /var/backups/mai/20260523-0200/etc/. /etc/mai/
   sudo chown -R root:mai /etc/mai
   sudo find /etc/mai -type f -exec chmod 0640 {} +
   ```
4. Re-validate the production profile against the restored tree:
   ```bash
   sudo mai-ship-validate \
        --profile     /etc/mai/profile.toml \
        --state-dir   /var/lib/mai
   ```
   Exit 0 is required before starting the service.
5. Start the daemon:
   ```bash
   sudo systemctl start mai-api.service
   sudo systemctl status mai-api.service
   curl -fsS http://127.0.0.1:8420/v1/health/live
   ```

## Verification

- `mai-admin audit verify --wal-dir /var/lib/mai/audit` exits 0.
- The `last_seq` matches what the backup manifest recorded.
- `restore-report.json` lists every component with `status =
  "ok"` and no `force` flags.
- API admin endpoint reports the expected bundle id and anchor
  count.

## DR drill matrix

Drills land in `tools/mai-admin/tests/restore_e2e.rs`. The
runbook above is the operator mirror of those drills:

| Drill | Expected behavior |
|---|---|
| WAL tamper in backup | `plan` fails, target stays empty |
| Missing trust bundle | `plan` fails, target stays empty |
| Missing model registry | `plan` fails, target stays empty |
| Signed-manifest tamper | `plan` fails, target stays empty |
| Round-trip backup of restored tree | byte-identical to the original |

## Do not

- Do not `apply` without a successful `plan`.
- Do not pass `--force` to make a refusal go away. The refusal
  protects the existing tree; the right answer is to either move
  the existing tree aside or pick a different target.
- Do not skip the post-restore `mai-ship-validate`. The validator
  catches restore artifacts that the WAL replay cannot.
