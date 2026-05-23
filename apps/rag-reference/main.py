"""RAG Reference — text-only retrieval-augmented chat scaffold.

Pipeline:
    1. read text files from ``[ingest].docs_dir``
    2. split each into ``chunk_chars`` slices
    3. embed via SDK ``client.embed()``
    4. on query: embed query, cosine-rank chunks, take top-k
    5. ask chat model with retrieved chunks as system context
"""

from __future__ import annotations

import argparse
import math
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mai import ChatMessage, MaiClient, MaiClientConfig, MaiError

DEFAULT_CONFIG = Path(__file__).with_name("config.toml")


# ---------------------------------------------------------------------------
# In-memory vector store
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    doc_id: str
    text: str
    embedding: list[float]


class VectorStore:
    """Tiny in-memory store. Good enough for a reference scaffold."""

    def __init__(self) -> None:
        self._chunks: list[Chunk] = []

    def add(self, chunk: Chunk) -> None:
        self._chunks.append(chunk)

    def __len__(self) -> int:
        return len(self._chunks)

    def top_k(self, query_vec: list[float], k: int) -> list[tuple[float, Chunk]]:
        scored = [
            (cosine(query_vec, c.embedding), c) for c in self._chunks
        ]
        scored.sort(key=lambda t: t[0], reverse=True)
        return scored[:k]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_app_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def chunk_text(text: str, chunk_chars: int) -> list[str]:
    """Naive char-window splitter. Real apps want token-aware chunking."""
    text = text.strip()
    if not text:
        return []
    return [text[i:i + chunk_chars] for i in range(0, len(text), chunk_chars)]


def ingest(client: MaiClient, docs_dir: Path, *,
           embed_model: str, chunk_chars: int) -> VectorStore:
    """Read docs, chunk, embed, return populated store."""
    store = VectorStore()
    if not docs_dir.exists():
        return store

    inputs: list[tuple[str, str]] = []  # (doc_id, chunk_text)
    for path in sorted(docs_dir.iterdir()):
        if path.suffix.lower() not in {".txt", ".md"}:
            continue
        body = path.read_text(encoding="utf-8")
        for chunk in chunk_text(body, chunk_chars):
            inputs.append((path.name, chunk))

    if not inputs:
        return store

    # One batched embed call per doc for readability; real apps batch globally.
    by_doc: dict[str, list[str]] = {}
    for doc_id, ch in inputs:
        by_doc.setdefault(doc_id, []).append(ch)

    for doc_id, chunks in by_doc.items():
        resp = client.embed(embed_model, chunks)
        for data, text in zip(resp.data, chunks, strict=False):
            store.add(Chunk(doc_id=doc_id, text=text,
                            embedding=list(data.embedding)))
    return store


def answer(client: MaiClient, store: VectorStore, *,
           query: str, embed_model: str, chat_model: str,
           top_k: int, temperature: float, max_tokens: int) -> str:
    """Embed the query, retrieve, generate, return the final answer text."""
    q_resp = client.embed(embed_model, query)
    q_vec = list(q_resp.data[0].embedding)
    hits = store.top_k(q_vec, top_k)

    context = "\n\n".join(
        f"[{i + 1}] (from {c.doc_id})\n{c.text}"
        for i, (_, c) in enumerate(hits)
    )
    system = (
        "You answer questions using only the provided context.\n"
        "If the context does not contain the answer, say you don't know.\n\n"
        f"Context:\n{context}"
    )
    messages = [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=query),
    ]
    resp = client.chat(chat_model, messages,
                       temperature=temperature, max_tokens=max_tokens)
    return resp.choices[0].message.content


# ---------------------------------------------------------------------------
# Hook + entry point
# ---------------------------------------------------------------------------

def _make_client(sdk_config: MaiClientConfig) -> MaiClient:
    return MaiClient(sdk_config)


def run(query: str, *, config_path: Path = DEFAULT_CONFIG) -> int:
    cfg = load_app_config(config_path)
    ingest_cfg = cfg.get("ingest", {})
    retr_cfg = cfg.get("retrieval", {})
    gen_cfg = cfg.get("generation", {})
    client_overrides = cfg.get("client", {})

    sdk_config = MaiClientConfig.load(**client_overrides)
    with _make_client(sdk_config) as client:
        try:
            docs_dir = (config_path.parent / ingest_cfg.get("docs_dir", "sample_docs")).resolve()
            store = ingest(
                client, docs_dir,
                embed_model=ingest_cfg.get("embed_model", "embed-v1"),
                chunk_chars=int(ingest_cfg.get("chunk_chars", 800)),
            )
        except MaiError as e:
            print(f"ingest failed ({type(e).__name__}): {e}", file=sys.stderr)
            return 2

        if len(store) == 0:
            print(f"no documents found under {docs_dir}", file=sys.stderr)
            return 3

        try:
            text = answer(
                client, store, query=query,
                embed_model=ingest_cfg.get("embed_model", "embed-v1"),
                chat_model=gen_cfg.get("chat_model", "qwen3-14b:Q4_K_M"),
                top_k=int(retr_cfg.get("top_k", 3)),
                temperature=float(gen_cfg.get("temperature", 0.3)),
                max_tokens=int(gen_cfg.get("max_tokens", 512)),
            )
        except MaiError as e:
            print(f"answer failed ({type(e).__name__}): {e}", file=sys.stderr)
            return 4

        print(text)
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rag-reference",
        description="Retrieval-augmented chat over local text documents.",
    )
    parser.add_argument("query", help="user question to answer")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
                        help="path to config.toml")
    args = parser.parse_args(argv)
    return run(args.query, config_path=Path(args.config))


if __name__ == "__main__":
    sys.exit(main())
