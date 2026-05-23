"""Local Secure Inference — minimal authenticated chat scaffold.

Run::

    python apps/local-secure-inference/main.py "Tell me a joke."

Uses the MAI SDK's ``MaiClient.load()`` so config flows from
constructor > env > $MAI_CONFIG > defaults. Streams the response
and (optionally) prints scheduler metrics under it.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path
from typing import Any

from mai import ChatMessage, MaiClient, MaiClientConfig, MaiError

DEFAULT_CONFIG = Path(__file__).with_name("config.toml")


def load_app_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    """Read the scaffold's TOML file. Missing file -> defaults."""
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def pick_model(client: MaiClient, configured: str) -> str:
    """Resolve "auto" to the first chat-capable model; else validate
    that the configured id exists. Returns the resolved id."""
    models = client.models.list()
    if configured == "auto":
        for m in models:
            if m.capabilities.chat:
                return m.id
        raise RuntimeError("no chat-capable model available on server")
    for m in models:
        if m.id == configured:
            return m.id
    raise RuntimeError(
        f"configured model '{configured}' not in server inventory "
        f"(available: {[m.id for m in models]})",
    )


def _make_client(sdk_config: MaiClientConfig) -> MaiClient:
    """Indirection hook so tests can inject a MockTransport-backed client."""
    return MaiClient(sdk_config)


def run(prompt: str, *, config_path: Path = DEFAULT_CONFIG,
        no_stream: bool = False) -> int:
    """Send one prompt and stream the reply. Returns process exit code."""
    cfg = load_app_config(config_path)
    chat_cfg = cfg.get("chat", {})
    ui_cfg = cfg.get("ui", {})

    # Build the SDK client. Honor [client] overrides if present.
    client_overrides = cfg.get("client", {})
    sdk_config = MaiClientConfig.load(**client_overrides)

    with _make_client(sdk_config) as client:
        if not client.health_check():
            print("MAI server unreachable; check MAI_BASE_URL", file=sys.stderr)
            return 1

        try:
            model = pick_model(client, chat_cfg.get("model", "auto"))
        except RuntimeError as e:
            print(f"model selection failed: {e}", file=sys.stderr)
            return 2

        messages = [ChatMessage(role="user", content=prompt)]
        temperature = float(chat_cfg.get("temperature", 0.7))
        max_tokens = int(chat_cfg.get("max_tokens", 512))

        try:
            if no_stream:
                resp = client.chat(
                    model, messages,
                    temperature=temperature, max_tokens=max_tokens,
                )
                print(resp.choices[0].message.content)
            else:
                for chunk in client.chat_stream(
                    model, messages,
                    temperature=temperature, max_tokens=max_tokens,
                ):
                    delta = chunk.choices[0].get("delta", {}).get("content", "")
                    if delta:
                        print(delta, end="", flush=True)
                print()
        except MaiError as e:
            print(f"\nchat failed ({type(e).__name__}): {e}", file=sys.stderr)
            return 3

        if ui_cfg.get("show_metrics", False):
            try:
                metrics = client.scheduler.metrics()
                print(
                    f"\n--- scheduler: queue={metrics.queue_depth} "
                    f"active={metrics.active_requests} "
                    f"p95_wait_ms={metrics.p95_wait_ms:.1f} ---",
                    file=sys.stderr,
                )
            except MaiError:
                pass  # metrics are advisory; don't fail the request
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="local-secure-inference",
        description="Send a single chat prompt to a local MAI server.",
    )
    parser.add_argument("prompt", help="user prompt to send")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
                        help="path to config.toml")
    parser.add_argument("--no-stream", action="store_true",
                        help="disable streaming")
    args = parser.parse_args(argv)
    return run(args.prompt, config_path=Path(args.config),
               no_stream=args.no_stream)


if __name__ == "__main__":
    sys.exit(main())
