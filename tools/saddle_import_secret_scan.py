#!/usr/bin/env python3
"""Run Saddle's strict, dependency-free secondary import secret detector.

This is intentionally independent from Gitleaks.  It scans only a materialized
tracked-file import simulation and emits location/fingerprint metadata, never a
matched value.  Any narrow suppression must pin the exact finding fingerprint
and carry a human review reason.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
MAX_FILE_BYTES = 64 * 1024 * 1024
OPERATIONAL_SUFFIXES = {
    ".conf",
    ".env",
    ".ini",
    ".json",
    ".jsonl",
    ".log",
    ".md",
    ".properties",
    ".ps1",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

DIRECT_RULES: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    (
        "private-key-pem",
        re.compile(
            rb"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----\s*"
            rb"(?:[A-Za-z0-9+/=]\s*){64,}"
            rb"-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"
        ),
    ),
    ("aws-access-key", re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    (
        "github-token",
        re.compile(
            rb"\b(?:ghp|gho|ghu|ghs)_[A-Za-z0-9]{20,}\b"
            rb"|\bgithub_pat_[A-Za-z0-9_]{20,}\b"
        ),
    ),
    ("gitlab-token", re.compile(rb"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("slack-token", re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("stripe-secret", re.compile(rb"\bsk_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    (
        "openai-or-anthropic-key",
        re.compile(rb"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}\b"),
    ),
    (
        "credential-url",
        re.compile(rb"(?i)https?://[^/\s:@]+:[^/\s@]+@"),
    ),
    ("bearer-token", re.compile(rb"(?i)\bbearer\s+[A-Za-z0-9._-]{24,}\b")),
)

ASSIGNMENT_RULE = re.compile(
    rb"(?im)^\s*(?:export\s+)?"
    rb"(?P<label>(?:[A-Z0-9_]*?(?:API(?:_|-)?KEY|TOKEN|SECRET|PASSWORD|PASSWD|"
    rb"PRIVATE(?:_|-)?KEY|CREDENTIAL)[A-Z0-9_]*)"
    rb")\s*[:=]\s*[\"']?(?P<value>[A-Za-z0-9+/_.=-]{16,})"
)


class ScanError(RuntimeError):
    """Raised when the scanner cannot establish complete coverage."""


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--exceptions",
        type=Path,
        help="Optional exact-fingerprint exception file with reviewed synthetic findings.",
    )
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Exit non-zero when any finding remains unsuppressed.",
    )
    return parser.parse_args(argv)


def fail(message: str) -> None:
    raise ScanError(message)


def relative_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        fail(f"scanner path escapes root: {path}")
        raise AssertionError from error


def iter_files(root: Path) -> Iterable[tuple[str, Path]]:
    if not root.is_dir():
        fail(f"scan root is not a directory: {root}")
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        yield relative_path(root, path), path


def line_number(content: bytes, offset: int) -> int:
    return content.count(b"\n", 0, offset) + 1


def finding_fingerprint(rule_id: str, path: str, line: int, matched: bytes) -> str:
    payload = b"\0".join(
        (rule_id.encode("utf-8"), path.encode("utf-8"), str(line).encode("ascii"), matched)
    )
    return hashlib.sha256(payload).hexdigest()


def match_metadata(matched: bytes) -> dict[str, Any]:
    return {
        "matched_is_lowercase_hex": bool(re.fullmatch(rb"[0-9a-f]{40,}", matched)),
        "matched_length": len(matched),
        "matched_sha256": hashlib.sha256(matched).hexdigest(),
    }


def entropy(value: bytes) -> float:
    if not value:
        return 0.0
    size = len(value)
    frequencies = {byte: value.count(byte) / size for byte in set(value)}
    return -sum(probability * math.log2(probability) for probability in frequencies.values())


def is_placeholder(value: bytes) -> bool:
    rendered = value.decode("utf-8", "replace").lower()
    markers = (
        "change-me",
        "replace-with",
        "your-",
        "example",
        "placeholder",
        "dummy",
        "fake",
        "test-",
        "sample",
        "not-a-",
        "${",
        "{{",
        "...",
    )
    return any(marker in rendered for marker in markers) or rendered in {"none", "null"}


def load_exceptions(path: Path | None) -> dict[tuple[str, str, int, str], str]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        fail(f"cannot read exceptions file {path}: {error}")
    except json.JSONDecodeError as error:
        fail(f"exceptions file is not JSON: {error}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        fail("exceptions file has an unsupported schema version")
    results: dict[tuple[str, str, int, str], str] = {}
    for item in payload.get("suppressed_findings", []):
        if not isinstance(item, dict):
            fail("exceptions file contains a non-object finding")
        try:
            key = (
                str(item["rule_id"]),
                str(item["path"]),
                int(item["line"]),
                str(item["fingerprint"]),
            )
            reason = str(item["reason"])
        except (KeyError, TypeError, ValueError) as error:
            fail(f"exceptions file contains an invalid finding: {error}")
        if not reason.strip():
            fail("exceptions file contains an unreviewed suppression")
        if key in results:
            fail("exceptions file contains a duplicate finding")
        results[key] = reason
    return results


def append_finding(
    findings: list[dict[str, Any]],
    seen: set[tuple[str, str, int, str]],
    rule_id: str,
    path: str,
    content: bytes,
    start: int,
    matched: bytes,
) -> None:
    line = line_number(content, start)
    fingerprint = finding_fingerprint(rule_id, path, line, matched)
    key = (rule_id, path, line, fingerprint)
    if key in seen:
        return
    seen.add(key)
    findings.append(
        {
            "fingerprint": fingerprint,
            "line": line,
            **match_metadata(matched),
            "path": path,
            "rule_id": rule_id,
        }
    )


def scan_file(path: str, content: bytes) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int, str]] = set()
    lower_path = path.lower()
    operational_surface = lower_path.endswith(".env.example") or Path(lower_path).suffix in OPERATIONAL_SUFFIXES
    rules = DIRECT_RULES if operational_surface else tuple(
        rule for rule in DIRECT_RULES if rule[0] == "private-key-pem"
    )
    for rule_id, pattern in rules:
        for match in pattern.finditer(content):
            append_finding(findings, seen, rule_id, path, content, match.start(), match.group(0))
    if operational_surface:
        for match in ASSIGNMENT_RULE.finditer(content):
            value = match.group("value")
            label = match.group("label").decode("ascii")
            if label.upper().endswith("_FILE") or is_placeholder(value) or entropy(value) < 3.25:
                continue
            append_finding(
                findings,
                seen,
                "high-entropy-credential-assignment",
                path,
                content,
                match.start("value"),
                value,
            )
    return findings


def encoded(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = args.root.resolve()
    exceptions = load_exceptions(args.exceptions)
    raw_findings: list[dict[str, Any]] = []
    files_scanned = 0
    for relative, path in iter_files(root):
        try:
            content = path.read_bytes()
        except OSError as error:
            fail(f"cannot read {relative}: {error}")
        if len(content) > MAX_FILE_BYTES:
            fail(f"refusing incomplete scan of oversized file: {relative}")
        files_scanned += 1
        raw_findings.extend(scan_file(relative, content))

    findings: list[dict[str, Any]] = []
    suppressed_count = 0
    matched_exception_keys: set[tuple[str, str, int, str]] = set()
    for finding in sorted(
        raw_findings,
        key=lambda item: (item["path"], item["line"], item["rule_id"], item["fingerprint"]),
    ):
        key = (
            finding["rule_id"],
            finding["path"],
            finding["line"],
            finding["fingerprint"],
        )
        suppression = exceptions.get(key)
        finding["suppressed"] = suppression is not None
        if suppression is not None:
            finding["suppression_reason"] = suppression
            suppressed_count += 1
            matched_exception_keys.add(key)
        findings.append(finding)
    unused_exceptions = set(exceptions) - matched_exception_keys
    if unused_exceptions:
        fail("exceptions file contains a stale finding that no longer matches the staged import")

    payload = {
        "detector": "saddle-import-secondary-static-v1",
        "findings": findings,
        "root": ".",
        "schema_version": SCHEMA_VERSION,
        "totals": {
            "files_scanned": files_scanned,
            "raw_finding_count": len(findings),
            "suppressed_finding_count": suppressed_count,
            "unsuppressed_finding_count": len(findings) - suppressed_count,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded(payload))
    unsuppressed = payload["totals"]["unsuppressed_finding_count"]
    print(
        "Saddle secondary secret scan: "
        f"{files_scanned} files, {unsuppressed} unsuppressed finding(s)"
    )
    return 1 if args.fail_on_findings and unsuppressed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScanError as error:
        print(f"Saddle secondary secret scan failed: {error}", file=sys.stderr)
        raise SystemExit(2)
