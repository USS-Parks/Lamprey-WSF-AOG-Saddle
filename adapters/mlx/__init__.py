"""MAI MLX backend adapter — Apple Silicon local inference via mlx-lm."""
from .adapter import MLXAdapter
from .client import MLXClient
from .config import MLXConfig

__all__ = ["MLXAdapter", "MLXClient", "MLXConfig"]
