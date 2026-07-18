#!/usr/bin/env python3
"""Generate disposable Saddle test PKI and runtime-state directories.

Nothing produced by this tool belongs in Git.  It is the SAD-03 replacement for
imported certificates, private keys, OpenBao state, and other machine-local
runtime material.  The destination must not exist so the command cannot
silently overwrite a previous environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
STATE_DIRECTORIES = (
    "state/audit",
    "state/openbao",
    "state/raft",
    "state/receipts",
    "state/saddle-store",
)


class MaterialError(RuntimeError):
    """Raised when ephemeral material cannot be generated safely."""


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--openssl", default="openssl")
    parser.add_argument("--days", default=1, type=int)
    return parser.parse_args(argv)


def fail(message: str) -> None:
    raise MaterialError(message)


def run(command: list[str]) -> None:
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode != 0:
        rendered = completed.stderr.decode("utf-8", "replace").strip()
        fail(f"OpenSSL command failed ({completed.returncode}): {' '.join(command)}: {rendered}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encoded(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def restrict_private_key(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError as error:
        fail(f"cannot restrict private key permissions for {path}: {error}")


def generate(openssl: str, output: Path, days: int) -> None:
    pki = output / "pki"
    pki.mkdir(parents=True)
    ca_key = pki / "ca.key"
    ca_cert = pki / "ca.crt"
    run(
        [
            openssl,
            "req",
            "-x509",
            "-new",
            "-nodes",
            "-newkey",
            "rsa:2048",
            "-sha256",
            "-days",
            str(days),
            "-subj",
            "/CN=Saddle Ephemeral Test CA",
            "-keyout",
            str(ca_key),
            "-out",
            str(ca_cert),
        ]
    )
    for identity, subject, san in (
        ("server", "/CN=saddle-test-server", "DNS:localhost,IP:127.0.0.1"),
        ("client", "/CN=saddle-test-client", ""),
    ):
        key = pki / f"{identity}.key"
        csr = pki / f"{identity}.csr"
        cert = pki / f"{identity}.crt"
        request = [
            openssl,
            "req",
            "-new",
            "-nodes",
            "-newkey",
            "rsa:2048",
            "-subj",
            subject,
            "-keyout",
            str(key),
            "-out",
            str(csr),
        ]
        if san:
            request.extend(("-addext", f"subjectAltName={san}"))
        run(request)
        run(
            [
                openssl,
                "x509",
                "-req",
                "-in",
                str(csr),
                "-CA",
                str(ca_cert),
                "-CAkey",
                str(ca_key),
                "-CAcreateserial",
                "-out",
                str(cert),
                "-days",
                str(days),
                "-sha256",
                "-copy_extensions",
                "copy",
            ]
        )
        csr.unlink()
    serial = pki / "ca.srl"
    if serial.is_file():
        serial.unlink()
    for key in (ca_key, pki / "server.key", pki / "client.key"):
        restrict_private_key(key)
    for relative in STATE_DIRECTORIES:
        (output / relative).mkdir(parents=True)
    manifest = {
        "certificate_sha256": {
            "ca": sha256(ca_cert),
            "client": sha256(pki / "client.crt"),
            "server": sha256(pki / "server.crt"),
        },
        "ephemeral": True,
        "private_key_paths": ["pki/ca.key", "pki/client.key", "pki/server.key"],
        "schema_version": SCHEMA_VERSION,
        "state_directories": list(STATE_DIRECTORIES),
    }
    (output / "material-manifest.json").write_bytes(encoded(manifest))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    output = args.output.resolve()
    if args.days < 1 or args.days > 7:
        fail("--days must be between 1 and 7 for disposable test material")
    if output.exists():
        fail(f"output already exists; refusing to overwrite runtime material: {output}")
    parent = output.parent
    if not parent.is_dir():
        fail(f"output parent does not exist: {parent}")
    created = False
    try:
        output.mkdir()
        created = True
        run([args.openssl, "version"])
        generate(args.openssl, output, args.days)
    except (OSError, MaterialError):
        if created:
            shutil.rmtree(output, ignore_errors=True)
        raise
    print(f"Saddle ephemeral test material: PASS ({output})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MaterialError as error:
        print(f"Saddle ephemeral test material failed: {error}", file=sys.stderr)
        raise SystemExit(2)
