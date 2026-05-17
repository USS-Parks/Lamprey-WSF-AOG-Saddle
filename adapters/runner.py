"""MAI Adapter Runner: JSON-RPC subprocess protocol handler.

Spawned by AdapterManager as a subprocess. Reads JSON-RPC requests from stdin,
dispatches to the loaded adapter, writes responses to stdout.

Protocol: newline-delimited JSON matching Rust bridge.rs types.
  Request:  {"id": <int>, "method": <str>, "params": <obj>}
  Response: {"id": <int>, "result": <value>}
  Error:    {"id": <int>, "error": {"code": <str>, "detail": <str>}}
  Event:    {"event": <str>, "data": <obj>}  (adapter -> manager, no id)

Usage: python -m adapters.runner <adapter_module> <adapter_class>
  e.g. python -m adapters.runner adapters.ollama.adapter OllamaAdapter

Session 08 deliverable.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import sys
import time
import traceback
from typing import Any

from adapters.base import (
    AdapterBase,
    AdapterError,
    GenerationParams,
)

logger = logging.getLogger("mai.adapters.runner")

# Redirect logging to stderr so stdout is reserved for protocol messages.
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


class AdapterRunner:
    """JSON-RPC protocol handler for a single adapter subprocess.

    Reads requests from stdin, dispatches to the adapter instance,
    writes responses to stdout. All I/O is newline-delimited JSON.
    """

    def __init__(self, adapter: AdapterBase) -> None:
        self._adapter = adapter
        self._running = False
        self._start_time_ms = 0
        self._requests_served = 0
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def run(self) -> None:
        """Main event loop. Read requests, dispatch, write responses."""
        self._running = True
        self._start_time_ms = _now_ms()

        loop = asyncio.get_event_loop()
        self._reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self._reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        # stdout writer: use raw fd for binary writes
        transport, _ = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout,
        )
        self._writer = asyncio.StreamWriter(
            transport, protocol, self._reader, loop,
        )

        logger.info("Adapter runner started, reading from stdin")

        while self._running:
            try:
                line = await self._reader.readline()
                if not line:
                    # EOF - parent closed pipe
                    logger.info("stdin EOF, shutting down")
                    break

                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue

                request = json.loads(line_str)
                response = await self._dispatch(request)
                await self._send(response)

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON on stdin: {e}")
                # Can't send error response without a valid request id
                continue
            except asyncio.CancelledError:
                break
            except Exception:
                logger.error(f"Runner loop error: {traceback.format_exc()}")
                break

        # Attempt graceful shutdown
        try:
            await self._adapter.shutdown()
        except Exception:
            logger.error(f"Shutdown error: {traceback.format_exc()}")

    async def _dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        """Route a JSON-RPC request to the appropriate adapter method."""
        req_id = request.get("id", 0)
        method = request.get("method", "")
        params = request.get("params", {})

        try:
            result = await self._handle_method(method, params, req_id)
            self._requests_served += 1
            return {"id": req_id, "result": result}
        except AdapterError as e:
            return {
                "id": req_id,
                "error": {
                    "code": e.code,
                    "detail": e.detail or str(e),
                    "data": e.data,
                },
            }
        except Exception as e:
            logger.error(f"Unhandled error in {method}: {traceback.format_exc()}")
            return {
                "id": req_id,
                "error": {
                    "code": "InternalError",
                    "detail": str(e),
                },
            }

    async def _handle_method(
        self, method: str, params: dict[str, Any], req_id: int,
    ) -> Any:
        """Dispatch to the correct adapter method by name."""
        if method == "initialize":
            config = params.get("config", {})
            handle = await self._adapter.initialize(config, hil_handle=None)
            return {"handle": handle}

        elif method == "generate":
            prompt = params["prompt"]
            gen_params = _parse_generation_params(params.get("params", {}))
            stream_id = params.get("stream_id", req_id)

            # Stream tokens as events, then return final response
            async for token in self._adapter.generate(prompt, gen_params):
                await self._send_event("token", {
                    "stream_id": stream_id,
                    "text": token.text,
                    "logprob": token.logprob,
                    "index": token.index,
                    "is_end_of_text": token.is_end_of_text,
                })

            # Send stream end event
            await self._send_event("stream_end", {
                "stream_id": stream_id,
                "finish_reason": "stop",
            })
            return {"stream_id": stream_id, "completed": True}

        elif method == "generate_batch":
            prompts = params["prompts"]
            gen_params = _parse_generation_params(params.get("params", {}))
            results = await self._adapter.generate_batch(prompts, gen_params)
            return {
                "results": [
                    {
                        "text": r.text,
                        "tokens_generated": r.tokens_generated,
                        "finish_reason": r.finish_reason.value,
                    }
                    for r in results
                ],
            }

        elif method == "embed":
            texts = params["texts"]
            embeddings = await self._adapter.embed(texts)
            return {
                "embeddings": [
                    {"vector": e.vector, "input_tokens": e.input_tokens}
                    for e in embeddings
                ],
            }

        elif method == "health_check":
            status = await self._adapter.health_check()
            return {
                "status": {
                    "kind": status.kind.value,
                    "uptime_ms": status.uptime_ms,
                    "requests_served": status.requests_served,
                    "reason": status.reason,
                },
            }

        elif method == "capabilities":
            caps = self._adapter.capabilities()
            return {
                "capabilities": {
                    "max_context_window": caps.max_context_window,
                    "supported_quantizations": caps.supported_quantizations,
                    "supports_streaming": caps.supports_streaming,
                    "supports_batching": caps.supports_batching,
                    "supports_structured_output": caps.supports_structured_output,
                    "supports_vision": caps.supports_vision,
                    "supports_tool_calling": caps.supports_tool_calling,
                    "supports_continuous_batching": caps.supports_continuous_batching,
                    "supports_embedding": caps.supports_embedding,
                    "supports_hot_swap": caps.supports_hot_swap,
                    "backend_version": caps.backend_version,
                },
            }

        elif method == "shutdown":
            await self._adapter.shutdown()
            self._running = False
            return {"ok": True}

        elif method == "heartbeat":
            return {"timestamp_ms": _now_ms()}

        else:
            raise AdapterError(
                code="UnsupportedOperation",
                detail=f"Unknown method: {method}",
            )

    async def _send(self, message: dict[str, Any]) -> None:
        """Write a JSON message to stdout, newline-terminated."""
        if self._writer is None:
            return
        line = json.dumps(message, separators=(",", ":")) + "\n"
        self._writer.write(line.encode("utf-8"))
        await self._writer.drain()

    async def _send_event(self, event: str, data: dict[str, Any]) -> None:
        """Write an event (no id) to stdout."""
        await self._send({"event": event, "data": data})


def _parse_generation_params(raw: dict[str, Any]) -> GenerationParams:
    """Convert a dict to GenerationParams with defaults."""
    return GenerationParams(
        temperature=raw.get("temperature", 0.7),
        top_p=raw.get("top_p", 0.9),
        max_tokens=raw.get("max_tokens", 512),
        stop_sequences=raw.get("stop_sequences", []),
        structured_schema=raw.get("structured_schema"),
    )


def _now_ms() -> int:
    """Current time in milliseconds."""
    return int(time.time() * 1000)


def load_adapter(module_path: str, class_name: str) -> AdapterBase:
    """Dynamically load an adapter class from module path and class name."""
    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        logger.error(f"Failed to import adapter module '{module_path}': {e}")
        sys.exit(1)

    cls = getattr(module, class_name, None)
    if cls is None:
        logger.error(f"Class '{class_name}' not found in module '{module_path}'")
        sys.exit(1)

    if not issubclass(cls, AdapterBase):
        logger.error(f"'{class_name}' does not inherit from AdapterBase")
        sys.exit(1)

    return cls()


def main() -> None:
    """Entry point. Usage: python -m adapters.runner <module> <class>"""
    if len(sys.argv) != 3:
        print(
            "Usage: python -m adapters.runner <adapter_module> <adapter_class>",
            file=sys.stderr,
        )
        sys.exit(1)

    module_path = sys.argv[1]
    class_name = sys.argv[2]

    adapter = load_adapter(module_path, class_name)
    runner = AdapterRunner(adapter)

    try:
        asyncio.run(runner.run())
    except KeyboardInterrupt:
        logger.info("Runner interrupted")
    except Exception:
        logger.error(f"Runner fatal error: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
