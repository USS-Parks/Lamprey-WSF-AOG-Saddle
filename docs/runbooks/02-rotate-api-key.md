# Runbook 02 — Rotate API Key

## When to use

- Scheduled rotation (90-day default; site policy decides).
- Suspected compromise — assume compromise on any unexplained
  401/403 spike, any key found in unrelated logs, or any laptop
  loss / staff change.

## Preconditions

- Operator can reach the host with sudo + edit
  `/etc/mai/auth_keys.toml`.
- A non-rotating fallback key (e.g. `role = "admin"`) exists; do
  not rotate the last admin key in a single pass.

## Steps (additive rotation — preferred)

1. Generate a new key + hash with the same banner format:
   ```bash
   sudo -u mai mai-api keygen --role admin
   ```
   The CLI prints `Key:  im-<64 hex>` and `Hash: <64 hex>` to
   stdout. Capture the key now.
2. Append the new **hash** to `/etc/mai/auth_keys.toml` under the
   `[[keys]]` array. Leave the old entry in place.
3. Reload the service:
   ```bash
   sudo systemctl reload mai-api.service
   ```
   (`reload` re-reads `auth_keys.toml` without dropping in-flight
   requests; `restart` is also safe but interrupts SSE/WS.)
4. Hand the new key to clients. Confirm they switch.
5. Remove the **old** entry from `auth_keys.toml`. Reload again.
6. Confirm with `curl -H "X-IM-Auth-Token: <new>"`; confirm the
   old key now returns 401.

## Steps (emergency rotation — known compromise)

1. Generate the new key (step 1 above).
2. **Replace** the old `[[keys]]` entry (do not append).
3. Reload. The compromised key is now invalid immediately.
4. Force-disconnect any active SSE/WS clients:
   ```bash
   sudo systemctl restart mai-api.service
   ```
5. Trigger an audit chain export covering the suspect window and
   archive it before any retention boundary expires:
   ```bash
   sudo -u mai mai-admin backup create \
        --out /var/backups/mai/post-rotate-$(date +%Y%m%d-%H%M)
   ```

## Verification

```bash
curl -fsS -H "X-IM-Auth-Token: <new>" \
     http://127.0.0.1:8420/v1/health/ready
curl -i  -H "X-IM-Auth-Token: <old>" \
     http://127.0.0.1:8420/v1/health/ready    # expect 401
```

The rotation event is logged to the audit WAL as
`auth.key.rotated`. Pull the entry to confirm:

```bash
sudo -u mai mai-admin audit tail --grep auth.key
```

## Do not

- Do not store the plaintext key in `auth_keys.toml`; only the
  hash. The file is `root:mai 0640`, but hashes are still the
  contract.
- Do not run `systemctl restart` during a routine rotation —
  use `reload` to keep in-flight requests.
- Do not rotate every key at once. Always leave a working admin
  fallback unless the rotation is itself the emergency.
