# OpenBao staging boundary

This directory is intentionally not a Saddle runtime or deployment interface.
The pinned seed contained environment-specific staging anchors, static
AppRole/key-hash configuration, and bootstrap automation that cannot prove
independent, non-secret reproducibility.

Saddle tests generate disposable PKI and state through
`tools/generate_saddle_ephemeral_test_material.py`. Do not copy source staging
keys, role identifiers, trust anchors, OpenBao state, or incident-response
scripts into this directory. Future Saddle OpenBao operations require their own
approved prompt, generated configuration, and live verification evidence.
