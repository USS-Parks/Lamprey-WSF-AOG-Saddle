"""Streaming example: print tokens as they arrive."""

from __future__ import annotations

import sys

from mai import ChatMessage, MaiClient, MaiError


def main() -> int:
    with MaiClient.load() as client:
        try:
            for chunk in client.chat_stream(
                "qwen3-14b:Q4_K_M",
                [ChatMessage(role="user", content="Write a short haiku about MAI.")],
                max_tokens=200,
            ):
                delta = chunk.choices[0].get("delta", {}).get("content", "")
                if delta:
                    print(delta, end="", flush=True)
            print()
            return 0
        except MaiError as e:
            print(f"\nstream failed: {e}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    sys.exit(main())
