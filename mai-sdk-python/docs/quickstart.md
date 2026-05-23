# MAI SDK — Quickstart

Connect to a local MAI inference server, send a chat, stream tokens.

## Install

```powershell
pip install -e mai-sdk-python
```

That also installs the `mai` CLI on your PATH.

## Configure

Three ways, highest precedence wins:

1. Constructor arguments
2. Environment variables (`MAI_BASE_URL`, `MAI_API_KEY`, …)
3. TOML file (`$MAI_CONFIG` or `~/.config/mai/config.toml`)

```toml
# ~/.config/mai/config.toml
base_url = "http://localhost:8420/v1"
api_key  = "im-..."
timeout  = 60.0

[retry]
max_retries = 3
base_delay  = 1.0
jitter      = 0.25
```

## First request

```python
from mai import MaiClient, ChatMessage

with MaiClient.load() as client:                # picks up env + file
    response = client.chat(
        "qwen3-14b:Q4_K_M",
        [ChatMessage(role="user", content="Say hi")],
    )
    print(response.choices[0].message.content)
```

## Streaming

```python
with MaiClient.load() as client:
    for chunk in client.chat_stream(
        "qwen3-14b:Q4_K_M",
        [ChatMessage(role="user", content="Tell me a story")],
    ):
        delta = chunk.choices[0].get("delta", {}).get("content", "")
        print(delta, end="", flush=True)
```

## Async

```python
import asyncio
from mai import AsyncMaiClient, ChatMessage

async def main() -> None:
    async with AsyncMaiClient.load() as client:
        async for chunk in client.chat_stream(
            "qwen3-14b:Q4_K_M",
            [ChatMessage(role="user", content="Hello")],
        ):
            ...

asyncio.run(main())
```

## CLI

```powershell
mai health
mai chat "Tell me a joke" --model qwen3-14b:Q4_K_M
mai models list
mai benchmark qwen3-14b:Q4_K_M
mai power state
```

`MAI_BASE_URL` and `MAI_API_KEY` are read from the environment; pass
`--base-url`, `--api-key`, or `--config PATH` to override.

## Next steps

- [API reference](api-reference.md)
- [Streaming patterns](streaming.md)
- [Error handling](error-handling.md)
- [Authentication](authentication.md)
- Examples in [`examples/`](examples/)
