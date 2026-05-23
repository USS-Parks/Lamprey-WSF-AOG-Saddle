# Local Secure Inference

Session 30 reference scaffold #1. Smallest end-to-end use of the MAI
SDK against a local server: pick a model, send a chat, stream the
reply, optionally print scheduler metrics.

## What it demonstrates

- `MaiClientConfig.load()` precedence — overrides ▸ env ▸ file ▸ defaults
- `client.health_check()` reachability probe
- `client.models.list()` + capability filter (chat-capable)
- `client.chat_stream()` SSE streaming
- `client.scheduler.metrics()` for an observability footer

## Run

```powershell
$env:MAI_API_KEY = "im-..."
python apps/local-secure-inference/main.py "Tell me a joke."
```

## Configure

Edit [`config.toml`](config.toml). All keys are optional. The most
common edit is setting an explicit `[chat] model = "qwen3-14b:Q4_K_M"`
instead of `"auto"`.

## Tests

```powershell
pytest apps/local-secure-inference/tests/
```

- `test_smoke.py` — starts, hits a mocked health endpoint, lists
  models, sends one chat. Verifies the scaffold loads its config.
- `test_integration.py` — full pick-model + streaming round trip
  using `httpx.MockTransport` for the server.

## Extending

This scaffold is meant to be copied. Likely next steps:
- multi-turn history (track `messages` across `run()` calls)
- profile selection (pass `profile_id` via `MaiClientConfig`)
- power-state-aware routing (`client.power.get_state()`, drop to
  short-prompt mode when Sentinel)
