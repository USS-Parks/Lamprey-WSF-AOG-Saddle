use std::collections::{BTreeSet, HashSet};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};

use chrono::{TimeZone, Utc};
use fabric_contracts::{
    Attenuation, Audience, AuthStrength, AuthenticatedFacts, Budget, CanonicalResource, Caveat,
    CaveatType, Classification, IdentityKind, RequestOperation, RevocationStatus, Route, Signature,
    TrustToken, VerifiedRequestContext, WsfPrincipal,
};
use fabric_crypto::Signer;
use fabric_crypto::providers::{MlDsa87Verifier, RustCryptoMlDsa87};
use fabric_revocation::{MonotonicRevocationStore, RevocationSnapshot, sign as sign_revocation};
use fabric_token::issue;
use fabric_token::spend::ReservationLedger;
use mai_compliance::{AggregateDecision, Destination, ModuleId};
use saddle_bridge::*;
use wsf_ledger::Ledger;

struct AllowPolicy;

impl AogPolicy for AllowPolicy {
    fn evaluate(&self, _input: &PolicyInput<'_>) -> AggregateDecision {
        AggregateDecision {
            allowed: true,
            route: Some(Destination::Local),
            flags: Vec::new(),
            reasons: Vec::new(),
            modules_applied: vec![ModuleId::Hipaa],
        }
    }
}

#[derive(Clone)]
struct LedgerSink {
    ledger: Arc<Mutex<Ledger>>,
    receipt_ids: Arc<Mutex<HashSet<String>>>,
    fail: bool,
    empty_proof: bool,
}

impl ActionReceiptSink for LedgerSink {
    fn commit_authorization(
        &mut self,
        receipt: &ActionAuthorizationReceipt,
    ) -> Result<String, String> {
        if self.fail {
            return Err("ledger unavailable".to_owned());
        }
        if !self
            .receipt_ids
            .lock()
            .expect("receipt id lock")
            .insert(receipt.receipt_id().to_owned())
        {
            return Err("duplicate receipt id".to_owned());
        }
        let value = serde_json::to_value(receipt).map_err(|error| error.to_string())?;
        let proof = self
            .ledger
            .lock()
            .expect("ledger lock")
            .ingest("saddle-action", value)
            .map_err(|error| error.to_string())?;
        Ok(if self.empty_proof {
            String::new()
        } else {
            proof
        })
    }
}

type TestGate = ActionGate<AllowPolicy, InMemoryReplayStore, LedgerSink>;

struct Fixture {
    signer: RustCryptoMlDsa87,
    request: VerifiedSaddleRequest,
    runtime: RuntimeGrant,
    revocation: MonotonicRevocationStore,
    gate: TestGate,
    ledger: Arc<Mutex<Ledger>>,
}

fn time(offset: i64) -> chrono::DateTime<Utc> {
    Utc.timestamp_opt(1_752_000_000 + offset, 0).unwrap()
}

fn csv(values: &[&str]) -> BTreeSet<String> {
    values.iter().map(|value| (*value).to_owned()).collect()
}

fn token(signer: &RustCryptoMlDsa87, tenant: &str, token_id: &str, root: &str) -> TrustToken {
    issue(
        TrustToken {
            token_id: token_id.into(),
            issued_at: time(-60).to_rfc3339(),
            expires_at: time(900).to_rfc3339(),
            issuer: "wsf-bridge".into(),
            trust_bundle_version: "bundle-v2".into(),
            tenant_id: tenant.into(),
            subject_id: None,
            subject_hash: format!("subject-{tenant}"),
            service_identity: Some("saddle-aog-runtime".into()),
            identity_id: None,
            roles: vec!["operator".into()],
            compliance_scopes: Vec::new(),
            allowed_routes: vec![Route::LocalOnly],
            allowed_models: vec!["model-a".into()],
            max_data_classification: Classification::Restricted,
            country: Some("US".into()),
            person_type: Some("us_person".into()),
            offline_mode: false,
            revocation_status: RevocationStatus::Valid,
            budget: Some(Budget {
                token_cap: 1_000,
                tokens_spent: 0,
                usd_cap_cents: 500,
                usd_spent_cents: 0,
                tool_call_cap: 10,
                tool_calls_spent: 0,
            }),
            attenuation: Attenuation {
                parent_id: Some(root.into()),
                root_id: Some(root.into()),
                depth: 1,
                ancestor_ids: vec![root.into()],
                caveats: vec![
                    Caveat {
                        caveat_type: CaveatType::ResourcePrefix,
                        value: "workloads/".into(),
                    },
                    Caveat {
                        caveat_type: CaveatType::ToolAllowlist,
                        value: "search,restart".into(),
                    },
                ],
            },
            signature: Signature {
                alg: String::new(),
                key_id: String::new(),
                value: String::new(),
            },
        },
        signer,
    )
    .unwrap()
}

