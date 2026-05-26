#!/usr/bin/env python3
"""Run detect-secrets without multiprocessing.

The upstream `detect-secrets scan` CLI always constructs a multiprocessing
pool when more than one file is scanned. On this Windows evidence host that
fails while creating IPC pipes, before any file is inspected. This wrapper
uses the same detect-secrets plugins and output format, but scans files one
at a time so the evidence runner gets a real secret-scan result.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from detect_secrets.core import baseline
from detect_secrets.core.secrets_collection import SecretsCollection
from detect_secrets.settings import default_settings


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serial detect-secrets scan.")
    parser.add_argument("paths", nargs="*", default=["."], help="Files or directories to scan.")
    parser.add_argument("--all-files", action="store_true", help="Scan all files instead of only git-tracked files.")
    parser.add_argument("--exclude-files", default="", help="Regex for relative paths to skip.")
    parser.add_argument("--fail-on-findings", action="store_true", help="Exit 1 when secrets are detected.")
    return parser.parse_args(argv)


def git_tracked_files(root: Path) -> set[str]:
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        text=True,
        capture_output=True,
        timeout=30,
    )
    if completed.returncode != 0:
        return set()
    return {line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()}


def iter_candidate_files(root: Path, paths: list[str], all_files: bool) -> list[str]:
    tracked = git_tracked_files(root)
    results: list[str] = []
    for raw in paths:
        path = (root / raw).resolve()
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            if all_files or not tracked or rel in tracked:
                results.append(rel)
            continue
        if not path.is_dir():
            continue
        for dirpath, _, filenames in os.walk(path):
            for filename in filenames:
                candidate = Path(dirpath) / filename
                try:
                    rel = candidate.resolve().relative_to(root).as_posix()
                except ValueError:
                    continue
                if all_files or not tracked or rel in tracked:
                    results.append(rel)
    return sorted(set(results))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = Path.cwd().resolve()
    exclude = re.compile(args.exclude_files) if args.exclude_files else None
    candidates = [
        rel for rel in iter_candidate_files(root, args.paths, args.all_files)
        if exclude is None or not exclude.search(rel)
    ]

    with default_settings():
        secrets = SecretsCollection(root=str(root))
        for rel in candidates:
            secrets.scan_file(rel)
        payload = baseline.format_for_output(secrets)

    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    has_findings = any(payload.get("results", {}).values())
    return 1 if args.fail_on_findings and has_findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
