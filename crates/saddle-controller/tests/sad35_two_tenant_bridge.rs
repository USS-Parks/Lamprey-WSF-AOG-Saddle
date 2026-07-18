//! SAD-35 live gate: two tenants traverse OpenBao-backed gateway auth, persisted
//! typed placement/runtime handoffs, real gateway/toolproxy effects, control
//! actions, node start, revocation, restart, connectivity loss, and off-host WSF
//! receipt verification without sharing authority.
#![allow(clippy::print_stderr)]

use std::collections::BTreeSet;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;

use aog_gateway::app::{AppState, ModelMap, Target};
use aog_gateway::provider::{
    ChunkStream, CompletionRequest, CompletionResponse, Provider, ProviderError, Registry, Usage,
};
use aog_gateway::{Gateway, GatewayConfig};
use aog_toolproxy::{InvokeContext, MintedCredential, ToolExecutor, ToolProxy};
use async_trait::async_trait;
use axum::Router;
use chrono::Utc;
use fabric_contracts::{
    Attenuation, Audience, AuthStrength, AuthenticatedFacts, Budget, CanonicalResource,
    Classification, IdentityKind, RequestOperation, RevocationStatus, Route, Signature, TrustToken,
    VerifiedRequestContext, WsfPrincipal,
};
use fabric_crypto::Signer;
use fabric_crypto::providers::{MlDsa87Verifier, RustCryptoMlDsa87};
use fabric_revocation::{MonotonicRevocationStore, RevocationSnapshot, sign as sign_revocation};
use futures::stream;
use mai_agent::types::{ToolAccessRole, ToolCall, ToolDefinition, ToolResult};
use mai_compliance::{AggregateDecision, Destination, ModuleId};
use reqwest::{Client, Method};
use saddle_bridge::{
    ActionKind, ActionReceiptSink, ActionSessionRegistry, ActionSpec, AdmissionSpec, AdmissionVerb,
    AogPolicy, CapabilityScope, GrantBudget, GrantIssuer, InMemoryReplayStore,
    PersistedGrantHandoff, PlacementSpec as BridgePlacementSpec, PolicyInput, ReceiptIntentSpec,
    RuntimeActionSession, RuntimeSpec, VerifiedGrantHandoff, VerifiedSaddleRequest,
    WsfLedgerActionSink, persist_grant_handoff, verify_grant_handoff,
};
use saddle_estate::{
    PlacementSpec as EstatePlacementSpec, Resource, SchedulingConstraints, WorkloadKind,
    WorkloadSpec,
};
use saddle_node::driver::{ProcessDriver, WorkloadDriver};
use saddle_node::runtime::{
    RuntimeAssignment, runtime_class, service_identity, start_bridged_authorized, workload_digest,
    workload_role,
};
use saddle_store::{Op, Precondition, RedbBackend, Store};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use tokio::net::TcpListener;
use wsf_bridge::{OpenBaoAuth, OpenBaoConfig};
use wsf_ledger::{Ledger, verify_pack};

const ROLE: &str = "saddle-sad35";
const KV_PREFIX: &str = "kv/data/saddle/sad35/virtual-keys";
const TENANTS: [&str; 2] = ["sad35-tenant-a", "sad35-tenant-b"];
const VKEYS: [&str; 2] = ["vk_sad35_a", "vk_sad35_b"];
const RUNTIME_CLASSES: [&str; 3] = ["aog-gateway", "aog-toolproxy", "saddle-control"];

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

fn openbao_addr() -> Option<String> {
    std::env::var("SADDLE_LIVE_OPENBAO_ADDR")
        .or_else(|_| std::env::var("WSF_OPENBAO_ADDR"))
        .ok()
}

fn root_token() -> String {
    std::env::var("SADDLE_LIVE_OPENBAO_TOKEN")
        .or_else(|_| std::env::var("WSF_OPENBAO_TOKEN"))
        .unwrap_or_else(|_| "root".to_owned())
}

fn handoff_store_path() -> PathBuf {
    std::env::temp_dir().join(format!("saddle-sad35-{}.redb", std::process::id()))
}

