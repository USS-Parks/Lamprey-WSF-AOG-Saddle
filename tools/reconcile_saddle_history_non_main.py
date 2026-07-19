#!/usr/bin/env python3
"""Reconcile every review-required non-main Mighty Eel commit for SAD-HIST-03."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


APPROVED_SOURCE_MAIN = "fedf005a30ad388ab156dc8bd693a3aa3f0702ea"
HISTORY_BASE = "0e3bd77656601b46cc03d96765d703c3916dbcd3"
ALLOWED_DISPOSITIONS = {"reuse", "superseded", "transplant", "archive", "exclusion"}
SCHEMA = "saddle-non-main-reconciliation/v1"


class ReconciliationError(RuntimeError):
    """Raised when the SAD-HIST-03 reconciliation contract is not satisfied."""


def fail(message: str) -> None:
    raise ReconciliationError(message)


def evidence(path: str, purpose: str, *anchors: str) -> dict[str, Any]:
    return {"anchors": list(anchors), "path": path, "purpose": purpose}


# This is a human decision table, not a patch-equivalence heuristic. Every entry
# names the behavior that was reviewed, the later implementation that controls
# Saddle today, and the exact code/test anchors that make the disposition
# auditable. The builder rejects any drift from the SAD-HIST-01 review queue.
DECISIONS: dict[str, dict[str, Any]] = {
    "02ae597155582f6fbcb25ae171d9b70cc2843943": {
        "behavior": "GitHub-hosted JavaScript actions moved off deprecated Node 20 runtimes.",
        "disposition": "superseded",
        "rationale": (
            "Saddle commit 30a30db independently moved the active workflow set to the "
            "declared Node 24 action majors and added a contract test. It is broader and "
            "newer than the source commit's checkout-v5 transition."
        ),
        "source_main_commits": [],
        "saddle_commits": ["30a30dbc4027d4b27080c2a329acb9364155125f"],
        "evidence": [
            evidence(
                ".github/workflows/ci.yml",
                "Active CI uses the current Node 24 checkout major.",
                "actions/checkout@v7",
            ),
            evidence(
                "tools/ci_surface_tests/test_workflows.py",
                "The workflow contract rejects a regression to older JavaScript runtimes.",
                '"actions/checkout": "v7"',
                "def test_javascript_actions_and_project_node_use_node24",
            ),
        ],
        "verification": ["python -m pytest tools/ci_surface_tests/test_workflows.py -q"],
    },
    "9684ab5f237ef7818d7485f25b657d95884c4a73": {
        "behavior": (
            "AF-001 parent authentication and monotonic attenuation, including the "
            "AOG mutate-stage call path."
        ),
        "disposition": "superseded",
        "rationale": (
            "The approved source main closed the same finding through smaller reviewed "
            "T1-T7 commits, then added lineage, versioning, and property hardening. "
            "Saddle imported that complete state and later renamed and hardened the AOG "
            "server boundary; the branch patch is an earlier, narrower implementation."
        ),
        "source_main_commits": [
            "aee70e10a87438db8a7b923ab46217751d5329ef",
            "bfdfa6ab0deb46db9ddd9a8758378029ed3f4b88",
            "f68f95b2c09f3a90a9960355bbc5f021b50a9ece",
            "1543b93544e242895c29c88f28ca27bb4cd531e3",
            "b3b674561be71e24bdb1a172ae1d2ef00c7f9e7b",
            "521837d2af294f93d637e23fe431ead1e7ba919b",
            "fc9c71a2d9f4767cc1423ccfd0e27884d325d87d",
        ],
        "saddle_commits": ["850628da4cffc92fc17e22811377a7c8eece1101"],
        "evidence": [
            evidence(
                "crates/fabric-token/src/lib.rs",
                "Attenuation authenticates the parent and applies the complete monotonicity gate.",
                "pub fn attenuate(",
                "verify_in_context(parent, ctx)?",
                "fn narrow_child(",
            ),
            evidence(
                "crates/fabric-token/tests/security_regression.rs",
                "Permanent adversarial fixtures reject unsigned, wrong-key, and widening parents.",
                "fn reg_af_001_unsigned_parent_is_rejected",
                "fn reg_af_001_wrong_key_parent_is_rejected",
                "fn reg_af_001_role_widening_is_rejected",
            ),
            evidence(
                "crates/saddle-apiserver/src/seal.rs",
                "The renamed Saddle server uses the reviewed preverified attenuation seam.",
                "pub fn scoped_child_token(",
                "attenuate_preverified",
            ),
        ],
        "verification": [
            "cargo test -p fabric-token",
            "cargo test -p saddle-apiserver --test seal",
        ],
    },
    "7b65774afd6bb6b6e06a9554b08318a7483d3806": {
        "behavior": (
            "AF-001 full attenuation closure across token, WSF, AOG, scheduler, node, and "
            "broker consumers."
        ),
        "disposition": "superseded",
        "rationale": (
            "The approved source-main T1-T7 series is the reviewed implementation and "
            "contains stricter parent context, expiry, external revocation, depth, lineage, "
            "and property checks. Saddle imported it and subsequently hardened its renamed "
            "bridge and server paths, so no branch transplant remains."
        ),
        "source_main_commits": [
            "aee70e10a87438db8a7b923ab46217751d5329ef",
            "bfdfa6ab0deb46db9ddd9a8758378029ed3f4b88",
            "77bc784cbdf92c6a66b0b4c29dbc70846842f2ac",
            "f68f95b2c09f3a90a9960355bbc5f021b50a9ece",
            "1543b93544e242895c29c88f28ca27bb4cd531e3",
            "61c120aac590382d577181322e3fc3b72bfe9e55",
        ],
        "saddle_commits": [
            "850628da4cffc92fc17e22811377a7c8eece1101",
            "9d173b2242720eb21e5f3ea5206022c3c77d05e8",
            "ef8b27236e1e4f24b27fbad9b249703299291bfc",
        ],
        "evidence": [
            evidence(
                "crates/fabric-token/tests/attenuation_context.rs",
                "Context tests cover tenant, bundle, freshness, and external revocation.",
                "fn verify_in_context_rejects_wrong_tenant_and_bundle",
                "fn verify_in_context_fresh_revocation_rejects_unknown",
            ),
            evidence(
                "crates/fabric-token/tests/attenuation_property.rs",
                "Property coverage exercises the monotonicity surface beyond fixed examples.",
                "fn randomized_widening_on_every_axis_is_rejected",
                "fn valid_narrowing_on_every_axis_succeeds",
            ),
            evidence(
                "crates/wsf-api/tests/attenuate_live.rs",
                "The public WSF route has an OpenBao-backed live attenuation gate.",
                "SKIP attenuate_live: set WSF_OPENBAO_ADDR",
            ),
            evidence(
                "crates/saddle-bridge/tests/contract_properties.rs",
                "Saddle's current bridge contract retains bounded authority properties.",
                "fn property_every_authority_axis_only_narrows",
            ),
        ],
        "verification": [
            "cargo test -p fabric-token",
            "cargo test -p saddle-bridge --test contract_properties",
        ],
    },
    "fe8f3321724c95bd45fc15715a9df28f0fc46075": {
        "behavior": "AF-002 authenticated, tenant-bound WSF token issuance and authorization.",
        "disposition": "superseded",
        "rationale": (
            "Approved source main implemented A1-A5 as separate principal, authenticator, "
            "policy, receipt, and live-gate commits. Saddle imported that complete series; "
            "the branch's combined Phase A patch is not the controlling implementation."
        ),
        "source_main_commits": [
            "97ad579fdc204ec7e324cb915d5bc88789d3c489",
            "a71bf03b5881ad0b48f094d1cf264e3b4bf6e6d0",
            "1a876859a2b4b67f2d464b7287c3c9a4da269278",
            "4dd56d178fa113e57633193a0706f1a109a7d081",
            "c509219ca63fcae9a23a9c89be12a7e7211c5ce4",
            "093b09e530e8a8f1f9e1e000973f970272dc67d3",
        ],
        "saddle_commits": ["850628da4cffc92fc17e22811377a7c8eece1101"],
        "evidence": [
            evidence(
                "crates/fabric-contracts/src/principal.rs",
                "The issued identity is a typed authenticated principal, not request JSON.",
                "pub struct WsfPrincipal",
            ),
            evidence(
                "crates/wsf-api/src/auth.rs",
                "Production authentication verifies signed workload credentials and tenant binding.",
                "pub trait WsfAuthenticator",
                "pub struct WorkloadAuthenticator",
            ),
            evidence(
                "crates/wsf-api/tests/issuance_perms.rs",
                "Permission tests deny ungranted roles and unknown tenants.",
                "async fn ungranted_role_is_denied_with_mode_labeled_receipt",
                "async fn unknown_tenant_is_denied_before_any_policy",
            ),
            evidence(
                "crates/wsf-api/tests/issue_authz.rs",
                "The two-tenant live authorization gate remains present.",
                "async fn two_tenants_two_workloads_against_live_openbao",
            ),
        ],
        "verification": [
            "cargo test -p fabric-contracts",
            "cargo test -p wsf-api --test auth_gate --test issuance_perms",
        ],
    },
    "9aea8b60b29fa90e5bb3b500b22546965e85dac5": {
        "behavior": "AF-003 tenant- and subject-bound envelope seal/unseal behavior.",
        "disposition": "superseded",
        "rationale": (
            "Approved source main separately implemented tenant-bound v2 envelopes, "
            "per-tenant Transit keys, service-capability checks, migration, and live tests. "
            "Saddle imported that broader state, which supersedes the branch Phase E patch."
        ),
        "source_main_commits": [
            "8fcb6ae7ed4f1458e5b1d767fea742c865566ef4",
            "0a7f3839c55382512f8eb607afc79c1251779425",
            "c15631c877d6e6ef4059b814733479f2863f4852",
            "4f7e29da413496e5ea4ef961ac5a1794bd6e1867",
        ],
        "saddle_commits": ["850628da4cffc92fc17e22811377a7c8eece1101"],
        "evidence": [
            evidence(
                "crates/fabric-contracts/src/envelope.rs",
                "The envelope contract carries an explicit tenant binding and v2 version.",
                "pub tenant_id: String",
                "pub envelope_version: u32",
            ),
            evidence(
                "crates/wsf-seal/src/lib.rs",
                "Seal/unseal derives tenant ownership and isolates Transit keys per tenant.",
                "pub fn transit_key_for",
                "cross-tenant unseal denied",
            ),
            evidence(
                "crates/wsf-seal/tests/live_tenant_keys.rs",
                "A live OpenBao test proves cryptographic tenant-key isolation.",
                "async fn per_tenant_transit_keys_isolate_wrapped_material",
            ),
        ],
        "verification": [
            "cargo test -p fabric-envelope",
            "cargo test -p wsf-seal --lib",
        ],
    },
    "d935079723f23a92ac4a6cf06273f3ce5e7d2daf": {
        "behavior": "AF-004 tenant-scoped named grants for bounded cloud credential exchange.",
        "disposition": "superseded",
        "rationale": (
            "Approved source main split the broker fix into grant resolution, least privilege, "
            "credential hygiene, and live gates for AWS, Azure, and GCP. Saddle imported the "
            "complete provider-neutral design, superseding the earlier branch patch."
        ),
        "source_main_commits": [
            "9b66c3adceeed594d62ab1300a7a1ef3a2c96578",
            "d5111e38bf4bd2bb92a5d679b1b6857205616bab",
            "30073bb33cf99d92bd5c0630bb253fdcc5989fb1",
            "dc8db0921cd3d350f8f28da4df8a7cde92e8dfe6",
        ],
        "saddle_commits": ["850628da4cffc92fc17e22811377a7c8eece1101"],
        "evidence": [
            evidence(
                "crates/wsf-api/src/grants.rs",
                "Callers name a tenant-scoped grant; server-side policy resolves cloud identity.",
                "pub trait GrantStore",
                "fn grant_for(&self, tenant_id: &str, grant_id: &str)",
            ),
            evidence(
                "crates/wsf-broker/src/lib.rs",
                "Broker scope types carry only server-resolved grant authority.",
                "pub struct GrantScope",
                "pub struct AzureGrantScope",
                "pub struct GcpGrantScope",
            ),
            evidence(
                "crates/wsf-api/tests/broker_grant.rs",
                "The public exchange route rejects raw or cross-tenant authority.",
                "async fn exchange_is_grant_scoped_not_raw_arn",
            ),
        ],
        "verification": [
            "cargo test -p wsf-broker --lib",
            "cargo test -p wsf-api --test broker_grant --no-run",
        ],
    },
    "83742a6e4c29beafc897af29672f05cc471ed337": {
        "behavior": "AF-007 authenticated tenant-scoped receipt queries and auditor export.",
        "disposition": "superseded",
        "rationale": (
            "Approved source main implemented tenant scoping, auditor-only cross-tenant reads, "
            "and signed export in focused L1-L4 commits with deterministic and live tests. "
            "That complete state was imported into Saddle and supersedes the branch core patch."
        ),
        "source_main_commits": [
            "38b71131565fc2ff95f30bc1391bbfecd619ae1b",
            "2726ed05927957c6a1b68e18863e73604b395989",
            "34be593e58a9cf1d8a06deaffc8331f476208b2b",
        ],
        "saddle_commits": ["850628da4cffc92fc17e22811377a7c8eece1101"],
        "evidence": [
            evidence(
                "crates/wsf-api/tests/ledger_authz.rs",
                "Tests prove tenant isolation and the explicit global-auditor exception.",
                "async fn receipts_are_tenant_scoped_with_no_cross_tenant_oracle",
                "async fn global_auditor_reads_across_tenants_and_exports_a_verifiable_pack",
            ),
            evidence(
                "crates/wsf-api/src/audit.rs",
                "Auditor enrollment is explicit server-side authority.",
                "pub trait AuditorStore",
            ),
            evidence(
                "crates/wsf-api/src/openapi.json",
                "The public contract documents tenant-scoped receipts and global auditors.",
                "tenant-scoped",
                "global auditors",
            ),
        ],
        "verification": ["cargo test -p wsf-api --test ledger_authz"],
    },
    "e2ddf278f579be7bf95d9f537b0e93fed33f81df": {
        "behavior": "AF-006 fresh signed revocation consumption on WSF privileged paths.",
        "disposition": "superseded",
        "rationale": (
            "Approved source main implemented anti-rollback snapshot storage, complete "
            "revocation predicates, fail-closed seal/broker consumers, and an end-to-end live "
            "gate. Later Saddle gateway and bridge work also requires current revocation."
        ),
        "source_main_commits": [
            "76f1ca50a8d925bd3e6aea9176539861f34f1e28",
            "8c2d4eaf5fafd68e4e9929da5b80b6415a887473",
            "116b0f1c3846cada458e290a492b49973fa97794",
            "bcd332f2c5f3f3c33eb0daf70adabe77518260fb",
            "e28494241a0cddbe415a576ad4a3352efdd47f18",
        ],
        "saddle_commits": [
            "850628da4cffc92fc17e22811377a7c8eece1101",
            "ef8b27236e1e4f24b27fbad9b249703299291bfc",
        ],
        "evidence": [
            evidence(
                "crates/fabric-revocation/src/lib.rs",
                "The snapshot store verifies signatures and rejects rollback.",
                "pub struct MonotonicRevocationStore",
                "Rollback",
            ),
            evidence(
                "crates/wsf-api/tests/live_revocation.rs",
                "The live gate proves propagation to seal and broker consumers.",
                "async fn revocation_propagates_to_seal_and_broker_end_to_end",
            ),
            evidence(
                "crates/wsf-broker/src/lib.rs",
                "Broker exchange consumes the current revocation snapshot.",
                "revoked (tenant)",
            ),
        ],
        "verification": [
            "cargo test -p fabric-revocation",
            "cargo test -p wsf-broker --lib",
            "cargo test -p wsf-seal --lib",
        ],
    },
    "f30164f01835c369b39552ae5bb760254330a319": {
        "behavior": "AF-005 MAI production-vault readiness and storage implementation.",
        "disposition": "exclusion",
        "rationale": (
            "The implementation paths are mai-api/mai-core/mai-vault appliance concerns and "
            "are outside Saddle's selected WSF+AOG source closure. Only the historical "
            "finding/devlog records were selected. Importing this patch would expand scope and "
            "reintroduce excluded MAI runtime ownership, so it remains external provenance."
        ),
        "source_main_commits": [],
        "saddle_commits": [],
        "evidence": [
            evidence(
                "test-evidence/saddle/SAD-HIST-01/history-inventory.json",
                "The frozen inventory records only two historical-evidence paths as selected.",
                '"sha": "f30164f01835c369b39552ae5bb760254330a319"',
                '"out-of-scope-no-match": 3',
            ),
            evidence(
                "PLANNING/SADDLE-SOURCE-AND-RENAME-MANIFEST.md",
                "The source boundary keeps appliance/MAI runtime ownership outside Saddle.",
                "out-of-scope",
            ),
        ],
        "verification": [
            "python tools/verify_saddle_independence.py --root . --evidence-output test-evidence/saddle/SAD-12/independence-gate.json --verify"
        ],
    },
    "fa956e788539594426ab4b9a7e281a68872bf557": {
        "behavior": "Partial quality closure: mock-LLM typing/loopback bind plus M1 documentation.",
        "disposition": "superseded",
        "rationale": (
            "Approved source main independently reviewed the same mock-LLM lint and bind issue, "
            "kept the required cross-container bind with an explicit non-production rationale, "
            "and completed the later quality and Phase X closeout. Saddle imported that result; "
            "the branch loopback default would break the appliance demo network."
        ),
        "source_main_commits": [
            "acd80a8297b3e072174a063d37e073450bde4f93",
            "700cf2b1c08f6c5dce66a2624992500ce50f049f",
        ],
        "saddle_commits": ["93f2d2f7fb9cba29e27a3bf57fe5554a58de97da"],
        "evidence": [
            evidence(
                "deployment/appliance/mock-llm/app.py",
                "The imported helper is typed and documents its intentional container-only bind.",
                "def _send(self, code: int, obj: object) -> None",
                "Binds to all interfaces by design",
                "# noqa: S104",
            ),
            evidence(
                "docs/scans/SECURITY-REMEDIATION-FINDINGS.md",
                "The preserved finding ledger records later complete and deferred states honestly.",
                "AF-005",
                "real ZFS+TPM hardware",
            ),
        ],
        "verification": [
            "python -m py_compile deployment/appliance/mock-llm/app.py",
            "python -m ruff check deployment/appliance/mock-llm/app.py",
        ],
    },
    "92dc928febb49837b71755ccb75a8eeccbe14b2b": {
        "behavior": "OpenAPI reconciliation for authenticated issuance, attenuation, grants, and receipts.",
        "disposition": "transplant",
        "rationale": (
            "Current Saddle code enforced the hardened routes, but its OpenAPI document still "
            "described the pre-hardening issuance, attenuation, and credential contracts. "
            "Commit 1caaa4f adapts the still-required intent to current DTOs, preserves the "
            "field/value receipt query, documents auditor export, and adds a contract test."
        ),
        "source_main_commits": [],
        "saddle_commits": ["1caaa4f8d160bece69aaf0416d57d573e73b2a1d"],
        "evidence": [
            evidence(
                "crates/wsf-api/src/openapi.json",
                "The adapted contract states authenticated issuance, bounded grants, and scoped receipts.",
                "authenticated principal",
                "tenant-scoped named grant",
                "global auditors",
            ),
            evidence(
                "tools/ci_surface_tests/test_wsf_openapi.py",
                "The CI contract locks the adapted authority descriptions to current DTOs.",
                "92dc928febb49837b71755ccb75a8eeccbe14b2b",
                "def test_privileged_routes_describe_their_authority_boundaries",
            ),
        ],
        "verification": [
            "python -m json.tool crates/wsf-api/src/openapi.json",
            "python -m unittest tools.ci_surface_tests.test_wsf_openapi -v",
            "cargo test -p wsf-api --test ledger_authz",
        ],
    },
    "8f27bbea2d04be3c9614eeeeac67bd0315b836a2": {
        "behavior": "Mighty Eel RC1.2 release-build, bundle, and outside-tester documentation.",
        "disposition": "archive",
        "rationale": (
            "The commit is product-release evidence for a different MAI/Lamprey bundle, not "
            "WSF, AOG, or Saddle behavior. All four paths were absent from the approved Saddle "
            "seed and selected closure. The sanitized historical object should be preserved in "
            "SAD-HIST-04, but its stale binaries, hashes, and tester instructions must not be "
            "presented as a Saddle release."
        ),
        "source_main_commits": [],
        "saddle_commits": [],
        "evidence": [
            evidence(
                "test-evidence/saddle/SAD-HIST-01/history-inventory.json",
                "The frozen inventory classifies all four changed paths as absent at the seed.",
                '"sha": "8f27bbea2d04be3c9614eeeeac67bd0315b836a2"',
                '"absent-at-seed": 4',
            ),
            evidence(
                "PLANNING/SADDLE-HISTORY-RECONCILIATION-ADDENDUM.md",
                "Historical release objects belong only under the protected archive namespace.",
                "history/mighty-eel/",
            ),
        ],
        "verification": [],
    },
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git(repo: Path, *args: str) -> bytes:
    command = [
        "git",
        "-c",
        f"safe.directory={repo.resolve()}",
        "-c",
        "core.quotePath=false",
        "-C",
        str(repo.resolve()),
        *args,
    ]
    completed = subprocess.run(command, check=False, capture_output=True)
    if completed.returncode != 0:
        fail(
            f"{' '.join(command)} failed with {completed.returncode}: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    return completed.stdout


def commit_record(repo: Path, commit_id: str) -> dict[str, str]:
    object_bytes = git(repo, "cat-file", "commit", commit_id)
    subject = git(repo, "show", "-s", "--format=%s", commit_id).decode().strip()
    return {
        "commit_object_sha256": sha256_bytes(object_bytes),
        "sha": git(repo, "rev-parse", f"{commit_id}^{{commit}}").decode().strip(),
        "subject": subject,
    }


def require_ancestor(repo: Path, ancestor: str, descendant: str, label: str) -> None:
    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={repo.resolve()}",
            "-C",
            str(repo.resolve()),
            "merge-base",
            "--is-ancestor",
            ancestor,
            descendant,
        ],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        fail(f"{label} commit {ancestor} is not reachable from {descendant}")


def validate_evidence(root: Path, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    for record in records:
        path = root / record["path"]
        if not path.is_file():
            fail(f"evidence path does not exist: {record['path']}")
        content = path.read_text(encoding="utf-8")
        for anchor in record["anchors"]:
            if anchor not in content:
                fail(f"evidence anchor {anchor!r} is absent from {record['path']}")
        validated.append({**record, "sha256": sha256_file(path)})
    return validated


def build_reconciliation(
    *, root: Path, source_repo: Path, inventory_path: Path
) -> dict[str, Any]:
    inventory_bytes = inventory_path.read_bytes()
    inventory = json.loads(inventory_bytes)
    if inventory.get("status") != "pass" or inventory.get("prompt") != "SAD-HIST-01":
        fail("input is not a passing SAD-HIST-01 inventory")
    if inventory.get("source", {}).get("approved_main_sha") != APPROVED_SOURCE_MAIN:
        fail("inventory is not pinned to the approved source main")

    queue = {
        record["sha"]: record
        for record in inventory.get("commits", [])
        if record.get("migration_disposition") == "review-required"
    }
    if set(queue) != set(DECISIONS):
        missing = sorted(set(queue) - set(DECISIONS))
        extra = sorted(set(DECISIONS) - set(queue))
        fail(f"decision table does not exactly cover review queue; missing={missing}, extra={extra}")

    source_main = git(source_repo, "rev-parse", f"{APPROVED_SOURCE_MAIN}^{{commit}}").decode().strip()
    if source_main != APPROVED_SOURCE_MAIN:
        fail("source repository does not contain the approved main commit")
    require_ancestor(root, HISTORY_BASE, "HEAD", "Saddle history base")

    reviews: list[dict[str, Any]] = []
    for commit_id in sorted(queue):
        inventory_record = queue[commit_id]
        decision = DECISIONS[commit_id]
        disposition = decision["disposition"]
        if disposition not in ALLOWED_DISPOSITIONS:
            fail(f"invalid disposition {disposition!r} for {commit_id}")
        if disposition == "superseded" and not (
            decision["source_main_commits"] or decision["saddle_commits"]
        ):
            fail(f"superseded decision lacks controlling commits: {commit_id}")
        if disposition == "transplant" and not decision["saddle_commits"]:
            fail(f"transplant decision lacks a focused Saddle commit: {commit_id}")

        source = commit_record(source_repo, commit_id)
        if source["subject"] != inventory_record["subject"]:
            fail(f"source subject drift for {commit_id}")
        patch = git(
            source_repo,
            "show",
            "--format=",
            "--binary",
            "--full-index",
            "--no-renames",
            commit_id,
        )
        changed_paths = sorted(
            line
            for line in git(
                source_repo,
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                "--no-renames",
                commit_id,
            )
            .decode("utf-8", "replace")
            .splitlines()
            if line
        )
        if changed_paths != inventory_record["changed_paths"]:
            fail(f"changed-path drift for {commit_id}")

        source_main_records = []
        for superseding in decision["source_main_commits"]:
            require_ancestor(
                source_repo,
                superseding,
                APPROVED_SOURCE_MAIN,
                "source-main superseding",
            )
            source_main_records.append(commit_record(source_repo, superseding))

        saddle_records = []
        for superseding in decision["saddle_commits"]:
            require_ancestor(root, superseding, "HEAD", "Saddle superseding")
            saddle_records.append(commit_record(root, superseding))

        reviews.append(
            {
                "behavior": decision["behavior"],
                "changed_paths": changed_paths,
                "disposition": disposition,
                "evidence": validate_evidence(root, decision["evidence"]),
                "inventory_patch_id": inventory_record.get("patch_id"),
                "manifest_disposition_counts": inventory_record[
                    "manifest_disposition_counts"
                ],
                "published_refs": inventory_record["published_refs"],
                "rationale": decision["rationale"],
                "saddle_commits": saddle_records,
                "source": source,
                "source_main_commits": source_main_records,
                "source_patch_sha256": sha256_bytes(patch),
                "verification": decision["verification"],
            }
        )

    counts = Counter(record["disposition"] for record in reviews)
    generator = root / "tools" / "reconcile_saddle_history_non_main.py"
    return {
        "generator": {
            "path": generator.relative_to(root).as_posix(),
            "sha256": sha256_file(generator),
        },
        "inputs": {
            "approved_source_main": APPROVED_SOURCE_MAIN,
            "history_base": HISTORY_BASE,
            "inventory_path": inventory_path.relative_to(root).as_posix(),
            "inventory_sha256": sha256_bytes(inventory_bytes),
        },
        "prompt": "SAD-HIST-03",
        "reviews": reviews,
        "schema_version": SCHEMA,
        "status": "pass",
        "summary": {
            "disposition_counts": dict(sorted(counts.items())),
            "review_required_commit_count": len(reviews),
            "transplant_commit_count": counts.get("transplant", 0),
            "unreviewed_commit_count": 0,
        },
    }


def canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--source-repo", type=Path, required=True)
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path("test-evidence/saddle/SAD-HIST-01/history-inventory.json"),
    )
    parser.add_argument(
        "--evidence-output",
        type=Path,
        default=Path("test-evidence/saddle/SAD-HIST-03/non-main-reconciliation.json"),
    )
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def resolve_under(root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    inventory_path = resolve_under(root, args.inventory)
    evidence_output = resolve_under(root, args.evidence_output)
    try:
        evidence_output.relative_to(root)
        rendered = canonical(
            build_reconciliation(
                root=root,
                source_repo=args.source_repo.resolve(),
                inventory_path=inventory_path,
            )
        )
        if args.verify:
            if not evidence_output.is_file():
                fail(f"evidence file does not exist: {evidence_output}")
            if evidence_output.read_text(encoding="utf-8") != rendered:
                fail("reconciliation evidence is not byte-for-byte reproducible")
        else:
            evidence_output.parent.mkdir(parents=True, exist_ok=True)
            evidence_output.write_text(rendered, encoding="utf-8", newline="\n")
    except (ReconciliationError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"SAD-HIST-03 reconciliation failed: {error}", file=sys.stderr)
        return 1
    print("SAD-HIST-03 non-main reconciliation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
