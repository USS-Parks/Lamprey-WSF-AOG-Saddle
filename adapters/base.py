"""MAI Adapter Base Class.

All backend adapters inherit from AdapterBase and implement its abstract
methods. Adapters are untrusted capsules in the Tock trust model: sandboxed,
crash-isolated, no direct hardware access.

Adapters self-register using the @mai_adapter decorator:

    @mai_adapter(name="ollama", version="1.0")
    class OllamaAdapter(AdapterBase):
        ...

Stub: full implementation in Session 08.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# Registration decorator stub
def mai_adapter(*, name: str, version: str):  # noqa: ANN201, ARG001
    """Register an adapter with the MAI AdapterManager."""
    def decorator(cls: type) -> type:
        cls._mai_adapter_name = name  # noqa: SLF001
        cls._mai_adapter_version = version  # noqa: SLF001
        return cls
    return decorator


class AdapterBase(ABC):
    """Abstract base class for MAI backend adapters."""

    @abstractmethod
    async def health_check(self) -> dict[str, object]:
        """Return adapter health status."""
        ...