fn context(tenant: &str, root: &str) -> VerifiedRequestContext {
    let principal = WsfPrincipal::establish(
        AuthenticatedFacts {
            principal_id: format!("spiffe://saddle/{tenant}/runtime"),
            kind: IdentityKind::Workload,
            tenant_id: tenant.into(),
            subject_hash: format!("subject-{tenant}"),
            service_identity: Some("saddle-aog-runtime".into()),
            roles: vec!["operator".into()],
            token_lineage: Some(root.into()),
            auth_strength: AuthStrength::MutualTls,
            audience: Audience::Saddle,
        },
        format!("correlation-{tenant}"),
        time(-30).to_rfc3339(),
    );
    VerifiedRequestContext::establish(
        principal,
        RequestOperation::SaddleAdmission,
        CanonicalResource::resolved("Workload", "workload-a", Some(tenant.into())).unwrap(),
    )
    .unwrap()
}

fn signed_snapshot(
    signer: &RustCryptoMlDsa87,
    sequence: u64,
    revoked_token: Option<&str>,
) -> RevocationSnapshot {
    let mut snapshot = RevocationSnapshot::new(
        format!("sad34-rev-{sequence}"),
        time(-120).to_rfc3339(),
        time(600).to_rfc3339(),
    )
    .with_sequence(sequence);
    if let Some(token_id) = revoked_token {
        snapshot.revoked_tokens.push(token_id.to_owned());
    }
    sign_revocation(snapshot, signer).unwrap()
}

fn revocation(signer: &RustCryptoMlDsa87) -> MonotonicRevocationStore {
    let mut store = MonotonicRevocationStore::new();
    store
        .advance(
            signed_snapshot(signer, 7, None),
            &MlDsa87Verifier,
            signer.public_key(),
        )
        .unwrap();
    store
}

fn receipt(id: &str, request_digest: &str) -> ReceiptIntentSpec {
    ReceiptIntentSpec {
        receipt_id: id.into(),
        request_digest: request_digest.into(),
    }
}

fn verified(
    issuer: &mut GrantIssuer<AllowPolicy>,
    signer: &RustCryptoMlDsa87,
    token: &TrustToken,
    tenant: &str,
    root: &str,
    nonce: &str,
    revocation: &MonotonicRevocationStore,
) -> VerifiedSaddleRequest {
    issuer
        .verify_request(
            context(tenant, root),
            token,
            nonce,
            time(0),
            &MlDsa87Verifier,
            signer.public_key(),
            "bundle-v2",
            revocation,
        )
        .unwrap()
}

fn runtime(
    issuer: &mut GrantIssuer<AllowPolicy>,
    request: &VerifiedSaddleRequest,
    revocation: &MonotonicRevocationStore,
) -> RuntimeGrant {
    let admission = issuer
        .issue_admission(
            request,
            AdmissionSpec {
                verb: AdmissionVerb::Create,
                object_uid: "workload-uid".into(),
                object_name: "workload-a".into(),
                tenant_id: "tenant-a".into(),
                mutation_digest: "mutation-digest".into(),
                expires_at: time(500).to_rfc3339(),
                scope: CapabilityScope {
                    resource_prefixes: csv(&["workloads/"]),
                    models: csv(&["model-a"]),
                    tools: csv(&["search", "restart"]),
                },
                receipt: receipt("admission", "mutation-digest"),
            },
            time(0),
            revocation,
        )
        .unwrap();
    let placement = issuer
        .issue_placement(
            request,
            &admission,
            PlacementSpec {
                placement_uid: "placement-uid".into(),
                workload_uid: "workload-uid".into(),
                generation: 1,
                eligible_nodes: csv(&["node-a"]),
                resource_reservation: csv(&["cpu=1"]),
                trust_constraints: csv(&["tpm"]),
                expires_at: time(400).to_rfc3339(),
                receipt: receipt("placement", "placement-digest"),
            },
            time(0),
            revocation,
        )
        .unwrap();
    issuer
        .issue_runtime(
            request,
            &placement,
            RuntimeSpec {
                node_identity: "node-a".into(),
                workload_digest: "sha256:runtime".into(),
                runtime_class: "aog-governed".into(),
                aog_permissions: csv(&["model-a", "search", "restart"]),
                budget: GrantBudget {
                    tokens: 500,
                    usd_cents: 200,
                    tool_calls: 5,
                },
                expires_at: time(300).to_rfc3339(),
                receipt: receipt("runtime", "sha256:runtime"),
            },
            time(0),
            revocation,
        )
        .unwrap()
}

