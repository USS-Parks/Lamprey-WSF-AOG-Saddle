# 01-06: Security Model

## Architectural Posture

- **Air-Gap Default:** Zero network assumptions. All components must function offline. Network is an exception, not a requirement.
- **Local-Only Telemetry:** Health metrics, audit logs, and usage stats NEVER transmit off-device. Stored in append-only vault with 90-day retention.
- **PQC-First:** ML-KEM (Kyber-1024) for encryption at rest. ML-DSA (Dilithium) for signatures. No classical fallback in production paths.
- **TPM Key Sealing:** Master encryption key sealed to TPM 2.0 PCRs. Model loading requires attestation.

## Threat Mitigations

| Threat | Mitigation |
|--------|------------|
| Adapter sandbox escape | Process isolation + cgroups + no `unsafe` bridge |
| Model weight tampering | SHA-256 hash tree + ML-DSA signature verification on load |
| Audit log manipulation | PQC-signed entries + cryptographic hash chaining |
| Profile privilege escalation | API middleware enforcement + SQLite WAL + read-only profile store |
| Network bypass (air-gap) | Hard switch monitoring + startup refusal + periodic daemon checks |
| Memory/swap leak | `mlock()` for sensitive buffers, `zeroize` on drop, no swap for vault partitions |