async fn bao(
    client: &Client,
    addr: &str,
    token: &str,
    method: Method,
    path: &str,
    body: Option<Value>,
) -> String {
    let mut request = client
        .request(method, format!("{addr}/v1/{path}"))
        .header("X-Vault-Token", token);
    if let Some(body) = body {
        request = request.json(&body);
    }
    request
        .send()
        .await
        .expect("OpenBao request")
        .text()
        .await
        .unwrap_or_default()
}

async fn provision(client: &Client, addr: &str, token: &str) -> (String, String) {
    let _ = bao(
        client,
        addr,
        token,
        Method::POST,
        "sys/auth/approle",
        Some(json!({"type": "approle"})),
    )
    .await;
    let _ = bao(
        client,
        addr,
        token,
        Method::POST,
        "sys/mounts/kv",
        Some(json!({"type": "kv", "options": {"version": "2"}})),
    )
    .await;
    let policy = format!(
        "path \"{KV_PREFIX}/*\" {{ capabilities = [\"create\",\"read\",\"update\",\"delete\"] }}"
    );
    bao(
        client,
        addr,
        token,
        Method::PUT,
        "sys/policies/acl/saddle-sad35",
        Some(json!({"policy": policy})),
    )
    .await;
    bao(
        client,
        addr,
        token,
        Method::POST,
        &format!("auth/approle/role/{ROLE}"),
        Some(json!({"token_policies": "default,saddle-sad35", "token_ttl": "15m"})),
    )
    .await;
    let role: Value = serde_json::from_str(
        &bao(
            client,
            addr,
            token,
            Method::GET,
            &format!("auth/approle/role/{ROLE}/role-id"),
            None,
        )
        .await,
    )
    .expect("role id response");
    let secret: Value = serde_json::from_str(
        &bao(
            client,
            addr,
            token,
            Method::POST,
            &format!("auth/approle/role/{ROLE}/secret-id"),
            Some(json!({})),
        )
        .await,
    )
    .expect("secret id response");
    (
        role["data"]["role_id"].as_str().unwrap().to_owned(),
        secret["data"]["secret_id"].as_str().unwrap().to_owned(),
    )
}

fn key_path(virtual_key: &str) -> String {
    format!(
        "{KV_PREFIX}/{}",
        hex::encode(Sha256::digest(virtual_key.as_bytes()))
    )
}

fn csv(values: &[&str]) -> BTreeSet<String> {
    values.iter().map(|value| (*value).to_owned()).collect()
}

