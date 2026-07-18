# Saddle Packaging

This directory packages the runnable boundary owned by this repository. It does
not ship the excluded MAI inference SDK, adapter framework, dashboard, or GPU
release lane.

The package contains these workspace binaries:

- `saddled`
- `saddle-noded`
- `saddlectl`
- `wsf-api`
- `wsf-seed`
- `aog-gateway`

It also carries the tracked configuration templates, the Kubernetes manifest,
the architecture contract, and build provenance under
`/usr/share/doc/saddle/PACKAGE_BUILD_INFO`.

Run a layout-only validation on any checkout with Git and standard POSIX tools:

```bash
./scripts/build-package.sh --validate-only
python -m pytest tools/packaging_tests -v
```

Run a real binary staging build on Linux with:

```bash
./scripts/build-package.sh
```

Add `--deb` on a Debian build host with `dpkg-buildpackage` installed. The
validation-only mode uses empty binary placeholders and records
`validation_only=true`; it is never a release artifact.
