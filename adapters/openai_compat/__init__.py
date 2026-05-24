"""MAI generic OpenAI-compatible local backend adapter (DOUGHERTY J-23)."""
from .adapter import OpenAICompatAdapter
from .client import OpenAICompatClient, OpenAICompatResponse, OpenAICompatStreamChunk
from .config import OpenAICompatConfig

__all__ = [
    "OpenAICompatAdapter",
    "OpenAICompatClient",
    "OpenAICompatConfig",
    "OpenAICompatResponse",
    "OpenAICompatStreamChunk",
]