fn build_fixture(fail_receipts: bool, empty_proof: bool) -> Fixture {
    let signer = RustCryptoMlDsa87::generate("sad34-anchor").unwrap();
    let revocation = revocation(&signer);
    let root = "root-a";
    let trust_token = token(&signer, "tenant-a", "token-a", root);
    let mut issuer = GrantIssuer::new(AllowPolicy);
    let request = verified(
        &mut issuer,
        &signer,
        &trust_token,
        "tenant-a",
        root,
        "request-a",
        &revocation,
    );
    let runtime = runtime(&mut issuer, &request, &revocation);
    let ledger = Arc::new(Mutex::new(Ledger::new(Arc::new(
        RustCryptoMlDsa87::generate("sad34-ledger").unwrap(),
    ))));
    let sink = LedgerSink {
        ledger: Arc::clone(&ledger),
        receipt_ids: Arc::new(Mutex::new(HashSet::new())),
        fail: fail_receipts,
        empty_proof,
    };
    Fixture {
        signer,
        request,
        runtime,
        revocation,
        gate: ActionGate::new(issuer, ReservationLedger::new(), sink),
        ledger,
    }
}

fn action(kind: ActionKind, name: &str, nonce: &str, budget: GrantBudget) -> ActionSpec {
    let request_digest = format!("request-{nonce}");
    ActionSpec {
        kind,
        action: name.into(),
        arguments_digest: format!("arguments-{nonce}"),
        request_digest: request_digest.clone(),
        destination: "aog-sink".into(),
        budget,
        nonce: nonce.into(),
        expires_at: time(120).to_rfc3339(),
        receipt: receipt(&format!("receipt-{nonce}"), &request_digest),
    }
}

#[tokio::test]
async fn model_tool_and_control_effects_require_a_precommitted_receipt() {
    let mut fixture = build_fixture(false, false);
    for (kind, name) in [
        (ActionKind::Model, "model-a"),
        (ActionKind::Tool, "search"),
        (ActionKind::Control, "restart"),
    ] {
        let nonce = format!("{kind:?}").to_lowercase();
        let prepared = fixture
            .gate
            .prepare(
                &fixture.request,
                &fixture.runtime,
                action(
                    kind,
                    name,
                    &nonce,
                    GrantBudget {
                        tokens: 10,
                        usd_cents: 2,
                        tool_calls: 1,
                    },
                ),
                time(0),
                &fixture.revocation,
            )
            .unwrap();
        let expected_receipts = fixture.ledger.lock().expect("ledger lock").len();
        let ledger = Arc::clone(&fixture.ledger);
        let execution = prepared
            .execute(
                &fixture.request,
                time(1),
                &fixture.revocation,
                move |grant| {
                    let observed = grant.kind();
                    async move {
                        assert_eq!(
                            ledger.lock().expect("ledger lock").len(),
                            expected_receipts,
                            "authorization receipt must exist before the effect"
                        );
                        Ok(observed)
                    }
                },
            )
            .await
            .unwrap();
        assert_eq!(execution.value, kind);
        assert!(!execution.receipt_proof.is_empty());
    }
    let ledger = fixture.ledger.lock().expect("ledger lock");
    assert_eq!(ledger.len(), 3);
    ledger.verify().unwrap();
}

#[tokio::test]
async fn replay_and_cross_tenant_token_theft_fail_closed() {
    let mut fixture = build_fixture(false, false);
    let spec = action(
        ActionKind::Tool,
        "search",
        "one-shot",
        GrantBudget {
            tokens: 1,
            usd_cents: 1,
            tool_calls: 1,
        },
    );
    let prepared = fixture
        .gate
        .prepare(
            &fixture.request,
            &fixture.runtime,
            spec.clone(),
            time(0),
            &fixture.revocation,
        )
        .unwrap();
    drop(prepared);
    assert!(matches!(
        fixture.gate.prepare(
            &fixture.request,
            &fixture.runtime,
            spec,
            time(0),
            &fixture.revocation
        ),
        Err(ActionGateError::Bridge(BridgeError::Replay))
    ));

    let mut attacker_issuer = GrantIssuer::new(AllowPolicy);
    let attacker = token(&fixture.signer, "tenant-b", "token-b", "root-b");
    let attacker_request = verified(
        &mut attacker_issuer,
        &fixture.signer,
        &attacker,
        "tenant-b",
        "root-b",
        "request-b",
        &fixture.revocation,
    );
    assert!(matches!(
        fixture.gate.prepare(
            &attacker_request,
            &fixture.runtime,
            action(
                ActionKind::Tool,
                "search",
                "theft",
                GrantBudget {
                    tokens: 1,
                    usd_cents: 1,
                    tool_calls: 1,
                }
            ),
            time(0),
            &fixture.revocation
        ),
        Err(ActionGateError::Bridge(BridgeError::TenantIsolation))
    ));
}