fn token(signer: &RustCryptoMlDsa87, tenant: &str) -> TrustToken {
    let now = Utc::now();
    fabric_token::issue(
        TrustToken {
            token_id: format!("token-{tenant}"),
            issued_at: (now - chrono::Duration::minutes(1)).to_rfc3339(),
            expires_at: (now + chrono::Duration::minutes(12)).to_rfc3339(),
            issuer: "wsf-bridge".to_owned(),
            trust_bundle_version: "sad35-bundle".to_owned(),
            tenant_id: tenant.to_owned(),
            subject_id: Some(format!("subject-{tenant}")),
            subject_hash: format!("hash-{tenant}"),
            service_identity: Some("saddled".to_owned()),
            identity_id: None,
            roles: vec!["operator".to_owned()],
            compliance_scopes: Vec::new(),
            allowed_routes: vec![Route::LocalOnly],
            allowed_models: vec!["model".to_owned(), "local-model".to_owned()],
            max_data_classification: Classification::Restricted,
            country: Some("US".to_owned()),
            person_type: Some("us_person".to_owned()),
            offline_mode: false,
            revocation_status: RevocationStatus::Valid,
            budget: Some(Budget {
                token_cap: 50_000,
                usd_cap_cents: 5_000,
                tool_call_cap: 100,
                ..Budget::default()
            }),
            attenuation: Attenuation {
                root_id: Some(format!("root-{tenant}")),
                parent_id: Some(format!("root-{tenant}")),
                depth: 1,
                ancestor_ids: vec![format!("root-{tenant}")],
                caveats: Vec::new(),
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

fn context(tenant: &str, resource_name: &str) -> VerifiedRequestContext {
    let now = Utc::now();
    let principal = WsfPrincipal::establish(
        AuthenticatedFacts {
            principal_id: format!("spiffe://saddle/{tenant}/saddled"),
            kind: IdentityKind::Workload,
            tenant_id: tenant.to_owned(),
            subject_hash: format!("hash-{tenant}"),
            service_identity: Some("saddled".to_owned()),
            roles: vec!["operator".to_owned()],
            token_lineage: Some(format!("root-{tenant}")),
            auth_strength: AuthStrength::MutualTls,
            audience: Audience::Saddle,
        },
        format!("correlation-{tenant}-{resource_name}"),
        now.to_rfc3339(),
    );
    VerifiedRequestContext::establish(
        principal,
        RequestOperation::SaddleAdmission,
        CanonicalResource::resolved("Workload", resource_name, Some(tenant.to_owned())).unwrap(),
    )
    .unwrap()
}

fn signed_revocation(
    signer: &RustCryptoMlDsa87,
    sequence: u64,
    revoked_token: Option<&str>,
) -> RevocationSnapshot {
    let now = Utc::now();
    let mut snapshot = RevocationSnapshot::new(
        format!("sad35-revocation-{sequence}"),
        (now - chrono::Duration::minutes(1)).to_rfc3339(),
        (now + chrono::Duration::minutes(10)).to_rfc3339(),
    )
    .with_sequence(sequence);
    if let Some(token_id) = revoked_token {
        snapshot.revoked_tokens.push(token_id.to_owned());
    }
    sign_revocation(snapshot, signer).unwrap()
}

fn revocation(signer: &RustCryptoMlDsa87, sequence: u64) -> MonotonicRevocationStore {
    let mut store = MonotonicRevocationStore::new();
    store
        .advance(
            signed_revocation(signer, sequence, None),
            &MlDsa87Verifier,
            signer.public_key(),
        )
        .unwrap();
    store
}

struct IssuedRuntime {
    request: VerifiedSaddleRequest,
    handoff: PersistedGrantHandoff,
}

fn issue_runtime(
    signer: &RustCryptoMlDsa87,
    tenant: &str,
    token: &TrustToken,
    runtime_class: &str,
    workload_digest: &str,
) -> IssuedRuntime {
    let now = Utc::now();
    let resource_name = format!("{tenant}-{runtime_class}");
    let placement_uid = format!("placement-{tenant}-{runtime_class}");
    let mut issuer = GrantIssuer::new(AllowPolicy);
    let store = revocation(signer, 1);
    let request = issuer
        .verify_request(
            context(tenant, &resource_name),
            token,
            format!("request-{tenant}-{runtime_class}"),
            now,
            &MlDsa87Verifier,
            signer.public_key(),
            "sad35-bundle",
            &store,
        )
        .unwrap();
    let expires_at = (now + chrono::Duration::minutes(8)).to_rfc3339();
    let admission = issuer
        .issue_admission(
            &request,
            AdmissionSpec {
                verb: AdmissionVerb::Create,
                object_uid: format!("uid-{resource_name}"),
                object_name: resource_name.clone(),
                tenant_id: tenant.to_owned(),
                mutation_digest: format!("mutation-{resource_name}"),
                expires_at: expires_at.clone(),
                scope: CapabilityScope {
                    resource_prefixes: csv(&["workloads/"]),
                    models: csv(&["local-model"]),
                    tools: csv(&["echo.say"]),
                },
                receipt: ReceiptIntentSpec {
                    receipt_id: format!("admission-{resource_name}"),
                    request_digest: format!("admission-digest-{resource_name}"),
                },
            },
            now,
            &store,
        )
        .unwrap();
    let placement = issuer
        .issue_placement(
            &request,
            &admission,
            BridgePlacementSpec {
                placement_uid,
                workload_uid: format!("uid-{resource_name}"),
                generation: 1,
                eligible_nodes: csv(&["sad35-node"]),
                resource_reservation: csv(&["cpu=1", "memory=64Mi"]),
                trust_constraints: csv(&["mTLS", "ring-1"]),
                expires_at: expires_at.clone(),
                receipt: ReceiptIntentSpec {
                    receipt_id: format!("placement-{resource_name}"),
                    request_digest: format!("placement-digest-{resource_name}"),
                },
            },
            now,
            &store,
        )
        .unwrap();
    let runtime = issuer
        .issue_runtime(
            &request,
            &placement,
            RuntimeSpec {
                node_identity: "sad35-node".to_owned(),
                workload_digest: workload_digest.to_owned(),
                runtime_class: runtime_class.to_owned(),
                aog_permissions: match runtime_class {
                    "aog-gateway" => csv(&["local-model", "aog:model:dispatch"]),
                    "aog-toolproxy" => csv(&["echo.say", "aog:tool:broker"]),
                    _ => csv(&["restart"]),
                },
                budget: GrantBudget {
                    tokens: 20_000,
                    usd_cents: 2_000,
                    tool_calls: 50,
                },
                expires_at,
                receipt: ReceiptIntentSpec {
                    receipt_id: format!("runtime-{resource_name}"),
                    request_digest: format!("runtime-digest-{resource_name}"),
                },
            },
            now,
            &store,
        )
        .unwrap();
    let handoff = persist_grant_handoff(&placement, &runtime, signer).unwrap();
    IssuedRuntime { request, handoff }
}

fn verify_handoff(
    handoff: &PersistedGrantHandoff,
    signer: &RustCryptoMlDsa87,
) -> VerifiedGrantHandoff {
    verify_grant_handoff(
        handoff,
        Utc::now(),
        &revocation(signer, 1),
        &MlDsa87Verifier,
        signer.public_key(),
    )
    .unwrap()
}

fn install_session(
    registry: &ActionSessionRegistry,
    issued: IssuedRuntime,
    signer: &RustCryptoMlDsa87,
    ledger: Arc<std::sync::Mutex<Ledger>>,
) {
    registry.install(Arc::new(RuntimeActionSession::new(
        issued.request,
        verify_handoff(&issued.handoff, signer),
        Box::new(AllowPolicy),
        Box::new(InMemoryReplayStore::default()),
        Box::new(WsfLedgerActionSink::new(ledger)) as Box<dyn ActionReceiptSink>,
        revocation(signer, 1),
    )));
}

struct LocalProvider;

#[async_trait]
impl Provider for LocalProvider {
    fn name(&self) -> &str {
        "local"
    }

    async fn complete(
        &self,
        _request: &CompletionRequest,
    ) -> Result<CompletionResponse, ProviderError> {
        Ok(CompletionResponse {
            model: "local-model".to_owned(),
            content: "tenant-isolated".to_owned(),
            usage: Usage {
                input_tokens: 2,
                output_tokens: 2,
            },
            finish_reason: "stop".to_owned(),
        })
    }

    async fn stream(&self, _request: &CompletionRequest) -> Result<ChunkStream, ProviderError> {
        Ok(Box::pin(stream::empty()))
    }
}

async fn spawn(app: Router) -> String {
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let base = format!("http://{}", listener.local_addr().unwrap());
    tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    base
}

async fn chat(client: &Client, base: &str, key: &str) -> u16 {
    client
        .post(format!("{base}/v1/chat/completions"))
        .bearer_auth(key)
        .json(&json!({
            "model": "model",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 8
        }))
        .send()
        .await
        .unwrap()
        .status()
        .as_u16()
}

struct EchoExecutor;

#[async_trait]
impl ToolExecutor for EchoExecutor {
    async fn execute(
        &self,
        _tool: &ToolDefinition,
        call: &ToolCall,
        _credential: Option<&MintedCredential>,
    ) -> ToolResult {
        ToolResult {
            call_id: call.call_id.clone(),
            tool_id: call.tool_id.clone(),
            success: true,
            output: call.arguments.clone(),
            error: None,
            duration_ms: 1,
        }
    }
}

fn tool() -> ToolDefinition {
    ToolDefinition {
        id: "echo.say".to_owned(),
        name: "echo.say".to_owned(),
        description: "Echo one value".to_owned(),
        parameters_schema: json!({"type": "object"}),
        return_schema: None,
        has_side_effects: false,
        timeout: Duration::from_secs(5),
        required_role: ToolAccessRole::Guest,
        supports_parallel: false,
    }
}

fn call(id: &str) -> ToolCall {
    ToolCall {
        call_id: id.to_owned(),
        tool_id: "echo.say".to_owned(),
        arguments: json!({"value": id}),
        chain_step: 0,
        parallel_group: None,
    }
}

fn control_spec(tenant: &str, nonce: &str) -> ActionSpec {
    ActionSpec {
        kind: ActionKind::Control,
        action: "restart".to_owned(),
        arguments_digest: format!("args-{tenant}-{nonce}"),
        request_digest: format!("request-{tenant}-{nonce}"),
        destination: "saddle-controller".to_owned(),
        budget: GrantBudget {
            tokens: 0,
            usd_cents: 0,
            tool_calls: 1,
        },
        nonce: nonce.to_owned(),
        expires_at: (Utc::now() + chrono::Duration::minutes(1)).to_rfc3339(),
        receipt: ReceiptIntentSpec {
            receipt_id: format!("control-{tenant}-{nonce}"),
            request_digest: format!("request-{tenant}-{nonce}"),
        },
    }
}

fn process_workload(tenant: &str) -> saddle_estate::Workload {
    let mut workload = Resource::new(
        format!("{tenant}-aog-gateway"),
        WorkloadSpec {
            workload_kind: WorkloadKind::Gateway,
            replicas: 1,
            ring: 1,
            classification_ceiling: Classification::Restricted,
            image: None,
            command: if cfg!(windows) {
                vec![
                    "cmd".to_owned(),
                    "/C".to_owned(),
                    "ping -n 30 127.0.0.1 >NUL".to_owned(),
                ]
            } else {
                vec!["sh".to_owned(), "-c".to_owned(), "sleep 30".to_owned()]
            },
            capability: None,
            scheduling: SchedulingConstraints::default(),
        },
    );
    workload.metadata.uid = format!("uid-{tenant}-aog-gateway");
    workload.metadata.tenant = Some(tenant.to_owned());
    workload
}

fn child_token(signer: &RustCryptoMlDsa87, assignment: &RuntimeAssignment) -> TrustToken {
    let now = Utc::now();
    fabric_token::issue(
        TrustToken {
            token_id: assignment.token_id.clone(),
            issued_at: now.to_rfc3339(),
            expires_at: (now + chrono::Duration::minutes(5)).to_rfc3339(),
            issuer: "saddle-scheduler".to_owned(),
            trust_bundle_version: "sad35-bundle".to_owned(),
            tenant_id: assignment.tenant.clone(),
            subject_id: Some(assignment.workload_uid.clone()),
            subject_hash: assignment.workload_digest.clone(),
            service_identity: Some(service_identity(
                &assignment.tenant,
                assignment.workload_kind,
                &assignment.node_identity,
                &assignment.placement_uid,
            )),
            identity_id: Some(assignment.placement_uid.clone()),
            roles: vec![workload_role(assignment.workload_kind).to_owned()],
            compliance_scopes: Vec::new(),
            allowed_routes: vec![Route::LocalOnly],
            allowed_models: vec!["model".to_owned()],
            max_data_classification: Classification::Restricted,
            country: None,
            person_type: None,
            offline_mode: false,
            revocation_status: RevocationStatus::Valid,
            budget: None,
            attenuation: Attenuation {
                root_id: Some(format!("root-{}", assignment.tenant)),
                parent_id: Some(format!("token-{}", assignment.tenant)),
                depth: 2,
                ancestor_ids: vec![
                    format!("root-{}", assignment.tenant),
                    format!("token-{}", assignment.tenant),
                ],
                caveats: Vec::new(),
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

#[tokio::test]
async fn live_two_tenant_bridge_isolated_restartable_and_off_host_verifiable() {
    let Some(addr) = openbao_addr() else {
        eprintln!("SKIP SAD-35 live gate: SADDLE_LIVE_OPENBAO_ADDR unset");
        return;
    };
    let http = Client::builder()
        .timeout(Duration::from_secs(10))
        .build()
        .unwrap();
    let (role_id, secret_id) = provision(&http, &addr, &root_token()).await;
    let anchor = RustCryptoMlDsa87::generate("sad35-anchor").unwrap();
    let evidence_signer = Arc::new(RustCryptoMlDsa87::generate("sad35-evidence").unwrap());
    let evidence_key = evidence_signer.public_key().to_vec();
    let ledger = Arc::new(std::sync::Mutex::new(Ledger::new(evidence_signer)));
    let tokens = [token(&anchor, TENANTS[0]), token(&anchor, TENANTS[1])];

    let openbao = OpenBaoAuth::new(OpenBaoConfig::new(&addr, role_id, secret_id)).unwrap();
    let vault = openbao.login().await.expect("OpenBao login");
    for (key, token) in VKEYS.iter().zip(&tokens) {
        openbao
            .put_kv_data(&vault, &key_path(key), json!({"token": token}))
            .await
            .expect("seed tenant virtual key");
    }

    let gateway_workloads = [process_workload(TENANTS[0]), process_workload(TENANTS[1])];
    let gateway_digests = [
        workload_digest(&gateway_workloads[0]).unwrap(),
        workload_digest(&gateway_workloads[1]).unwrap(),
    ];
    let mut issued = Vec::new();
    for (tenant_index, tenant) in TENANTS.iter().enumerate() {
        for runtime in RUNTIME_CLASSES {
            let digest = if runtime == runtime_class(WorkloadKind::Gateway) {
                gateway_digests[tenant_index].as_str()
            } else {
                match runtime {
                    "aog-toolproxy" => "sha256:sad35-toolproxy",
                    _ => "sha256:sad35-control",
                }
            };
            issued.push((
                (*tenant).to_owned(),
                runtime.to_owned(),
                issue_runtime(&anchor, tenant, &tokens[tenant_index], runtime, digest),
            ));
        }
    }

    // Persist all six typed handoffs in the real redb state engine, close it,
    // then recover bytes into freshly verified runtime sessions.
    let store_path = handoff_store_path();
    let _ = std::fs::remove_file(&store_path);
    {
        let mut store = Store::open(RedbBackend::open(&store_path).unwrap()).unwrap();
        for (tenant, runtime, grant) in &issued {
            store
                .apply(&Op::Put {
                    key: format!("/bridge/{tenant}/{runtime}"),
                    value: serde_json::to_vec(&grant.handoff).unwrap(),
                    expected: Precondition::Absent,
                })
                .unwrap();
        }
    }
    let recovered = Store::open(RedbBackend::open(&store_path).unwrap()).unwrap();
    for (tenant, runtime, grant) in &mut issued {
        let bytes = recovered
            .get(&format!("/bridge/{tenant}/{runtime}"))
            .unwrap()
            .expect("persisted handoff")
            .value;
        grant.handoff = serde_json::from_slice(&bytes).unwrap();
        verify_handoff(&grant.handoff, &anchor);
    }

    let bridge = Arc::new(ActionSessionRegistry::new());
    for (_, _, grant) in issued {
        install_session(&bridge, grant, &anchor, Arc::clone(&ledger));
    }

    // The typed gateway handoff also binds the real node start. The existing
    // child token remains an independent last-moment proof.
    let gateway_handoff = bridge
        .session(TENANTS[0], "aog-gateway")
        .expect("tenant A gateway session");
    let mut placement = Resource::new(
        format!("placement-{}-aog-gateway", TENANTS[0]),
        EstatePlacementSpec {
            workload: gateway_workloads[0].metadata.name.clone(),
            node: "sad35-node".to_owned(),
            token_id: format!("child-{}-gateway", TENANTS[0]),
        },
    );
    placement.metadata.uid = format!("placement-{}-aog-gateway", TENANTS[0]);
    placement.metadata.tenant = Some(TENANTS[0].to_owned());
    let assignment =
        RuntimeAssignment::from_resources(&gateway_workloads[0], &placement, "sad35-node").unwrap();
    let child = child_token(&anchor, &assignment);
    let node_revocation = revocation(&anchor, 1);
    let driver = ProcessDriver::default();
    bridge
        .execute(
            TENANTS[0],
            &format!("root-{}", TENANTS[0]),
            control_spec(TENANTS[0], "node-restart"),
            Utc::now(),
            |_| async {
                let handle = start_bridged_authorized(
                    &driver,
                    &assignment,
                    gateway_handoff.handoff(),
                    &child,
                    node_revocation.current().unwrap(),
                    Utc::now(),
                    &MlDsa87Verifier,
                    anchor.public_key(),
                )
                .map_err(|error| error.to_string())?;
                driver.stop(&handle).map_err(|error| error.to_string())?;
                Ok(())
            },
        )
        .await
        .unwrap();

    let mut providers = Registry::new();
    providers.register(Arc::new(LocalProvider));
    let gateway = Arc::new(Gateway::new(
        openbao,
        GatewayConfig {
            token_public_key: anchor.public_key().to_vec(),
            virtual_key_kv_prefix: KV_PREFIX.to_owned(),
        },
    ));
    let models = ModelMap::new().route("model", Target::new("local", "local-model"));
    let state = AppState::new(gateway, Arc::new(providers), Arc::new(models))
        .with_saddle_bridge(Arc::clone(&bridge));
    let gateway_base = spawn(aog_gateway::surface_openai::router(state)).await;

    let proxy = ToolProxy::new().with_saddle_bridge(Arc::clone(&bridge));
    proxy.register(tool()).unwrap();
    let contexts = [
        InvokeContext::from_verified_request(
            "sad35-a",
            ToolAccessRole::Guest,
            bridge
                .session(TENANTS[0], "aog-toolproxy")
                .unwrap()
                .request()
                .context(),
        ),
        InvokeContext::from_verified_request(
            "sad35-b",
            ToolAccessRole::Guest,
            bridge
                .session(TENANTS[1], "aog-toolproxy")
                .unwrap()
                .request()
                .context(),
        ),
    ];

    for index in 0..2 {
        assert_eq!(chat(&http, &gateway_base, VKEYS[index]).await, 200);
        assert!(
            proxy
                .invoke(
                    &call(&format!("initial-{index}")),
                    &contexts[index],
                    &EchoExecutor
                )
                .await
                .unwrap()
                .success
        );
        bridge
            .execute(
                TENANTS[index],
                &format!("root-{}", TENANTS[index]),
                control_spec(TENANTS[index], &format!("initial-{index}")),
                Utc::now(),
                |_| async { Ok("restarted") },
            )
            .await
            .unwrap();
    }

    // A tenant cannot name its sibling's lineage or use a missing runtime.
    assert!(
        bridge
            .execute(
                TENANTS[1],
                &format!("root-{}", TENANTS[0]),
                control_spec(TENANTS[1], "cross-tenant"),
                Utc::now(),
                |_| async { Ok(()) },
            )
            .await
            .is_err()
    );

    // Consumer network loss is isolated and fail-closed; the sibling tenant
    // remains available and the restored session resumes without a new grant.
    let tenant_a_gateway = bridge.session(TENANTS[0], "aog-gateway").unwrap();
    tenant_a_gateway.set_available(false);
    assert_eq!(chat(&http, &gateway_base, VKEYS[0]).await, 503);
    assert_eq!(chat(&http, &gateway_base, VKEYS[1]).await, 200);
    tenant_a_gateway.set_available(true);
    assert_eq!(chat(&http, &gateway_base, VKEYS[0]).await, 200);

    // Revocation advances independently into every tenant-A consumer. No model,
    // tool, or control effect is reachable afterward; tenant B remains live.
    let revoked = signed_revocation(&anchor, 2, Some(&tokens[0].token_id));
    for runtime in RUNTIME_CLASSES {
        bridge
            .session(TENANTS[0], runtime)
            .unwrap()
            .advance_revocation(revoked.clone(), &MlDsa87Verifier, anchor.public_key())
            .unwrap();
    }
    assert_eq!(chat(&http, &gateway_base, VKEYS[0]).await, 503);
    assert_eq!(chat(&http, &gateway_base, VKEYS[1]).await, 200);
    assert!(
        proxy
            .invoke(&call("revoked-a"), &contexts[0], &EchoExecutor)
            .await
            .is_err()
    );
    assert!(
        proxy
            .invoke(&call("still-live-b"), &contexts[1], &EchoExecutor)
            .await
            .unwrap()
            .success
    );
    assert!(
        bridge
            .execute(
                TENANTS[0],
                &format!("root-{}", TENANTS[0]),
                control_spec(TENANTS[0], "revoked"),
                Utc::now(),
                |_| async { Ok(()) },
            )
            .await
            .is_err()
    );
    bridge
        .execute(
            TENANTS[1],
            &format!("root-{}", TENANTS[1]),
            control_spec(TENANTS[1], "still-live"),
            Utc::now(),
            |_| async { Ok(()) },
        )
        .await
        .unwrap();

    let pack = ledger
        .lock()
        .unwrap()
        .export_pack(Utc::now().to_rfc3339())
        .unwrap();
    let off_host: wsf_ledger::EvidencePack =
        serde_json::from_slice(&serde_json::to_vec(&pack).unwrap()).unwrap();
    assert!(verify_pack(&off_host, &MlDsa87Verifier, &evidence_key));
    assert!(
        off_host.count >= 10,
        "all consumer effects must be receipted"
    );

    drop(recovered);
    std::fs::remove_file(store_path).unwrap();
}
