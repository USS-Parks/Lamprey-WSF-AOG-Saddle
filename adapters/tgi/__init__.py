"""MAI TGI backend adapter."""
from .adapter import TgiAdapter
from .config import TgiConfig
from .client import TgiClient

__all__ = ["TgiAdapter", "TgiConfig", "TgiClient"]