#[tokio::test]
async fn revocation_between_receipt_and_effect_still_blocks_the_effect() {
    let mut fixture = build_fixture(false, false);
    let prepared = fixture
        .gate
        .prepare(
            &fixture.request,
            &fixture.runtime,
            action(
                ActionKind::Control,
                "restart",
                "revocation-race",
                GrantBudget {
                    tokens: 0,
                    usd_cents: 0,
                    tool_calls: 1,
                },
            ),
            time(0),
            &fixture.revocation,
        )
        .unwrap();
    fixture
        .revocation
        .advance(
            signed_snapshot(&fixture.signer, 8, Some("token-a")),
            &MlDsa87Verifier,
            fixture.signer.public_key(),
        )
        .unwrap();
    let effect_ran = Arc::new(AtomicBool::new(false));
    let flag = Arc::clone(&effect_ran);
    let result = prepared
        .execute(
            &fixture.request,
            time(1),
            &fixture.revocation,
            move |_| async move {
                flag.store(true, Ordering::SeqCst);
                Ok(())
            },
        )
        .await;
    assert!(matches!(
        result,
        Err(ActionGateError::Bridge(BridgeError::Revocation(_)))
    ));
    assert!(!effect_ran.load(Ordering::SeqCst));
}

#[tokio::test]
async fn action_expiry_between_receipt_and_effect_still_blocks_the_effect() {
    let mut fixture = build_fixture(false, false);
    let prepared = fixture
        .gate
        .prepare(
            &fixture.request,
            &fixture.runtime,
            action(
                ActionKind::Control,
                "restart",
                "expiry-race",
                GrantBudget {
                    tokens: 0,
                    usd_cents: 0,
                    tool_calls: 1,
                },
            ),
            time(0),
            &fixture.revocation,
        )
        .unwrap();
    let effect_ran = Arc::new(AtomicBool::new(false));
    let flag = Arc::clone(&effect_ran);
    let result = prepared
        .execute(
            &fixture.request,
            time(121),
            &fixture.revocation,
            move |_| async move {
                flag.store(true, Ordering::SeqCst);
                Ok(())
            },
        )
        .await;
    assert!(matches!(
        result,
        Err(ActionGateError::Bridge(BridgeError::ActionExpired))
    ));
    assert!(!effect_ran.load(Ordering::SeqCst));
}

#[test]
fn concurrent_budget_reservations_and_audit_failure_cannot_reach_effect_authority() {
    let mut fixture = build_fixture(false, false);
    let first = fixture
        .gate
        .prepare(
            &fixture.request,
            &fixture.runtime,
            action(
                ActionKind::Model,
                "model-a",
                "budget-one",
                GrantBudget {
                    tokens: 300,
                    usd_cents: 0,
                    tool_calls: 0,
                },
            ),
            time(0),
            &fixture.revocation,
        )
        .unwrap();
    let mut second = action(
        ActionKind::Model,
        "model-a",
        "budget-two",
        GrantBudget {
            tokens: 300,
            usd_cents: 0,
            tool_calls: 0,
        },
    );
    second.destination = "different-aog-sink".into();
    assert!(matches!(
        fixture.gate.prepare(
            &fixture.request,
            &fixture.runtime,
            second,
            time(0),
            &fixture.revocation
        ),
        Err(ActionGateError::Budget(_))
    ));
    drop(first);

    let mut unavailable = build_fixture(true, false);
    assert!(matches!(
        unavailable.gate.prepare(
            &unavailable.request,
            &unavailable.runtime,
            action(
                ActionKind::Tool,
                "search",
                "audit-down",
                GrantBudget {
                    tokens: 1,
                    usd_cents: 1,
                    tool_calls: 1,
                }
            ),
            time(0),
            &unavailable.revocation
        ),
        Err(ActionGateError::Receipt(_))
    ));
    assert_eq!(unavailable.ledger.lock().expect("ledger lock").len(), 0);

    let mut empty_proof = build_fixture(false, true);
    assert!(matches!(
        empty_proof.gate.prepare(
            &empty_proof.request,
            &empty_proof.runtime,
            action(
                ActionKind::Tool,
                "search",
                "empty-proof",
                GrantBudget {
                    tokens: 1,
                    usd_cents: 1,
                    tool_calls: 1,
                }
            ),
            time(0),
            &empty_proof.revocation
        ),
        Err(ActionGateError::Receipt(_))
    ));
}
