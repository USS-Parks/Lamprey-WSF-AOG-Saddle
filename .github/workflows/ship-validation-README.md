# Saddle Validation Workflow

Workflow file: [`ship-validation.yml`](./ship-validation.yml)

This workflow covers repository contracts that complement the Rust-focused
`Saddle CI` workflow:

- the six-binary Saddle package layout;
- production/demo Compose trust posture;
- independent-source and active-identity boundaries;
- static workflow/package contracts; and
- a scheduled or manually dispatched full Rust and active-tooling matrix.

The imported MAI forbidden-symbol allowlist, ship validator, admin backup,
Python SDK, inference adapter, dashboard, and GPU release jobs are intentionally
absent. Their roots and packages are not members of this repository's
38-package workspace and cannot be claimed as Saddle gates.

The fast jobs run on every push to `main` and every pull request. The full
matrix runs nightly at 03:30 UTC and on `workflow_dispatch`. A nightly run is
eligible only after all fast jobs pass.

Workflow drift is tested in `tools/ci_surface_tests/`, including unknown Cargo
package references and executable Git modes for tracked shell entrypoints.
