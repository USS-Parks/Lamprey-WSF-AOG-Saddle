"""Generic OpenAI-compatible local adapter configuration.

Default values target a local OpenAI-compatible server (LM Studio,
LocalAI, FastChat, or an internal gateway). Loopback only; the operator
must opt in to any non-loopback host.

DOUGHERTY J-23.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OpenAICompatConfig:
    """Configuration for the generic OpenAI-compatible local adapter.

    The adapter targets ``/v1/models``, ``/v1/completions``,
    ``/v1/chat/completions``, and ``/v1/embeddings``. Streaming uses
    SSE on the chat-completions endpoint when ``supports_streaming``
    is left enabled.
    """

    # Connection
    host: str = "127.0.0.1"
    port: int = 1234
    scheme: str = "http"
    base_path: str = ""

    # Auth (optional bearer token; many local servers ignore it)
    api_key: str | None = None

    # Timeouts (separate budgets for streaming vs unary calls)
    timeout_ms: int = 30000
    stream_timeout_ms: int = 120000
    health_check_timeout_ms: int = 5000

    # Model defaults
    default_model: str = ""
    chat_model: str = ""
    completion_model: str = ""
    embedding_model: str = ""

    # Context budget (advertised through capabilities())
    context_size: int = 8192

    # Endpoint preference: "chat" or "completion" decides which path
    # the unary ``generate`` call uses. SSE streaming always goes
    # through ``/v1/chat/completions``.
    prefer_endpoint: str = "chat"

    # Feature toggles. Truthful capability reporting depends on these:
    # a backend that does not implement /v1/embeddings must be
    # configured with supports_embeddings=False so capabilities() and
    # embed() agree.
    supports_streaming: bool = True
    supports_embeddings: bool = False
    supports_tool_calling: bool = False
    supports_structured_output: bool = False

    # Retry budget for transient backend failures. Applied to unary
    # requests only; streaming is single-shot.
    max_retries: int = 0
    retry_backoff_ms: int = 100

    # Concurrency hint (used by callers; the adapter itself is async
    # and does not throttle in-process).
    max_concurrent_requests: int = 4

    # Backend version string surfaced through capabilities(). Set by
    # initialize() when the backend advertises one via /v1/models or a
    # header; defaults to "unknown".
    backend_version: str = "unknown"

    # Passthrough options for backends that accept extra fields on
    # their request body (e.g. LocalAI's "backend" key). The adapter
    # merges these into each request payload as-is.
    extra_request_fields: dict[str, object] = field(default_factory=dict)

    # Catch-all for unknown TOML keys; kept so config files can grow
    # without invalidating older adapters.
    extra_options: dict[str, object] = field(default_factory=dict)

    @property
    def base_url(self) -> str:
        """Construct the base URL for the OpenAI-compatible server."""
        path = self.base_path.rstrip("/")
        return f"{self.scheme}://{self.host}:{self.port}{path}"

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> OpenAICompatConfig:
        """Create a config from a TOML/JSON section.

        Unknown keys are preserved on ``extra_options`` so the surface
        stays backwards-compatible with newer config files.
        """
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        known = {k: v for k, v in data.items() if k in known_fields}
        extra = {k: v for k, v in data.items() if k not in known_fields}
        config = cls(**known)  # type: ignore[arg-type]
        config.extra_options.update(extra)
        return config
