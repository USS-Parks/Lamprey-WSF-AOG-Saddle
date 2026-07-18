//! SAD-33 live gate: the four governed AOG service roles are scheduled with
//! exact child capabilities and started by the real node process driver.
//! Scale, digest roll, and capability revocation converge through the real
//! scheduler controller and node lifecycle reconciler against live OpenBao.
#![allow(clippy::print_stderr)]

use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};

use chrono::Utc;
use fabric_contracts::{Budget, Classification, Route, TrustToken};
use fabric_crypto::Signer;
use fabric_crypto::providers::{MlDsa87Verifier, RustCryptoMlDsa87};
use fabric_revocation::RevocationSnapshot;
use reqwest::{Client, Method};
use saddle_apiserver::AppState;
use saddle_apiserver::admission::ControllerProfile;
use saddle_apiserver::auth::Authenticator;
use saddle_apiserver::seal::Sealer;
use saddle_controller::{
    AlwaysLeader, Controller, EstateClient, Reconciler, SchedulerController, SyncStats,
};
use saddle_estate::{
    AttestationProfile, CapabilitySpec, Capacity, Kind, NodeSpec, NodeStatus, Resource,
    ResourceObject, SchedulingConstraints, WorkloadKind, WorkloadSpec,
};
use saddle_node::driver::{NoopDriver, ProcessDriver};
use saddle_node::runtime::{AuthorizedAssignment, NodeRuntime, RuntimeAssignment, workload_role};
use serde_json::{Value, json};
use wsf_bridge::{OpenBaoAuth, OpenBaoConfig};

const ROLE: &str = "saddle-sad33";
const PREFIX: &str = "kv/data/saddle/sad33/runtime";
const CAP: &str = "sad33-child-root";
const TENANT: &str = "sad33-tenant";
const NODE: &str = "sad33-node";

fn openbao_addr() -> Option<String> {
    std::env::var("WSF_OPENBAO_ADDR").ok()
}

fn root_token() -> String {
    std::env::var("WSF_OPENBAO_TOKEN").unwrap_or_else(|_| "root".to_owned())
}

fn fresh_dir(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(name);
    let _ = std::fs::remove_dir_all(&dir);
    dir
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
        "path \"{PREFIX}/*\" {{ capabilities = [\"create\",\"read\",\"update\",\"delete\"] }}"
    );
    bao(
        client,
        addr,
        token,
        Method::PUT,
        "sys/policies/acl/saddle-sad33",
        Some(json!({"policy": policy})),
    )
    .await;
    bao(
        client,
        addr,
        token,
        Method::POST,
        &format!("auth/approle/role/{ROLE}"),
        Some(json!({"token_policies": "default,saddle-sad33", "token_ttl": "15m"})),
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
    .unwrap();
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
    .unwrap();
    (
        role["data"]["role_id"].as_str().unwrap().to_owned(),
        secret["data"]["secret_id"].as_str().unwrap().to_owned(),
    )
}

fn quiet(stats: SyncStats) -> bool {
    stats.enqueued == 0 && stats.drained == 0 && stats.processed == 0
}

async fn settle<R: Reconciler>(controller: &mut Controller<R>) {
    let mut now = Instant::now();
    let mut last = SyncStats::default();
    for _ in 0..300 {
        let stats = controller.sync(now).await.unwrap();
        if quiet(stats) && controller.queue_len() == 0 && controller.delayed_len() == 0 {
            return;
        }
        last = stats;
        now += Duration::from_secs(20);
    }
    panic!("controller did not settle: {last:?}");
}

fn command() -> Vec<String> {
    if cfg!(windows) {
        vec![
            "cmd".to_owned(),
            "/C".to_owned(),
            "ping -n 120 127.0.0.1 >NUL".to_owned(),
        ]
    } else {
        vec!["sh".to_owned(), "-c".to_owned(), "sleep 120".to_owned()]
    }
}

fn workload(name: &str, kind: WorkloadKind) -> ResourceObject {
    let mut workload = Resource::new(
        name,
        WorkloadSpec {
            workload_kind: kind,
            replicas: 1,
            ring: 1,
            classification_ceiling: Classification::Internal,
            image: None,
            command: command(),
            capability: Some(CAP.to_owned()),
            scheduling: SchedulingConstraints::default(),
        },
    );
    workload.metadata.tenant = Some(TENANT.to_owned());
    ResourceObject::Workload(workload)
}

