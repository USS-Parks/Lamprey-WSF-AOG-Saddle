# Streaming

The SDK streams chat completions and text completions over
Server-Sent Events. The server sends `data: <json>` lines followed
by `data: [DONE]` to terminate.

## Sync

```python
from mai import MaiClient, ChatMessage

with MaiClient.load() as client:
    for chunk in client.chat_stream(
        "qwen3-14b:Q4_K_M",
        [ChatMessage(role="user", content="Tell me a haiku")],
        max_tokens=100,
    ):
        delta = chunk.choices[0].get("delta", {}).get("content", "")
        if delta:
            print(delta, end="", flush=True)
    print()
```

## Async

```python
async with AsyncMaiClient.load() as client:
    async for chunk in client.chat_stream(
        "qwen3-14b:Q4_K_M",
        [ChatMessage(role="user", content="Hello")],
    ):
        delta = chunk.choices[0].get("delta", {}).get("content", "")
        ...
```

## Cancellation

Sync: stop iterating (the `with` block on `_http.stream` releases the
connection). Async: cancel the task or break out of the `async for`.

## Errors during a stream

If the server returns a non-2xx status before the first event, the
SDK reads the body and raises the appropriate `MaiError` subclass
(`AuthenticationError`, `RateLimitError`, etc). Errors that occur
mid-stream are sent as terminating `error` events; the SDK passes
the parsed chunk through and lets the application decide.

## Timeouts

`stream_timeout` (default 300 s) caps the whole streaming connection.
Set it explicitly when generating long responses:

```python
MaiClientConfig(stream_timeout=900.0)
```

## stream_completions vs chat_stream

`stream_completions(model, prompt)` wraps the prompt in a single
user message and dispatches to `chat_stream`. The server serves
both `/v1/chat/completions` and `/v1/completions` from the same
handler, so completions are delivered as `chat.completion.chunk`
objects.
