# Authentication

Two modes today, three after BF-6 ships:

## 1. API key (current, recommended for local-dev)

The server validates an `X-IM-Auth-Token` header against keys stored
in its local vault.

```python
MaiClient(MaiClientConfig(api_key="im-..."))
```

Or via env / file:

```powershell
$env:MAI_API_KEY = "im-..."
```

```toml
# ~/.config/mai/config.toml
api_key = "im-..."
```

## 2. Legacy profile id (deprecated but still wired)

Falls back to `X-IM-Profile` when no API key is set.

```python
MaiClient(MaiClientConfig(profile_id="<uuid>"))
```

## 3. Trust Manifold claim (BF-6 — not yet shipped)

Once BF-6 lands, applications can exchange a cloud-issued claim for
a short-lived session token:

```python
# Pending BF-6
token = client.auth.exchange_token(claim)
```

Session 29 ships these methods as stubs that raise
`TrustNotProvisionedError`. Catch that exception and fall back to
API-key auth until BF-6 closes.

## Priority header

Every request carries an `X-IM-Priority` header (`low | normal |
high | critical`). Configure the default on the client:

```python
from mai import MaiClientConfig
MaiClientConfig(priority="high")
```

The scheduler uses this hint when admitting requests under load.

## Forward-compatibility note

When BF-6 lands, `client.trust.bundle_status()` will start returning
real `TrustBundleStatus` objects with `connectivity` set to one of:

- `connected` — fresh bundle, online verification working
- `degraded` — bundle valid, OpenBao unreachable, local verification only
- `stale` — bundle past expected refresh but still inside `expires_at`
- `expired` — bundle past `expires_at` — fail closed
- `air_gapped` — offline mode set at deploy time; no cloud expected

Applications that catch `TrustCacheStaleError` should prompt the
operator to refresh or accept degraded operation.
