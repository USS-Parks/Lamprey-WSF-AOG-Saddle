use std::collections::BTreeSet;

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
use mai_compliance::{AggregateDecision, Destination, ModuleId};
use saddle_bridge::*;

#[derive(Clone, Copy)]
enum PolicyMode {
    Allow,
    Deny,
    Fence,
}

struct TestPolicy(PolicyMode);

struct FailedReplayStore;

impl ReplayStore for FailedReplayStore {
    fn consume(
        &mut self,
        _class: ReplayClass,
        _tenant_id: &str,
        _lineage: &str,
        _nonce: &str,
    ) -> Result<bool, String> {
        Err("backend unavailable".into())
    }
}

impl AogPolicy for TestPolicy {
    fn evaluate(&self, _input: &PolicyInput<'_>) -> AggregateDecision {
        AggregateDecision {
            allowed: matches!(self.0, PolicyMode::Allow),
            route: Some(Destination::Local),
            flags: Vec::new(),
            reasons: Vec::new(),
            modules_applied: if matches!(self.0, PolicyMode::Fence) {
                Vec::new()
            } else {
                vec![ModuleId::Hipaa]
            },
        }
    }
}

fn time(offset: i64) -> chrono::DateTime<Utc> {
    Utc.timestamp_opt(1_752_000_000 + offset, 0).unwrap()
}

fn csv(values: &[&str]) -> BTreeSet<String> {
    values.iter().map(|value| (*value).to_owned()).collect()
}

