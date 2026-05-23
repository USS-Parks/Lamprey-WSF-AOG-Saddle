"""Sync API namespaces for ``MaiClient``.

Each namespace class wraps a thin slice of the REST API (models,
power, scheduler, …) and is instantiated once per client. They
delegate all transport to the client's ``_request_with_retry`` so
retry/auth/error mapping stays in one place.

Async equivalents live in :mod:`mai.async_client` (AsyncMaiClient
attaches its own namespace instances bound to its async transport).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mai.errors import MaiError
from mai.types import (
    AirgapStatusResponse,
    AuditLogResponse,
    BenchmarkResult,
    HardwareHealthResponse,
    InstanceHealthResponse,
    InstanceMetricsResponse,
    ModelDetail,
    ModelDiscoverResponse,
    ModelInstallResponse,
    ModelLoadResponse,
    ModelObject,
    ModelRemoveResponse,
    ModelUnloadResponse,
    PowerStateResponse,
    PowerTransitionRequest,
    PowerTransitionResponse,
    ProfileObject,
    RevocationStatusResponse,
    SchedulerAnomaliesResponse,
    SchedulerMetricsResponse,
    SystemHealthResponse,
    TrustBundleStatus,
    TrustClaim,
    UpdateCheckResponse,
    UpdateStatusResponse,
)

if TYPE_CHECKING:
    from mai.client import MaiClient


# ---------------------------------------------------------------------------
# Trust namespace error (BF-6 stub)
# ---------------------------------------------------------------------------

class TrustNotProvisionedError(MaiError):
    """Raised when a trust API is called but the server has no trust bridge.

    Session 29 ships the SDK trust surface as a stub. BF-6 wires the
    real OpenBao Trust Manifold backend in a later session. Applications
    that catch this can fall back to API-key auth.
    """


_TRUST_STUB_MESSAGE = (
    "trust API is not provisioned in this build (BF-6 pending). "
    "Configure a Trust Manifold backend or use API-key auth."
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Models:
    """Model management namespace (``client.models``)."""

    def __init__(self, client: MaiClient) -> None:
        self._client = client

    def list(self, **filters: Any) -> list[ModelObject]:
        """GET /v1/models."""
        resp = self._client._request_with_retry("GET", "/models", params=filters)
        data = resp.json()
        return [ModelObject.model_validate(m) for m in data.get("data", [])]

    def get(self, model_id: str) -> ModelDetail:
        """GET /v1/models/{model_id}."""
        resp = self._client._request_with_retry("GET", f"/models/{model_id}")
        return ModelDetail.model_validate(resp.json())

    def load(self, model_id: str) -> ModelLoadResponse:
        """POST /v1/models/{model_id}/load."""
        resp = self._client._request_with_retry("POST", f"/models/{model_id}/load")
        return ModelLoadResponse.model_validate(resp.json())

    def unload(self, model_id: str) -> ModelUnloadResponse:
        """POST /v1/models/{model_id}/unload."""
        resp = self._client._request_with_retry("POST", f"/models/{model_id}/unload")
        return ModelUnloadResponse.model_validate(resp.json())

    def benchmark(self, model_id: str, **opts: Any) -> BenchmarkResult:
        """POST /v1/models/{model_id}/benchmark — kick off / return result."""
        resp = self._client._request_with_retry(
            "POST", f"/models/{model_id}/benchmark", json=opts or None,
        )
        return BenchmarkResult.model_validate(resp.json())

    def get_benchmark(self, model_id: str) -> BenchmarkResult:
        """GET /v1/models/{model_id}/benchmark — most recent benchmark."""
        resp = self._client._request_with_retry(
            "GET", f"/models/{model_id}/benchmark",
        )
        return BenchmarkResult.model_validate(resp.json())

    def discover(self, path: str | None = None) -> ModelDiscoverResponse:
        """POST /v1/models/discover — scan a path for installable packages."""
        body = {"path": path} if path else {}
        resp = self._client._request_with_retry(
            "POST", "/models/discover", json=body,
        )
        return ModelDiscoverResponse.model_validate(resp.json())

    def install(
        self, package_bytes: bytes, *, filename: str = "package.mpkg",
    ) -> ModelInstallResponse:
        """POST /v1/models/install — upload a package (multipart)."""
        files = {"package": (filename, package_bytes, "application/octet-stream")}
        resp = self._client._request_with_retry(
            "POST", "/models/install", files=files,
        )
        return ModelInstallResponse.model_validate(resp.json())

    def remove(self, model_id: str) -> ModelRemoveResponse:
        """POST /v1/models/{model_id}/remove (DELETE also accepted)."""
        resp = self._client._request_with_retry(
            "POST", f"/models/{model_id}/remove",
        )
        return ModelRemoveResponse.model_validate(resp.json())


# ---------------------------------------------------------------------------
# Power
# ---------------------------------------------------------------------------

class Power:
    """Power management namespace (``client.power``)."""

    def __init__(self, client: MaiClient) -> None:
        self._client = client

    def get_state(self) -> PowerStateResponse:
        """GET /v1/power/state."""
        resp = self._client._request_with_retry("GET", "/power/state")
        return PowerStateResponse.model_validate(resp.json())

    def transition(
        self, request: PowerTransitionRequest,
    ) -> PowerTransitionResponse:
        """POST /v1/power/transition."""
        resp = self._client._request_with_retry(
            "POST", "/power/transition", json=request.model_dump(),
        )
        return PowerTransitionResponse.model_validate(resp.json())


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

class System:
    """System status namespace (``client.system``)."""

    def __init__(self, client: MaiClient) -> None:
        self._client = client

    def airgap(self) -> AirgapStatusResponse:
        """GET /v1/system/airgap."""
        resp = self._client._request_with_retry("GET", "/system/airgap")
        return AirgapStatusResponse.model_validate(resp.json())

    def system_health(self) -> SystemHealthResponse:
        """GET /v1/health/system."""
        resp = self._client._request_with_retry("GET", "/health/system")
        return SystemHealthResponse.model_validate(resp.json())

    def hardware_health(self) -> HardwareHealthResponse:
        """GET /v1/health/hardware."""
        resp = self._client._request_with_retry("GET", "/health/hardware")
        return HardwareHealthResponse.model_validate(resp.json())


# ---------------------------------------------------------------------------
# Scheduler / telemetry
# ---------------------------------------------------------------------------

class Scheduler:
    """Scheduler metrics namespace (``client.scheduler``)."""

    def __init__(self, client: MaiClient) -> None:
        self._client = client

    def metrics(self) -> SchedulerMetricsResponse:
        """GET /v1/scheduler/metrics."""
        resp = self._client._request_with_retry("GET", "/scheduler/metrics")
        return SchedulerMetricsResponse.model_validate(resp.json())

    def instance_metrics(self, instance_id: str) -> InstanceMetricsResponse:
        """GET /v1/scheduler/instances/{id}/metrics."""
        resp = self._client._request_with_retry(
            "GET", f"/scheduler/instances/{instance_id}/metrics",
        )
        return InstanceMetricsResponse.model_validate(resp.json())

    def instance_health(self, instance_id: str) -> InstanceHealthResponse:
        """GET /v1/scheduler/instances/{id}/health."""
        resp = self._client._request_with_retry(
            "GET", f"/scheduler/instances/{instance_id}/health",
        )
        return InstanceHealthResponse.model_validate(resp.json())

    def anomalies(self) -> SchedulerAnomaliesResponse:
        """GET /v1/scheduler/anomalies."""
        resp = self._client._request_with_retry("GET", "/scheduler/anomalies")
        return SchedulerAnomaliesResponse.model_validate(resp.json())


# ---------------------------------------------------------------------------
# Updates (OTA)
# ---------------------------------------------------------------------------

class Updates:
    """Update channel namespace (``client.updates``)."""

    def __init__(self, client: MaiClient) -> None:
        self._client = client

    def check(self) -> UpdateCheckResponse:
        """GET /v1/updates/check."""
        resp = self._client._request_with_retry("GET", "/updates/check")
        return UpdateCheckResponse.model_validate(resp.json())

    def download(self, component: str, target_version: str) -> dict[str, Any]:
        """POST /v1/updates/download."""
        resp = self._client._request_with_retry(
            "POST", "/updates/download",
            json={"component": component, "target_version": target_version},
        )
        return resp.json()  # type: ignore[no-any-return]

    def status(self) -> UpdateStatusResponse:
        """GET /v1/updates/status."""
        resp = self._client._request_with_retry("GET", "/updates/status")
        return UpdateStatusResponse.model_validate(resp.json())


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

class Admin:
    """Admin operations namespace (``client.admin``).

    All methods require admin-class credentials. The server enforces
    permissions; failures surface as ``PermissionError``.
    """

    def __init__(self, client: MaiClient) -> None:
        self._client = client

    def list_profiles(self) -> list[ProfileObject]:
        """GET /v1/profiles."""
        resp = self._client._request_with_retry("GET", "/profiles")
        data = resp.json()
        return [ProfileObject.model_validate(p) for p in data.get("data", [])]

    def get_profile(self, profile_id: str) -> ProfileObject:
        """GET /v1/profiles/{profile_id}."""
        resp = self._client._request_with_retry("GET", f"/profiles/{profile_id}")
        return ProfileObject.model_validate(resp.json())

    def audit_log(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        since_unix: int | None = None,
    ) -> AuditLogResponse:
        """GET /v1/audit/log."""
        params: dict[str, Any] = {"offset": offset, "limit": limit}
        if since_unix is not None:
            params["since"] = since_unix
        resp = self._client._request_with_retry(
            "GET", "/audit/log", params=params,
        )
        return AuditLogResponse.model_validate(resp.json())

    def adapters(self) -> dict[str, Any]:
        """GET /v1/adapters — raw adapter inventory."""
        resp = self._client._request_with_retry("GET", "/adapters")
        return resp.json()  # type: ignore[no-any-return]

    def registry(self) -> dict[str, Any]:
        """GET /v1/registry — raw registry manifest."""
        resp = self._client._request_with_retry("GET", "/registry")
        return resp.json()  # type: ignore[no-any-return]

    def registry_scan(self) -> dict[str, Any]:
        """POST /v1/registry/scan — trigger a rescan."""
        resp = self._client._request_with_retry("POST", "/registry/scan")
        return resp.json()  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Auth (Session 29 placeholder — server endpoint pending)
# ---------------------------------------------------------------------------

class Auth:
    """Auth/token operations (``client.auth``).

    Stubbed in Session 29. The ``/v1/auth/exchange_token`` endpoint is
    declared in the plan but not yet on the server — calls raise a
    clear error so applications can detect it.
    """

    def __init__(self, client: MaiClient) -> None:
        self._client = client

    def exchange_token(self, claim: TrustClaim) -> str:  # noqa: ARG002
        """POST /v1/auth/exchange_token — trade a trust claim for a session token.

        Not yet implemented server-side (BF-6). Raises
        :class:`TrustNotProvisionedError`.
        """
        raise TrustNotProvisionedError(_TRUST_STUB_MESSAGE)


# ---------------------------------------------------------------------------
# Trust (BF-6 stubs)
# ---------------------------------------------------------------------------

class Trust:
    """Trust Manifold namespace (``client.trust``).

    Stubbed in Session 29 per S29 acceptance criteria (the surface
    must exist). Real wiring lands in BF-6 (before S44 closes).
    All methods raise :class:`TrustNotProvisionedError` with a clear
    message until then.
    """

    def __init__(self, client: MaiClient) -> None:
        self._client = client

    def claims(self) -> list[TrustClaim]:
        """GET /v1/trust/claims — list active claims for the current session."""
        raise TrustNotProvisionedError(_TRUST_STUB_MESSAGE)

    def bundle_status(self) -> TrustBundleStatus:
        """GET /v1/trust/bundle — local trust cache state."""
        raise TrustNotProvisionedError(_TRUST_STUB_MESSAGE)

    def revocation_status(self, subject_hash: str) -> RevocationStatusResponse:  # noqa: ARG002
        """GET /v1/trust/revocation/{subject_hash} — revocation snapshot lookup."""
        raise TrustNotProvisionedError(_TRUST_STUB_MESSAGE)


# ---------------------------------------------------------------------------
# Compliance (Session 36-44 surface — declared early per S29 spec)
# ---------------------------------------------------------------------------

class Compliance:
    """Lamprey compliance namespace (``client.compliance``).

    Reserved for Sessions 36-44 (router, HIPAA, ITAR/EAR, OCAP, policy
    runtime, audit, reports, dashboard). Session 29 only declares the
    attribute so application code can do feature detection.
    """

    def __init__(self, client: MaiClient) -> None:
        self._client = client

    def __getattr__(self, name: str) -> Any:
        raise NotImplementedError(
            f"compliance.{name} not yet available (Sessions 36-44 land Lamprey)",
        )


__all__ = [
    "Admin",
    "Auth",
    "Compliance",
    "Models",
    "Power",
    "Scheduler",
    "System",
    "Trust",
    "TrustNotProvisionedError",
    "Updates",
]