async fn desired_assignments(
    client: &EstateClient,
    openbao: &OpenBaoAuth,
) -> Vec<AuthorizedAssignment> {
    let vault = openbao.login().await.unwrap();
    let mut out = Vec::new();
    for object in client.list(Kind::Placement).await.unwrap() {
        let ResourceObject::Placement(placement) = object else {
            continue;
        };
        let Some(ResourceObject::Workload(workload)) = client
            .get(Kind::Workload, &placement.spec.workload)
            .await
            .unwrap()
        else {
            panic!("placement workload missing");
        };
        let value = openbao
            .get_kv_data(&vault, &format!("{PREFIX}/{}", placement.metadata.name))
            .await
            .unwrap();
        let token: TrustToken =
            serde_json::from_value(value.get("token").unwrap().clone()).unwrap();
        out.push(AuthorizedAssignment {
            assignment: RuntimeAssignment::from_resources(&workload, &placement, NODE).unwrap(),
            token,
        });
    }
    out.sort_by(|left, right| left.assignment.run.name.cmp(&right.assignment.run.name));
    out
}

#[tokio::test]
async fn start_scale_roll_and_revoke_are_capability_bound_end_to_end() {
    let Some(addr) = openbao_addr() else {
        eprintln!("SKIP SAD-33 live gate: WSF_OPENBAO_ADDR unset");
        return;
    };
    let http = Client::new();
    let (role_id, secret_id) = provision(&http, &addr, &root_token()).await;
    let anchor = Arc::new(RustCryptoMlDsa87::generate("sad33-anchor").unwrap());
    let state = AppState::bootstrap(
        1,
        fresh_dir("saddle-sad33-aog-workloads"),
        Authenticator::new(anchor.public_key().to_vec()),
        Sealer::generate().unwrap(),
    )
    .await
    .unwrap();
    let client = EstateClient::new(state.admission(), state.reader());
    let scheduler_admission = state.admission();
    let scheduler_client = EstateClient::for_controller(
        scheduler_admission.clone(),
        state.reader(),
        scheduler_admission.issue_controller_grant(
            ControllerProfile::Scheduler,
            TENANT,
            chrono::Duration::minutes(15),
        ),
    );
    let openbao =
        Arc::new(OpenBaoAuth::new(OpenBaoConfig::new(&addr, role_id, secret_id)).unwrap());

    let mut capability = Resource::new(
        CAP,
        CapabilitySpec {
            budget: Budget {
                token_cap: 10_000,
                tool_call_cap: 100,
                ..Budget::default()
            },
            caveats: Vec::new(),
            allowed_routes: vec![Route::LocalOnly],
            allowed_models: vec!["local-governed".to_owned()],
            max_classification: Classification::Internal,
            ttl_seconds: 900,
        },
    );
    capability.metadata.tenant = Some(TENANT.to_owned());
    client
        .ensure_created(ResourceObject::Capability(capability))
        .await
        .unwrap();

    let capacity = Capacity {
        cpu_millis: 16_000,
        memory_mb: 32_768,
        gpu: 0,
        max_workloads: 16,
    };
    let mut node = Resource::new(
        NODE,
        NodeSpec {
            ring: 1,
            attestation_floor: Classification::Restricted,
            attestation: AttestationProfile::default(),
            capacity,
        },
    );
    node.metadata.tenant = Some(TENANT.to_owned());
    client
        .ensure_created(ResourceObject::Node(node))
        .await
        .unwrap();
    let Some(ResourceObject::Node(mut node)) = client.get(Kind::Node, NODE).await.unwrap() else {
        panic!("node missing");
    };
    saddle_node::registration::mint_node_attestation(
        &node,
        anchor.as_ref(),
        chrono::Duration::hours(1),
    )
    .unwrap()
    .stamp(&mut node)
    .unwrap();
    node.status = Some(NodeStatus {
        ready: true,
        allocatable: capacity,
        last_heartbeat: Some(Utc::now().to_rfc3339()),
        ..NodeStatus::default()
    });
    client.update(ResourceObject::Node(node)).await.unwrap();

    for (name, kind) in [
        ("gateway", WorkloadKind::Gateway),
        ("toolproxy", WorkloadKind::Toolproxy),
        ("approvals", WorkloadKind::Approvals),
        ("agent", WorkloadKind::Agent),
    ] {
        client.ensure_created(workload(name, kind)).await.unwrap();
    }

    let scheduler_probe = scheduler_client.clone();
    let Some(ResourceObject::Workload(agent_for_scope_check)) =
        client.get(Kind::Workload, "agent").await.unwrap()
    else {
        panic!("agent missing");
    };
    assert!(
        scheduler_probe
            .update(ResourceObject::Workload(agent_for_scope_check))
            .await
            .is_err(),
        "scheduler grant cannot update a workload"
    );

    let signer: Arc<dyn Signer> = anchor.clone();
    let scheduler = SchedulerController::new(scheduler_client, openbao.clone(), PREFIX, signer);
    let mut controller = Controller::new(
        "sad33-scheduler",
        state.informer("Workload/"),
        scheduler.clone(),
        Arc::new(AlwaysLeader),
    );
    settle(&mut controller).await;

    let Some(ResourceObject::Placement(mut forged_binding)) =
        client.get(Kind::Placement, "gateway-r0").await.unwrap()
    else {
        panic!("gateway placement missing");
    };
    forged_binding.spec.node = "attacker-node".to_owned();
    assert!(
        scheduler_probe
            .update(ResourceObject::Placement(forged_binding))
            .await
            .is_err(),
        "scheduler grant cannot rewrite a finalized placement binding"
    );

    let runtime = NodeRuntime::new(ProcessDriver::default());
    let mut desired = desired_assignments(&client, &openbao).await;
    assert_eq!(desired.len(), 4, "all four AOG workload roles placed");
    for entry in &desired {
        assert_eq!(
            entry.token.roles,
            vec![workload_role(entry.assignment.workload_kind)],
            "one fixed least-privilege role per child"
        );
        assert_eq!(entry.token.attenuation.depth, 1);
        assert_eq!(entry.token.attenuation.parent_id.as_deref(), Some(CAP));
    }
    let revocation = RevocationSnapshot::new(
        "sad33",
        Utc::now().to_rfc3339(),
        (Utc::now() + chrono::Duration::hours(1)).to_rfc3339(),
    );
    let mut stolen = desired[0].clone();
    stolen.token = desired[1].token.clone();
    let theft_probe = NodeRuntime::new(NoopDriver::default());
    let denied = theft_probe
        .reconcile(
            &[stolen],
            &revocation,
            Utc::now(),
            &MlDsa87Verifier,
            anchor.public_key(),
        )
        .unwrap();
    assert_eq!(denied.denied.len(), 1, "a sibling child token cannot start");
    assert!(denied.running.is_empty());
    let started = runtime
        .reconcile(
            &desired,
            &revocation,
            Utc::now(),
            &MlDsa87Verifier,
            anchor.public_key(),
        )
        .unwrap();
    assert_eq!(started.started.len(), 4, "real process driver started four");
    assert!(started.denied.is_empty());

    // Scale the governed agent to two replicas; one new exact child starts.
    let Some(ResourceObject::Workload(mut agent)) =
        client.get(Kind::Workload, "agent").await.unwrap()
    else {
        panic!("agent missing");
    };
    agent.spec.replicas = 2;
    client
        .update(ResourceObject::Workload(agent))
        .await
        .unwrap();
    scheduler.reconcile("Workload/agent").await.unwrap();
    desired = desired_assignments(&client, &openbao).await;
    let scaled = runtime
        .reconcile(
            &desired,
            &revocation,
            Utc::now(),
            &MlDsa87Verifier,
            anchor.public_key(),
        )
        .unwrap();
    assert_eq!(desired.len(), 5);
    assert_eq!(scaled.started, vec!["agent-r1"]);

    // Roll the gateway runtime inputs. The same ordinal receives a new binding
    // UID/digest and the node stops then restarts it under the new child.
    let old_gateway = desired
        .iter()
        .find(|entry| entry.assignment.run.name == "gateway-r0")
        .unwrap()
        .assignment
        .clone();
    let Some(ResourceObject::Workload(mut gateway)) =
        client.get(Kind::Workload, "gateway").await.unwrap()
    else {
        panic!("gateway missing");
    };
    gateway.spec.command.push("rolled".to_owned());
    client
        .update(ResourceObject::Workload(gateway))
        .await
        .unwrap();
    scheduler.reconcile("Workload/gateway").await.unwrap();
    desired = desired_assignments(&client, &openbao).await;
    let new_gateway = desired
        .iter()
        .find(|entry| entry.assignment.run.name == "gateway-r0")
        .unwrap();
    assert_ne!(
        new_gateway.assignment.placement_uid,
        old_gateway.placement_uid
    );
    assert_ne!(
        new_gateway.assignment.workload_digest,
        old_gateway.workload_digest
    );
    let rolled = runtime
        .reconcile(
            &desired,
            &revocation,
            Utc::now(),
            &MlDsa87Verifier,
            anchor.public_key(),
        )
        .unwrap();
    assert_eq!(rolled.started, vec!["gateway-r0"]);
    assert_eq!(rolled.stopped, vec!["gateway-r0"]);

    // Revoking the shared declared root deletes every child and placement; the
    // node observes no desired assignments and stops every process.
    client.delete(Kind::Capability, CAP).await.unwrap();
    for name in ["gateway", "toolproxy", "approvals", "agent"] {
        scheduler
            .reconcile(&format!("Workload/{name}"))
            .await
            .unwrap();
    }
    desired = desired_assignments(&client, &openbao).await;
    assert!(desired.is_empty(), "revocation removed every binding");
    let revoked = runtime
        .reconcile(
            &desired,
            &revocation,
            Utc::now(),
            &MlDsa87Verifier,
            anchor.public_key(),
        )
        .unwrap();
    assert_eq!(revoked.stopped.len(), 5);
    assert!(revoked.running.is_empty());

    scheduler_admission.revoke_controller_grants();
    assert!(
        scheduler_probe
            .delete(Kind::Placement, "already-gone")
            .await
            .is_err(),
        "controller epoch revocation invalidates an outstanding scheduler grant"
    );
}
