# Runbook 09 — Recover From a Failed Upgrade

## When to use

The upgrade flow in
[UPGRADE-ROLLBACK.md](../UPGRADE-ROLLBACK.md) covers the
happy path. Use this runbook when:

- `apt install ./mai_<new>.deb` exited non-zero.
- The new package installed cleanly but `mai-ship-validate`
  exits non-zero on the new layout.
- `mai-api.service` enters `failed` state after upgrade and
  cannot be coaxed to `active` by config edits.
- The dashboard or compliance dashboard fails to load with the
  new wheels.

## Preconditions

- A pre-upgrade backup exists and verifies clean
  ([07-back-up-node](07-back-up-node.md)). Without a verified
  pre-upgrade backup, this is no longer a "failed upgrade
  recovery" — it is an incident response per
  [INCIDENT-RESPONSE.md](../INCIDENT-RESPONSE.md).

## Decision tree

1. If the install **never wrote** any new state under
   `/var/lib/mai/`: re-install the previous `.deb` and stop —
   no restore needed.
2. If the daemon **started** under the new package and wrote
   even one audit entry: the WAL has migrated forward. Use
   the restore path below.
3. If the new package **did not start at all** but `apt` left
   `/etc/mai/` in a half-migrated state: re-install the old
   `.deb` first to restore `/etc/mai/` conffile defaults, then
   reconcile the operator's edits from the pre-upgrade backup.

## Steps — full restore path

1. Stop the failing service:
   ```bash
   sudo systemctl stop mai-api.service mai-dashboard.service \
        mai-adapter-manager.service
   ```
2. Re-install the previous `.deb`:
   ```bash
   sudo apt install --reinstall ./mai_<old-version>_amd64.deb
   ```
   `dpkg` will warn about downgrade; this is expected. Confirm.
3. Move the corrupted state aside (do not delete — it is
   evidence and may be the only copy of post-upgrade WAL
   entries):
   ```bash
   sudo mv /var/lib/mai /var/lib/mai.failed-upgrade-$(date +%Y%m%d-%H%M)
   sudo install -d -o mai -g mai -m 0750 /var/lib/mai
   ```
4. Restore from the pre-upgrade backup
   ([08-restore-node](08-restore-node.md), steps 1–4).
5. Start the service, verify health.
6. **Do not delete** the `/var/lib/mai.failed-upgrade-*` tree
   until the post-mortem is written and any audit entries it
   carries that should survive the rollback have been
   reconciled into the live chain (operator decision; document
   the reasoning).

## Steps — reconfigure-only path

If only `/etc/mai/` drifted (new conffile defaults, operator
edits lost):

```bash
sudo cp -a /var/backups/mai/<pre-upgrade>/etc/. /etc/mai/
sudo chown -R root:mai /etc/mai
sudo find /etc/mai -type f -exec chmod 0640 {} +
sudo mai-ship-validate --profile /etc/mai/profile.toml
sudo systemctl start mai-api.service
```

## What does NOT solve a failed upgrade

- `apt --fix-broken install` — masks the actual failure and
  often re-applies the broken upgrade.
- `dpkg --force-overwrite` — wipes operator edits in
  `/etc/mai/`. Never on this fleet.
- `systemctl reset-failed` — clears the systemd flag without
  fixing the cause. Useful **after** the cause is fixed.

## Do not

- Do not delete the failed state dir until reconciled.
- Do not skip the post-rollback `mai-ship-validate`; the new
  package may have installed binaries that the old config does
  not expect.
- Do not consider the rollback complete until a fresh backup of
  the recovered node has been taken and verified.
