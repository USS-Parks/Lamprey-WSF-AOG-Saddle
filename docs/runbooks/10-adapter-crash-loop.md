# Runbook 10 — Adapter Crash Loop

## When to use

- `mai-adapter-manager.service` is in `failed` state or
  flapping `active <-> failed`.
- `/v1/health/adapters` reports any adapter with
  `state = "crashed"` and `restart_count` climbing.
- Clients see `503 adapter_unavailable` for one or more models.

## What "adapter" means here

Adapters are the per-backend Python subprocesses (`ollama`,
`vllm`, `llamacpp`, `tgi`, `tensorrt`, `exllamav2`, `sglang`)
that load and serve a model. Each runs under `mai-adapter-manager`
with its own systemd-style supervisor loop and NDJSON IPC to
the API.

## Triage steps

1. Identify which adapter:
   ```bash
   curl -fsS -H "X-IM-Auth-Token: $MAI_ADMIN_TOKEN" \
        http://127.0.0.1:8420/v1/health/adapters | jq .
   ```
   Pick the entries with `state != "running"` and a non-zero
   `restart_count`.
2. Pull the last crash output:
   ```bash
   sudo journalctl -u mai-adapter-manager.service -n 200 --no-pager
   ```
   And the per-adapter log:
   ```bash
   sudo tail -n 200 /var/log/mai/adapter-<name>.log
   ```
3. Classify the failure:
   - **CUDA / driver fault.** GPU is the host's responsibility,
     not MAI's. Check `nvidia-smi`; check
     `journalctl -k | grep -i nvidia`. If the driver is wedged,
     resolve at the host layer (reboot, reset, replace).
   - **Out of VRAM.** The scheduler should not place a model
     that does not fit; if it did, the placement decision is the
     bug. Capture the placement event from the audit feed and
     open an issue. Mitigation: unload the model or move it to
     a host with more VRAM.
   - **Model file missing / corrupt.** `/var/lib/mai/models/`
     was modified out-of-band. Re-import the model via the
     standard pipeline; do not hand-edit.
   - **Adapter Python venv broken.** Postinstall left the venv
     in a bad state, or an `apt upgrade` of system Python broke
     ABI. Re-install the `mai-adapter-manager` half of the
     package.
   - **Backend bug (vLLM/Ollama/etc.).** Pin the backend
     version; isolate the model that triggers it; report
     upstream.

## Stabilize quickly (cool-down)

If clients are seeing 503 storms, drain the failing model from
the scheduler so non-failing models still serve:

```bash
curl -fsS -X POST -H "X-IM-Auth-Token: $MAI_ADMIN_TOKEN" \
     "http://127.0.0.1:8420/v1/models/<model>/disable"
```

This is reversible; re-enable via the same path with `/enable`.

## Full recovery

1. Address the root cause (above).
2. Reset the supervisor counter:
   ```bash
   sudo systemctl reset-failed mai-adapter-manager.service
   sudo systemctl restart mai-adapter-manager.service
   ```
3. Confirm `/v1/health/adapters` shows `state = "running"`
   with `restart_count = 0` for the recovered adapter.
4. Re-enable the model if you disabled it during cool-down.

## Do not

- Do not raise `restart_max` to "fix" a crash loop. The cap
  exists so a failing adapter does not consume infinite GPU
  resources. Raising it hides the failure, it does not solve it.
- Do not `kill -9` adapter subprocesses to force a reset. The
  IPC channel will be in an undefined state. Use
  `systemctl restart mai-adapter-manager.service` instead.
- Do not edit `/var/lib/mai/models/` by hand to "fix" a
  corrupt file. Use the model import pipeline so the manifest
  and audit trail stay coherent.