fn token(signer: &RustCryptoMlDsa87) -> TrustToken {
    issue(
        TrustToken {
            token_id: "child-token".into(),
            issued_at: time(-60).to_rfc3339(),
            expires_at: time(900).to_rfc3339(),
            issuer: "wsf-bridge".into(),
            trust_bundle_version: "bundle-v2".into(),
            tenant_id: "tenant-a".into(),
            subject_id: None,
            subject_hash: "subject-hash".into(),
            service_identity: Some("saddled".into()),
            identity_id: None,
            roles: vec!["operator".into()],
            compliance_scopes: Vec::new(),
            allowed_routes: vec![Route::LocalOnly],
            allowed_models: vec!["model-a".into(), "model-b".into()],
            max_data_classification: Classification::Restricted,
            country: Some("US".into()),
            person_type: Some("us_person".into()),
            offline_mode: false,
            revocation_status: RevocationStatus::Valid,
            budget: Some(Budget {
                token_cap: 1_000,
                tokens_spent: 100,
                usd_cap_cents: 500,
                usd_spent_cents: 50,
                tool_call_cap: 10,
                tool_calls_spent: 1,
            }),
            attenuation: Attenuation {
                parent_id: Some("root-token".into()),
                root_id: Some("root-token".into()),
                depth: 1,
                ancestor_ids: vec!["root-token".into()],
                caveats: vec![
                    Caveat {
                        caveat_type: CaveatType::ResourcePrefix,
                        value: "workloads/".into(),
                    },
                    Caveat {
                        caveat_type: CaveatType::ToolAllowlist,
                        value: "search,calculator".into(),
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

fn context(tenant: &str) -> VerifiedRequestContext {
    let principal = WsfPrincipal::establish(
        AuthenticatedFacts {
            principal_id: "spiffe://saddle/saddled".into(),
            kind: IdentityKind::Workload,
            tenant_id: tenant.into(),
            subject_hash: "subject-hash".into(),
            service_identity: Some("saddled".into()),
            roles: vec!["operator".into()],
            token_lineage: Some("root-token".into()),
            auth_strength: AuthStrength::MutualTls,
            audience: Audience::Saddle,
        },
        "correlation-1",
        time(-30).to_rfc3339(),
    );
    VerifiedRequestContext::establish(
        principal,
        RequestOperation::SaddleAdmission,
        CanonicalResource::resolved("Workload", "workload-a", Some(tenant.into())).unwrap(),
    )
    .unwrap()
}

fn revocation(signer: &RustCryptoMlDsa87, sequence: u64) -> MonotonicRevocationStore {
    let snapshot = RevocationSnapshot::new(
        format!("rev-{sequence}"),
        time(-120).to_rfc3339(),
        time(600).to_rfc3339(),
    )
    .with_sequence(sequence);
    let snapshot = sign_revocation(snapshot, signer).unwrap();
    let mut store = MonotonicRevocationStore::new();
    store
        .advance(snapshot, &MlDsa87Verifier, signer.public_key())
        .unwrap();
    store
}

fn verified<P: AogPolicy>(
    issuer: &mut GrantIssuer<P>,
    signer: &RustCryptoMlDsa87,
    token: &TrustToken,
    nonce: &str,
) -> VerifiedSaddleRequest {
    issuer
        .verify_request(
            context("tenant-a"),
            token,
            nonce,
            time(0),
            &MlDsa87Verifier,
            signer.public_key(),
            "bundle-v2",
            &revocation(signer, 7),
        )
        .unwrap()
}

fn receipt(id: &str) -> ReceiptIntentSpec {
    ReceiptIntentSpec {
        receipt_id: id.into(),
        request_digest: format!("digest-{id}"),
    }
}

fn admission_spec() -> AdmissionSpec {
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
            tools: csv(&["search"]),
        },
        receipt: receipt("admission"),
    }
}

fn grant_chain(
    issuer: &mut GrantIssuer<TestPolicy>,
    request: &VerifiedSaddleRequest,
    store: &MonotonicRevocationStore,
) -> RuntimeGrant {
    let admission = issuer
        .issue_admission(request, admission_spec(), time(0), store)
        .unwrap();
    let placement = issuer
        .issue_placement(
            request,
            &admission,
            PlacementSpec {
                placement_uid: "placement-uid".into(),
                workload_uid: "workload-uid".into(),
                generation: 3,
                eligible_nodes: csv(&["node-a", "node-b"]),
                resource_reservation: csv(&["cpu=4", "memory=8Gi"]),
                trust_constraints: csv(&["tpm", "confidential-compute"]),
                expires_at: time(400).to_rfc3339(),
                receipt: receipt("placement"),
            },
            time(0),
            store,
        )
        .unwrap();
    issuer
        .issue_runtime(
            request,
            &placement,
            RuntimeSpec {
                node_identity: "node-a".into(),
                workload_digest: "sha256:workload".into(),
                runtime_class: "confidential".into(),
                aog_permissions: csv(&["model-a", "search"]),
                budget: GrantBudget {
                    tokens: 500,
                    usd_cents: 200,
                    tool_calls: 4,
                },
                expires_at: time(300).to_rfc3339(),
                receipt: receipt("runtime"),
            },
            time(0),
            store,
        )
        .unwrap()
}

#[test]
fn exact_grant_chain_is_serialize_only_and_preserves_lineage() {
    let signer = RustCryptoMlDsa87::generate("test-key").unwrap();
    let token = token(&signer);
    let mut issuer = GrantIssuer::new(TestPolicy(PolicyMode::Allow));
    let request = verified(&mut issuer, &signer, &token, "request-nonce");
    let store = revocation(&signer, 7);
    let runtime = grant_chain(&mut issuer, &request, &store);
    let action_spec = ActionSpec {
        kind: ActionKind::Model,
        action: "model-a".into(),
        arguments_digest: "sha256:args".into(),
        request_digest: "sha256:request".into(),
        destination: "local".into(),
        budget: GrantBudget {
            tokens: 100,
            usd_cents: 20,
            tool_calls: 0,
        },
        nonce: "action-nonce".into(),
        expires_at: time(200).to_rfc3339(),
        receipt: receipt("action"),
    };
    let action = issuer
        .issue_action(&request, &runtime, action_spec.clone(), time(0), &store)
        .unwrap();

    assert_eq!(action.lineage(), "root-token");
    assert_eq!(action.revocation_sequence(), 7);
    assert_eq!(action.tenant_id(), "tenant-a");
    let wire = serde_json::to_value(action).unwrap();
    assert_eq!(wire["contract_version"], CONTRACT_VERSION);
    assert_eq!(wire["action"], "model-a");
    assert_eq!(
        issuer.issue_action(&request, &runtime, action_spec, time(0), &store),
        Err(BridgeError::Replay)
    );
}

#[test]
fn property_every_authority_axis_only_narrows() {
    let signer = RustCryptoMlDsa87::generate("test-key").unwrap();
    let token = token(&signer);
    let mut issuer = GrantIssuer::new(TestPolicy(PolicyMode::Allow));
    let request = verified(&mut issuer, &signer, &token, "narrowing");
    let store = revocation(&signer, 7);

    for extra in ["model-c", "model-d", "model-e"] {
        let mut spec = admission_spec();
        spec.scope.models.insert(extra.into());
        assert_eq!(
            issuer.issue_admission(&request, spec, time(0), &store),
            Err(BridgeError::ScopeWidens)
        );
    }
    for seconds in [901, 1_000, 10_000] {
        let mut spec = admission_spec();
        spec.expires_at = time(seconds).to_rfc3339();
        assert_eq!(
            issuer.issue_admission(&request, spec, time(0), &store),
            Err(BridgeError::ExpiryWidens)
        );
    }

    let runtime = grant_chain(&mut issuer, &request, &store);
    for budget in [
        GrantBudget {
            tokens: 501,
            usd_cents: 200,
            tool_calls: 4,
        },
        GrantBudget {
            tokens: 500,
            usd_cents: 201,
            tool_calls: 4,
        },
        GrantBudget {
            tokens: 500,
            usd_cents: 200,
            tool_calls: 5,
        },
    ] {
        let error = issuer.issue_action(
            &request,
            &runtime,
            ActionSpec {
                kind: ActionKind::Model,
                action: "model-a".into(),
                arguments_digest: "args".into(),
                request_digest: "request".into(),
                destination: "local".into(),
                budget,
                nonce: format!("budget-{budget:?}"),
                expires_at: time(200).to_rfc3339(),
                receipt: receipt("budget"),
            },
            time(0),
            &store,
        );
        assert_eq!(error, Err(BridgeError::BudgetWidens));
    }
}

#[test]
fn tenant_and_nonce_properties_isolate_authority_and_resist_replay() {
    let signer = RustCryptoMlDsa87::generate("test-key").unwrap();
    let token = token(&signer);
    let mut issuer = GrantIssuer::new(TestPolicy(PolicyMode::Allow));
    let store = revocation(&signer, 8);

    for tenant in ["tenant-b", "tenant-c", "tenant-d"] {
        let result = issuer.verify_request(
            context(tenant),
            &token,
            format!("nonce-{tenant}"),
            time(0),
            &MlDsa87Verifier,
            signer.public_key(),
            "bundle-v2",
            &store,
        );
        assert_eq!(result, Err(BridgeError::TenantIsolation));
    }

    let first = issuer.verify_request(
        context("tenant-a"),
        &token,
        "same-nonce",
        time(0),
        &MlDsa87Verifier,
        signer.public_key(),
        "bundle-v2",
        &store,
    );
    assert!(first.is_ok());
    let replay = issuer.verify_request(
        context("tenant-a"),
        &token,
        "same-nonce",
        time(0),
        &MlDsa87Verifier,
        signer.public_key(),
        "bundle-v2",
        &store,
    );
    assert_eq!(replay, Err(BridgeError::Replay));

    let mut unavailable =
        GrantIssuer::with_replay_store(TestPolicy(PolicyMode::Allow), FailedReplayStore);
    let failed = unavailable.verify_request(
        context("tenant-a"),
        &token,
        "store-failure",
        time(0),
        &MlDsa87Verifier,
        signer.public_key(),
        "bundle-v2",
        &store,
    );
    assert_eq!(
        failed,
        Err(BridgeError::ReplayUnavailable("backend unavailable".into()))
    );
}

#[test]
fn deny_wins_and_missing_policy_modules_fence_every_grant_stage() {
    let signer = RustCryptoMlDsa87::generate("test-key").unwrap();
    let token = token(&signer);

    let mut deny = GrantIssuer::new(TestPolicy(PolicyMode::Deny));
    let request = verified(&mut deny, &signer, &token, "deny");
    let store = revocation(&signer, 7);
    assert_eq!(
        deny.issue_admission(&request, admission_spec(), time(0), &store),
        Err(BridgeError::PolicyDenied)
    );

    let mut fence = GrantIssuer::new(TestPolicy(PolicyMode::Fence));
    let request = verified(&mut fence, &signer, &token, "fence");
    assert_eq!(
        fence.issue_admission(&request, admission_spec(), time(0), &store),
        Err(BridgeError::PolicyFenced)
    );
}

#[test]
fn absent_expired_and_revoked_state_fail_closed() {
    let signer = RustCryptoMlDsa87::generate("test-key").unwrap();
    let token = token(&signer);
    let mut issuer = GrantIssuer::new(TestPolicy(PolicyMode::Allow));
    let request = verified(&mut issuer, &signer, &token, "transition-check");

    let stale = revocation(&signer, 6);
    let result = issuer.issue_admission(&request, admission_spec(), time(0), &stale);
    assert!(matches!(result, Err(BridgeError::Revocation(_))));

    let empty = MonotonicRevocationStore::new();
    let result = issuer.verify_request(
        context("tenant-a"),
        &token,
        "empty",
        time(0),
        &MlDsa87Verifier,
        signer.public_key(),
        "bundle-v2",
        &empty,
    );
    assert!(matches!(result, Err(BridgeError::Revocation(_))));

    let mut snapshot =
        RevocationSnapshot::new("revoked", time(-120).to_rfc3339(), time(600).to_rfc3339())
            .with_sequence(9);
    snapshot.revoked_tokens.push(token.token_id.clone());
    let snapshot = sign_revocation(snapshot, &signer).unwrap();
    let mut revoked = MonotonicRevocationStore::new();
    revoked
        .advance(snapshot, &MlDsa87Verifier, signer.public_key())
        .unwrap();
    let transition = issuer.issue_admission(&request, admission_spec(), time(0), &revoked);
    assert!(matches!(transition, Err(BridgeError::Revocation(_))));
    let result = issuer.verify_request(
        context("tenant-a"),
        &token,
        "revoked",
        time(0),
        &MlDsa87Verifier,
        signer.public_key(),
        "bundle-v2",
        &revoked,
    );
    assert!(matches!(result, Err(BridgeError::Revocation(_))));

    let expired = revocation(&signer, 10);
    let result = issuer.verify_request(
        context("tenant-a"),
        &token,
        "expired",
        time(601),
        &MlDsa87Verifier,
        signer.public_key(),
        "bundle-v2",
        &expired,
    );
    assert!(matches!(result, Err(BridgeError::Revocation(_))));
}
