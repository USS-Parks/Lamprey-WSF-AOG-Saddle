# RAG Reference

Session 30 reference scaffold #2. Minimal retrieval-augmented chat:
local text docs → embed → cosine top-k → chat with retrieved context.

## What it demonstrates

- Batched embedding via `client.embed(model, [chunks])`
- In-memory `VectorStore` with cosine similarity ranking
- Two-stage SDK use (embed pipeline + chat with system context)
- Clean per-stage error handling distinguishing ingest vs. answer failures

## Run

```powershell
mkdir apps/rag-reference/sample_docs
"The MAI server runs locally on port 8420." | Out-File -Encoding utf8 apps/rag-reference/sample_docs/about.md

python apps/rag-reference/main.py "What port does MAI use?"
```

## Configure

Edit [`config.toml`](config.toml). The defaults assume:
- An `embed-v1` model that the server reports with `capabilities.embedding = true`.
- A `qwen3-14b:Q4_K_M` chat model.

Change `[ingest] docs_dir` to point at your own corpus.

## Tests

```powershell
pytest apps/rag-reference/tests/
```

- `test_smoke.py` — VectorStore cosine math, chunking helper, end-to-end run with mocked server.
- `test_integration.py` — top-k ranking quality with three competing chunks.

## Limitations (intentional, for a scaffold)

- **In-memory only** — no persistence between runs. Swap in `mai-vault::VectorStore` once exposed over HTTP (BF-6 / S34 work).
- **Naive chunker** — character-window, not token-aware. Real apps want sentence/paragraph segmentation.
- **No reranker** — top-k is direct cosine; production RAG benefits from a second-stage reranker.
- **No streaming** — final answer is generated in one shot for simplicity.
