"""CLI smoke tests — argparse wiring + monkeypatched client."""

from __future__ import annotations

from typing import Any

import pytest
from mai import cli
from mai.errors import AuthenticationError


class _FakePower:
    def get_state(self) -> Any:
        from mai.types import AutoDemotion, PowerState, PowerStateResponse
        return PowerStateResponse(
            state=PowerState.FULL_INFERENCE,
            estimated_power_watts=200.0,
            auto_demotion=AutoDemotion(enabled=False),
            promotion_available=True,
            promotion_latency_target_ms=1000,
        )


class _FakeModels:
    def list(self, **_: Any) -> list[Any]:
        from mai.types import (
            CapabilityInfo,
            ModelFormat,
            ModelObject,
            ModelStatus,
        )
        return [ModelObject(
            id="m1", created=1, name="m1", version="v1",
            format=ModelFormat.GGUF, size_bytes=1024**3,
            required_vram_bytes=1024**3,
            status=ModelStatus.LOADED,
            capabilities=CapabilityInfo(chat=True),
        )]

    def load(self, model_id: str) -> Any:
        from mai.types import ModelLoadResponse, ModelStatus
        return ModelLoadResponse(
            model_id=model_id, status=ModelStatus.LOADED,
            adapter_id="a1", gpu_id="g0",
            vram_allocated_bytes=0, load_time_ms=12,
        )

    def unload(self, model_id: str) -> Any:
        from mai.types import ModelStatus, ModelUnloadResponse
        return ModelUnloadResponse(
            model_id=model_id, status=ModelStatus.EVICTED,
            vram_freed_bytes=512,
        )

    def benchmark(self, model_id: str) -> Any:
        from mai.types import BenchmarkResult
        return BenchmarkResult(
            model_id=model_id, completed=True,
            tokens_per_second=42.0,
            first_token_latency_ms=80.0,
            p50_latency_ms=100.0, p95_latency_ms=200.0, p99_latency_ms=300.0,
        )


class _FakeClient:
    def __init__(self, *_: Any, **__: Any) -> None:
        self.models = _FakeModels()
        self.power = _FakePower()

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def close(self) -> None:
        pass

    def health(self) -> Any:
        from mai.types import HealthResponse, PowerState
        return HealthResponse(
            status="healthy", air_gap_verified=True,
            power_state=PowerState.FULL_INFERENCE,
            uptime_seconds=100,
            adapters={}, hardware={}, system={},
        )


@pytest.fixture(autouse=True)
def _patch_build(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_build_client", lambda _args: _FakeClient())


def test_cli_health(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["health"])
    out = capsys.readouterr().out
    assert rc == cli.EXIT_OK
    assert "status: healthy" in out


def test_cli_health_json(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--json", "health"])
    out = capsys.readouterr().out
    assert rc == cli.EXIT_OK
    assert '"status"' in out


def test_cli_models_list(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["models", "list"])
    out = capsys.readouterr().out
    assert rc == cli.EXIT_OK
    assert "m1" in out


def test_cli_models_load(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["models", "load", "m1"])
    out = capsys.readouterr().out
    assert rc == cli.EXIT_OK
    assert "loaded: m1" in out


def test_cli_models_unload(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["models", "unload", "m1"])
    out = capsys.readouterr().out
    assert rc == cli.EXIT_OK
    assert "unloaded: m1" in out


def test_cli_benchmark(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["benchmark", "m1"])
    out = capsys.readouterr().out
    assert rc == cli.EXIT_OK
    assert "42.0 tok/s" in out


def test_cli_power_state(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["power", "state"])
    out = capsys.readouterr().out
    assert rc == cli.EXIT_OK
    assert "state: full_inference" in out


def test_cli_auth_error_exits_with_auth_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    class _ErrClient(_FakeClient):
        def health(self) -> Any:
            raise AuthenticationError("bad key", status_code=401)

    monkeypatch.setattr(cli, "_build_client", lambda _args: _ErrClient())
    rc = cli.main(["health"])
    capsys.readouterr()  # drain stderr
    assert rc == cli.EXIT_AUTH


def test_cli_no_subcommand_prints_help_and_exits_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as ei:
        cli.main([])
    assert ei.value.code == 2  # argparse usage exit
    err = capsys.readouterr().err
    assert "required" in err.lower()
