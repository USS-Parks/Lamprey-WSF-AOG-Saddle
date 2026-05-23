"""MAI SDK command-line tool.

Installed as ``mai`` via ``[project.scripts]``. Commands::

    mai health [--base-url URL]
    mai chat "prompt"  [--model M] [--system PROMPT] [--no-stream]
    mai models list
    mai models load   MODEL_ID
    mai models unload MODEL_ID
    mai benchmark     MODEL_ID
    mai power state

Auth, base URL and timeouts come from env vars (see :mod:`mai.config`)
or a config file (``--config PATH`` / ``MAI_CONFIG``).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from mai.client import MaiClient
from mai.config import MaiClientConfig
from mai.errors import (
    AuthenticationError,
    MaiError,
    NotFoundError,
    RateLimitError,
)
from mai.errors import (
    ConnectionError as MaiConnectionError,
)
from mai.errors import (
    PermissionError as MaiPermissionError,
)
from mai.types import ChatMessage

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_AUTH = 3
EXIT_PERM = 4
EXIT_NOTFOUND = 5
EXIT_RATELIMIT = 6
EXIT_CONNECT = 7
EXIT_SERVER = 8


def _build_client(args: argparse.Namespace) -> MaiClient:
    overrides: dict[str, Any] = {}
    if args.base_url is not None:
        overrides["base_url"] = args.base_url
    if args.api_key is not None:
        overrides["api_key"] = args.api_key
    cfg = MaiClientConfig.load(args.config, **overrides)
    return MaiClient(cfg)


def _print_err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _exit_for(err: MaiError) -> int:
    if isinstance(err, AuthenticationError):
        return EXIT_AUTH
    if isinstance(err, MaiPermissionError):
        return EXIT_PERM
    if isinstance(err, NotFoundError):
        return EXIT_NOTFOUND
    if isinstance(err, RateLimitError):
        return EXIT_RATELIMIT
    if isinstance(err, MaiConnectionError):
        return EXIT_CONNECT
    return EXIT_SERVER


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def cmd_health(args: argparse.Namespace) -> int:
    with _build_client(args) as client:
        try:
            h = client.health()
        except MaiError as e:
            _print_err(f"health failed: {e}")
            return _exit_for(e)
        if args.json:
            print(h.model_dump_json(indent=2))
        else:
            print(f"status: {h.status}")
            print(f"power_state: {h.power_state.value}")
            print(f"air_gap_verified: {h.air_gap_verified}")
            print(f"uptime_seconds: {h.uptime_seconds}")
        return EXIT_OK


def cmd_chat(args: argparse.Namespace) -> int:
    messages: list[ChatMessage] = []
    if args.system:
        messages.append(ChatMessage(role="system", content=args.system))
    messages.append(ChatMessage(role="user", content=args.prompt))

    with _build_client(args) as client:
        try:
            if args.no_stream:
                resp = client.chat(
                    args.model, messages,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                )
                if args.json:
                    print(resp.model_dump_json(indent=2))
                else:
                    print(resp.choices[0].message.content)
                return EXIT_OK

            for chunk in client.chat_stream(
                args.model, messages,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
            ):
                delta = chunk.choices[0].get("delta", {}) if chunk.choices else {}
                content = delta.get("content", "")
                if content:
                    print(content, end="", flush=True)
            print()
            return EXIT_OK
        except MaiError as e:
            _print_err(f"\nchat failed: {e}")
            return _exit_for(e)


def cmd_models_list(args: argparse.Namespace) -> int:
    with _build_client(args) as client:
        try:
            models = client.models.list()
        except MaiError as e:
            _print_err(f"models list failed: {e}")
            return _exit_for(e)
        if args.json:
            print(json.dumps([m.model_dump(mode="json") for m in models], indent=2))
        else:
            for m in models:
                size_gib = m.size_bytes / (1024**3)
                print(f"{m.id:<40} {m.status.value:<12} {size_gib:6.2f} GiB  {m.format.value}")
        return EXIT_OK


def cmd_models_load(args: argparse.Namespace) -> int:
    with _build_client(args) as client:
        try:
            r = client.models.load(args.model_id)
        except MaiError as e:
            _print_err(f"load failed: {e}")
            return _exit_for(e)
        print(f"loaded: {r.model_id} status={r.status.value} "
              f"adapter={r.adapter_id or '-'} load_time_ms={r.load_time_ms}")
        return EXIT_OK


def cmd_models_unload(args: argparse.Namespace) -> int:
    with _build_client(args) as client:
        try:
            r = client.models.unload(args.model_id)
        except MaiError as e:
            _print_err(f"unload failed: {e}")
            return _exit_for(e)
        print(f"unloaded: {r.model_id} status={r.status.value} "
              f"freed={r.vram_freed_bytes} bytes")
        return EXIT_OK


def cmd_benchmark(args: argparse.Namespace) -> int:
    with _build_client(args) as client:
        try:
            r = client.models.benchmark(args.model_id)
        except MaiError as e:
            _print_err(f"benchmark failed: {e}")
            return _exit_for(e)
        if args.json:
            print(r.model_dump_json(indent=2))
        else:
            print(f"model: {r.model_id}")
            print(f"throughput: {r.tokens_per_second:.1f} tok/s")
            print(f"first_token_latency_ms: {r.first_token_latency_ms:.1f}")
            print(f"p50/p95/p99 latency ms: "
                  f"{r.p50_latency_ms:.1f}/{r.p95_latency_ms:.1f}/{r.p99_latency_ms:.1f}")
        return EXIT_OK


def cmd_power_state(args: argparse.Namespace) -> int:
    with _build_client(args) as client:
        try:
            p = client.power.get_state()
        except MaiError as e:
            _print_err(f"power state failed: {e}")
            return _exit_for(e)
        if args.json:
            print(p.model_dump_json(indent=2))
        else:
            print(f"state: {p.state.value}")
            print(f"estimated_power_watts: {p.estimated_power_watts:.1f}")
            print(f"promotion_available: {p.promotion_available}")
        return EXIT_OK


# ---------------------------------------------------------------------------
# Argparse wiring
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mai",
        description="MAI CLI — talk to a local MAI inference server",
    )
    parser.add_argument("--base-url", help="override MAI base URL")
    parser.add_argument("--api-key", help="override API key")
    parser.add_argument("--config", help="path to TOML config file")
    parser.add_argument("--json", action="store_true", help="emit JSON output")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_health = sub.add_parser("health", help="check server health")
    p_health.set_defaults(func=cmd_health)

    p_chat = sub.add_parser("chat", help="send a chat completion")
    p_chat.add_argument("prompt", help="user message")
    p_chat.add_argument("--model", default="default", help="model id")
    p_chat.add_argument("--system", help="system prompt")
    p_chat.add_argument("--temperature", type=float, default=0.7)
    p_chat.add_argument("--max-tokens", type=int, default=2048)
    p_chat.add_argument("--no-stream", action="store_true",
                        help="disable streaming output")
    p_chat.set_defaults(func=cmd_chat)

    p_models = sub.add_parser("models", help="model management")
    models_sub = p_models.add_subparsers(dest="models_cmd", required=True)

    p_ml = models_sub.add_parser("list", help="list models")
    p_ml.set_defaults(func=cmd_models_list)

    p_load = models_sub.add_parser("load", help="load a model into VRAM")
    p_load.add_argument("model_id")
    p_load.set_defaults(func=cmd_models_load)

    p_unload = models_sub.add_parser("unload", help="unload a model from VRAM")
    p_unload.add_argument("model_id")
    p_unload.set_defaults(func=cmd_models_unload)

    p_bench = sub.add_parser("benchmark", help="benchmark a model")
    p_bench.add_argument("model_id")
    p_bench.set_defaults(func=cmd_benchmark)

    p_power = sub.add_parser("power", help="power state inspection")
    power_sub = p_power.add_subparsers(dest="power_cmd", required=True)
    p_pstate = power_sub.add_parser("state", help="show current power state")
    p_pstate.set_defaults(func=cmd_power_state)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return EXIT_USAGE
    return int(func(args))


if __name__ == "__main__":
    sys.exit(main())
