# Runbook 01 — First Boot and Key Capture

**Profile:** `ship` only. For `local-dev`, see [BUILD.md](../BUILD.md).

## When to use

First time bringing up a freshly installed appliance, before any
client connects. Must be done by the operator (not the daemon).

## Preconditions

- `mai_*.deb` has been installed (`sudo apt install ./mai_*.deb`).
- `/etc/mai/profile.toml` exists with `profile.mode = "production"`.
- At least one trust anchor `.pub` file lives under
  `/etc/mai/trust-anchors/`.
- `/var/lib/mai/{vault,audit,trust,models,reports}` directories
  exist and are owned `mai:mai 0750` (postinstall does this).
- No prior `auth_keys.toml`; first boot only runs against an empty
  key store.

## Steps

1. Validate the profile before starting the service:
   ```bash
   sudo mai-ship-validate --profile /etc/mai/profile.toml
   ```
   Exit code 0 is required. Non-zero: read the report, fix the
   reported `PROD-*` check, re-run. Do not start `mai-api`.
2. Start the API once, attached, to capture the printed key:
   ```bash
   sudo -u mai mai-api --config /etc/mai/profile.toml 2>&1 | tee /tmp/first-boot.log
   ```
3. Watch stdout for the banner. The line `Key:  im-<64 hex>` is
   printed once and only once. Copy it immediately.
4. Stop the foreground process (`Ctrl+C`).
5. Persist the **hash** (not the key) to
   `/etc/mai/auth_keys.toml`. The banner prints both; the hash is
   what the server compares against on subsequent boots.
6. Enable the unit so the daemon takes over:
   ```bash
   sudo systemctl enable --now mai-api.service
   sudo systemctl status mai-api.service
   ```

## Verification

```bash
sudo systemctl is-active mai-api.service     # active
curl -fsS http://127.0.0.1:8420/v1/health/live
curl -fsS -H "X-IM-Auth-Token: im-<...>" \
     http://127.0.0.1:8420/v1/health/ready
```

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Validate exits non-zero | Profile or filesystem gap | Read the `PROD-*` line; consult `docs/SHIP-PROFILE.md` |
| No `Key:` banner | Server crashed before bind, or key store already seeded | Check `journalctl -u mai-api`; if seeded, use [02-rotate-api-key](02-rotate-api-key.md) |
| Bind fails | Port 8420/50051 occupied | Free the port; key is still valid, restart |
| Banner missed | Stdout not captured | Wipe the key store, restart from step 2 — never reuse a key whose plaintext was not captured |

## Do not

- Do not write the **key** (the `im-...` value) to
  `auth_keys.toml`. Only the hash goes there.
- Do not enable `mai-api.service` before capturing the key. The
  unit's `ExecStartPre` calls `mai-ship-validate` and will fail
  closed on an empty key store anyway.
- Do not skip validation. The validator is the only ship gate.
