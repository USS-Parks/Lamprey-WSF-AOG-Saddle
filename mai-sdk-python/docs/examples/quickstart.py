"""Minimum end-to-end example: health check + one chat."""

from __future__ import annotations

import sys

from mai import ChatMessage, MaiClient, MaiError


def main() -> int:
    with MaiClient.load() as client:
        if not client.health_check():
            print("MAI server unreachable", file=sys.stderr)
            return 1

        try:
            response = client.chat(
                "qwen3-14b:Q4_K_M",
                [ChatMessage(role="user", content="Say hi in five words.")],
                max_tokens=32,
            )
        except MaiError as e:
            print(f"chat failed: {e}", file=sys.stderr)
            return 2

        print(response.choices[0].message.content)
        return 0


if __name__ == "__main__":
    sys.exit(main())
