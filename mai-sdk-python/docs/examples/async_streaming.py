"""Async streaming example with concurrent embeddings."""

from __future__ import annotations

import asyncio
import sys

from mai import AsyncMaiClient, ChatMessage, MaiError


async def main() -> int:
    async with AsyncMaiClient.load() as client:
        try:
            # Concurrent embed + streaming chat
            embed_task = asyncio.create_task(
                client.embed("embed-1", "the quick brown fox"),
            )

            async for chunk in client.chat_stream(
                "qwen3-14b:Q4_K_M",
                [ChatMessage(role="user", content="Tell me a joke.")],
                max_tokens=200,
            ):
                delta = chunk.choices[0].get("delta", {}).get("content", "")
                if delta:
                    print(delta, end="", flush=True)
            print()

            embedding = await embed_task
            print(f"\nembedding dim: {len(embedding.data[0].embedding)}")
            return 0
        except MaiError as e:
            print(f"\nfailed: {e}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
