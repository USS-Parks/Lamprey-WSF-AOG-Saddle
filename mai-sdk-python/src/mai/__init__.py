"""MAI Python SDK for IM-OS applications.

Provides typed client access to the MAI API (REST and gRPC) for
building L4-L5 applications on top of the Model Abstraction Interface.

Session 05 deliverable: type stubs and client skeleton.
Full implementation in Session 11.
"""

__version__ = "0.1.0"

from mai.client import AsyncMaiClient, MaiClient
from mai.types import (
    AdapterHealthEntry,
    AuditEntry,
    AuditLogResponse,
    CapabilityInfo,
    ChatChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    CompletionRequest,
    CompletionResponse,
    ContentSafetyLevel,
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    ErrorResponse,
    FinishReason,
    FunctionCallRequest,
    FunctionCallResponse,
    GpuHealthEntry,
    HardwareHealthResponse,
    HealthResponse,
    MaiError,
    ModelDetail,
    ModelObject,
    PowerStateResponse,
    ProfileObject,
    ProfilePermissions,
    ProfileRole,
    RequestPriority,
    StructuredRequest,
    StructuredResponse,
    Usage,
)

__all__ = [
    "AdapterHealthEntry",
    "AsyncMaiClient",
    # Audit types
    "AuditEntry",
    "AuditLogResponse",
    "CapabilityInfo",
    "ChatChoice",
    "ChatCompletionRequest",
    # Response types
    "ChatCompletionResponse",
    # Request types
    "ChatMessage",
    "CompletionRequest",
    "CompletionResponse",
    "ContentSafetyLevel",
    "EmbeddingData",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "ErrorResponse",
    "FinishReason",
    "FunctionCallRequest",
    "FunctionCallResponse",
    "GpuHealthEntry",
    "HardwareHealthResponse",
    # Health types
    "HealthResponse",
    # Client
    "MaiClient",
    # Error types
    "MaiError",
    "ModelDetail",
    # Model types
    "ModelObject",
    # Power types
    "PowerStateResponse",
    # Profile types
    "ProfileObject",
    "ProfilePermissions",
    "ProfileRole",
    # Enums
    "RequestPriority",
    "StructuredRequest",
    "StructuredResponse",
    "Usage",
]
