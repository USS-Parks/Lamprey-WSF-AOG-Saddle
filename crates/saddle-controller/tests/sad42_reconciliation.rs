//! SAD-42 level-triggered reconciliation gate.
//!
//! The histories below use the real Raft store, informer lag/re-list path,
//! controller queue, admitted finalizer mutation path, retry machinery, and
//! cancellation behavior. Events are only hints: every reconciler re-reads
//! current state before making an idempotent effect.

use std::collections::{BTreeMap, HashMap, VecDeque};
use std::future::{Future, pending};
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use fabric_contracts::Classification;
use fabric_crypto::Signer;
use fabric_crypto::providers::RustCryptoMlDsa87;
use saddle_apiserver::AppState;
use saddle_apiserver::auth::Authenticator;
use saddle_apiserver::seal::Sealer;
use saddle_controller::{
    Action, AlwaysLeader, Backoff, Controller, EstateClient, ReconcileError, Reconciler,
    SharedGate, SyncStats,
};
use saddle_estate::{
    Kind, Resource, ResourceObject, SchedulingConstraints, WorkloadKind, WorkloadSpec,
};
use saddle_store::raft::RaftNode;
use saddle_store::raft::types::RaftResponse;
use saddle_store::{Op, Precondition};
use tokio::sync::Notify;

const PREFIX: &str = "Desired/";
const TERMINATING: &str = "__terminating__";
const FINALIZER: &str = "saddle.islandmountain.io/sad42-external";

fn fresh_dir(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    dir
}

async fn put(node: &RaftNode, key: &str, value: &str) {
    let response = node
        .write(Op::Put {
            key: key.to_owned(),
            value: value.as_bytes().to_vec(),
            expected: Precondition::Any,
        })
        .await
        .unwrap();
    assert!(matches!(response, RaftResponse::Applied { .. }));
}

async fn delete(node: &RaftNode, key: &str) {
    node.write(Op::Delete {
        key: key.to_owned(),
        expected: Precondition::Any,
    })
    .await
    .unwrap();
}

fn quiet(stats: SyncStats) -> bool {
    stats.enqueued == 0 && stats.drained == 0 && stats.processed == 0
}

async fn settle<R: Reconciler>(controller: &mut Controller<R>, mut now: Instant) -> Instant {
    for _ in 0..512 {
        let stats = controller.sync(now).await.unwrap();
        if quiet(stats) && controller.queue_len() == 0 && controller.delayed_len() == 0 {
            assert!(
                controller.dead_letters().is_empty(),
                "settled controller retained dead letters: {:?}",
                controller.dead_letters()
            );
            return now;
        }
        now += Duration::from_millis(100);
    }
    panic!(
        "controller did not settle: queued={}, delayed={}, dead={:?}",
        controller.queue_len(),
        controller.delayed_len(),
        controller.dead_letters()
    );
}

struct SplitMix64(u64);

impl SplitMix64 {
    fn new(seed: u64) -> Self {
        Self(seed)
    }

    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9e37_79b9_7f4a_7c15);
        let mut value = self.0;
        value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
        value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
        value ^ (value >> 31)
    }

    fn below(&mut self, ceiling: u64) -> u64 {
        self.next() % ceiling.max(1)
    }
}

#[derive(Debug, Clone, Copy)]
enum Fault {
    BeforeEffect,
    AfterEffect,
}

#[derive(Clone)]
struct ProjectionReconciler {
    node: Arc<RaftNode>,
    external: Arc<Mutex<BTreeMap<String, String>>>,
    faults: Arc<Mutex<HashMap<String, VecDeque<Fault>>>>,
    cleanup_attempts: Arc<AtomicUsize>,
}

impl ProjectionReconciler {
    fn new(node: Arc<RaftNode>, external: Arc<Mutex<BTreeMap<String, String>>>) -> Self {
        Self {
            node,
            external,
            faults: Arc::new(Mutex::new(HashMap::new())),
            cleanup_attempts: Arc::new(AtomicUsize::new(0)),
        }
    }

    fn set_faults(&self, faults: HashMap<String, VecDeque<Fault>>) {
        *self.faults.lock().unwrap() = faults;
    }

    fn pop_fault(&self, key: &str) -> Option<Fault> {
        self.faults
            .lock()
            .unwrap()
            .get_mut(key)
            .and_then(VecDeque::pop_front)
    }
}

impl Reconciler for ProjectionReconciler {
    fn reconcile(&self, key: &str) -> impl Future<Output = Result<Action, ReconcileError>> + Send {
        let reconciler = self.clone();
        let key = key.to_owned();
        async move {
            let fault = reconciler.pop_fault(&key);
            if matches!(fault, Some(Fault::BeforeEffect)) {
                return Err(ReconcileError(format!(
                    "injected pre-effect fault for {key}"
                )));
            }

            let current = reconciler
                .node
                .get(&key)
                .await
                .map_err(|error| ReconcileError(error.to_string()))?;
            match current {
                Some(versioned) => {
                    let value = String::from_utf8(versioned.value)
                        .map_err(|error| ReconcileError(error.to_string()))?;
                    if value == TERMINATING {
                        reconciler.external.lock().unwrap().remove(&key);
                        reconciler.cleanup_attempts.fetch_add(1, Ordering::SeqCst);
                        if matches!(fault, Some(Fault::AfterEffect)) {
                            return Err(ReconcileError(format!(
                                "injected lost cleanup acknowledgement for {key}"
                            )));
                        }
                        let response = reconciler
                            .node
                            .write(Op::Delete {
                                key: key.clone(),
                                expected: Precondition::Revision(versioned.mod_revision),
                            })
                            .await
                            .map_err(|error| ReconcileError(error.to_string()))?;
                        if !matches!(response, RaftResponse::Applied { .. }) {
                            return Err(ReconcileError(format!(
                                "finalization CAS lost for {key}: {response:?}"
                            )));
                        }
                    } else {
                        reconciler
                            .external
                            .lock()
                            .unwrap()
                            .insert(key.clone(), value);
                        if matches!(fault, Some(Fault::AfterEffect)) {
                            return Err(ReconcileError(format!(
                                "injected lost projection acknowledgement for {key}"
                            )));
                        }
                    }
                }
                None => {
                    reconciler.external.lock().unwrap().remove(&key);
                    if matches!(fault, Some(Fault::AfterEffect)) {
                        return Err(ReconcileError(format!(
                            "injected lost absence acknowledgement for {key}"
                        )));
                    }
                }
            }
            Ok(Action::Done)
        }
    }
}

fn projection_controller(
    node: &Arc<RaftNode>,
    reconciler: ProjectionReconciler,
    gate: Arc<SharedGate>,
) -> Controller<ProjectionReconciler> {
    Controller::new("sad42-history", node.informer(PREFIX), reconciler, gate)
        .with_budget(1)
        .with_backoff(Backoff {
            base: Duration::from_millis(1),
            max: Duration::from_millis(20),
        })
        .with_max_retries(6)
}

#[tokio::test]
async fn fault_injected_histories_converge_to_same_state() {
    const HISTORIES: usize = 256;
    let node = Arc::new(
        RaftNode::bootstrap(1, fresh_dir("saddle-sad42-histories"))
            .await
            .unwrap(),
    );
    let external = Arc::new(Mutex::new(BTreeMap::new()));
    let mut random = SplitMix64::new(0x5ad4_2000_c0de_f17e);
    let expected: BTreeMap<String, String> = [
        ("Desired/k0".to_owned(), "v2".to_owned()),
        ("Desired/k2".to_owned(), "v1".to_owned()),
        ("Desired/k3".to_owned(), "v1".to_owned()),
        ("Desired/k4".to_owned(), "v1".to_owned()),
        ("Desired/k5".to_owned(), "v1".to_owned()),
        ("Desired/k6".to_owned(), "v1".to_owned()),
    ]
    .into_iter()
    .collect();
    let mut injected_faults = 0;
    let mut overflow_histories = 0;
    let mut restart_histories = 0;
    let mut cleanup_attempts = 0;

    for history in 0..HISTORIES {
        external.lock().unwrap().clear();
        for index in 0..6 {
            put(&node, &format!("Desired/k{index}"), "v1").await;
        }
        delete(&node, "Desired/k6").await;

        let reconciler = ProjectionReconciler::new(Arc::clone(&node), Arc::clone(&external));
        let gate = SharedGate::new(true);
        let mut controller = projection_controller(&node, reconciler.clone(), Arc::clone(&gate));
        let mut now = settle(&mut controller, Instant::now()).await;

        put(&node, "Desired/k0", "v2").await;
        put(&node, "Desired/k1", TERMINATING).await;
        put(&node, "Desired/k6", "v1").await;

        let mut faults = HashMap::new();
        for key in ["Desired/k0", "Desired/k1", "Desired/k6"] {
            let mut plan = VecDeque::new();
            match random.below(4) {
                1 => plan.push_back(Fault::BeforeEffect),
                2 => plan.push_back(Fault::AfterEffect),
                3 => {
                    plan.push_back(Fault::BeforeEffect);
                    plan.push_back(Fault::AfterEffect);
                }
                _ => {}
            }
            injected_faults += plan.len();
            faults.insert(key.to_owned(), plan);
        }
        if faults.values().all(VecDeque::is_empty) {
            faults
                .get_mut("Desired/k1")
                .unwrap()
                .push_back(Fault::AfterEffect);
            injected_faults += 1;
        }
        reconciler.set_faults(faults);

        let mut delivery = vec!["Desired/k0", "Desired/k1", "Desired/k6"];
        for index in (1..delivery.len()).rev() {
            let swap = usize::try_from(random.below(index as u64 + 1)).unwrap();
            delivery.swap(index, swap);
        }
        for key in delivery {
            for _ in 0..=random.below(4) {
                controller.enqueue(key);
            }
        }

        if history % 3 == 0 {
            overflow_histories += 1;
            for index in 0..100 {
                put(&node, &format!("Noise/{index:03}"), "watch-overflow").await;
            }
        }
        if history % 4 == 0 {
            gate.set(false);
            let stats = controller.sync(now).await.unwrap();
            assert!(!stats.leader);
            assert_eq!(stats.processed, 0, "a follower only accumulates work");
            gate.set(true);
            now += Duration::from_millis(100);
        }
        if history % 5 == 0 {
            restart_histories += 1;
            let _ = controller.sync(now).await.unwrap();
            now += Duration::from_millis(100);
            drop(controller);
            controller = projection_controller(&node, reconciler.clone(), Arc::clone(&gate));
        }

        settle(&mut controller, now).await;
        let got = external.lock().unwrap().clone();
        assert_eq!(got, expected, "history {history} diverged");
        assert!(node.get("Desired/k1").await.unwrap().is_none());
        cleanup_attempts += reconciler.cleanup_attempts.load(Ordering::SeqCst);
    }

    assert!(injected_faults >= HISTORIES);
    assert_eq!(overflow_histories, 86);
    assert_eq!(restart_histories, 52);
    assert!(cleanup_attempts >= HISTORIES);
    node.stop().await.unwrap();
}

#[derive(Clone)]
struct FinalizerReconciler {
    client: EstateClient,
    external: Arc<Mutex<BTreeMap<String, u32>>>,
    cleanup_failures: Arc<AtomicUsize>,
    cleanup_attempts: Arc<AtomicUsize>,
}

impl FinalizerReconciler {
    fn consume_cleanup_failure(&self) -> bool {
        self.cleanup_failures
            .fetch_update(Ordering::SeqCst, Ordering::SeqCst, |remaining| {
                remaining.checked_sub(1)
            })
            .is_ok()
    }
}

impl Reconciler for FinalizerReconciler {
    fn reconcile(&self, key: &str) -> impl Future<Output = Result<Action, ReconcileError>> + Send {
        let reconciler = self.clone();
        let key = key.to_owned();
        async move {
            let Some(name) = key.strip_prefix("Workload/") else {
                return Ok(Action::Done);
            };
            let Some(ResourceObject::Workload(mut workload)) =
                reconciler.client.get(Kind::Workload, name).await?
            else {
                reconciler.external.lock().unwrap().remove(name);
                return Ok(Action::Done);
            };

            if workload.metadata.deletion_timestamp.is_some() {
                reconciler.external.lock().unwrap().remove(name);
                reconciler.cleanup_attempts.fetch_add(1, Ordering::SeqCst);
                if reconciler.consume_cleanup_failure() {
                    return Err(ReconcileError(
                        "injected lost external-cleanup acknowledgement".to_owned(),
                    ));
                }
                workload
                    .metadata
                    .finalizers
                    .retain(|value| value != FINALIZER);
                reconciler
                    .client
                    .update(ResourceObject::Workload(workload))
                    .await?;
                return Ok(Action::Done);
            }

            if !workload
                .metadata
                .finalizers
                .iter()
                .any(|value| value == FINALIZER)
            {
                workload.metadata.finalizers.push(FINALIZER.to_owned());
                reconciler
                    .client
                    .update(ResourceObject::Workload(workload))
                    .await?;
                return Ok(Action::Requeue);
            }

            reconciler
                .external
                .lock()
                .unwrap()
                .insert(name.to_owned(), workload.spec.replicas);
            Ok(Action::Done)
        }
    }
}

fn workload(replicas: u32) -> ResourceObject {
    ResourceObject::Workload(Resource::new(
        "agent",
        WorkloadSpec {
            workload_kind: WorkloadKind::Agent,
            replicas,
            ring: 1,
            classification_ceiling: Classification::Internal,
            image: None,
            command: Vec::new(),
            capability: None,
            scheduling: SchedulingConstraints::default(),
        },
    ))
}

#[tokio::test]
async fn real_finalizer_replay_withdraws_external_state_before_delete() {
    let node = Arc::new(
        RaftNode::bootstrap(1, fresh_dir("saddle-sad42-finalizer"))
            .await
            .unwrap(),
    );
    let anchor = RustCryptoMlDsa87::generate("sad42-finalizer-anchor").unwrap();
    let state = AppState::from_raft(
        Arc::clone(&node),
        Authenticator::new(anchor.public_key().to_vec()),
        Sealer::generate().unwrap(),
    );
    let client = EstateClient::new(state.admission(), state.reader());
    client.ensure_created(workload(1)).await.unwrap();

    let external = Arc::new(Mutex::new(BTreeMap::new()));
    let reconciler = FinalizerReconciler {
        client: client.clone(),
        external: Arc::clone(&external),
        cleanup_failures: Arc::new(AtomicUsize::new(0)),
        cleanup_attempts: Arc::new(AtomicUsize::new(0)),
    };
    let mut controller = Controller::new(
        "sad42-finalizer",
        state.informer("Workload/"),
        reconciler.clone(),
        Arc::new(AlwaysLeader),
    )
    .with_budget(1)
    .with_backoff(Backoff {
        base: Duration::from_millis(1),
        max: Duration::from_millis(10),
    });
    let mut now = settle(&mut controller, Instant::now()).await;
    assert_eq!(external.lock().unwrap().get("agent"), Some(&1));
    let Some(ResourceObject::Workload(mut desired)) =
        client.get(Kind::Workload, "agent").await.unwrap()
    else {
        panic!("workload missing after initial reconciliation");
    };
    assert!(desired.metadata.finalizers.contains(&FINALIZER.to_owned()));

    desired.spec.replicas = 3;
    client
        .update(ResourceObject::Workload(desired))
        .await
        .unwrap();
    for _ in 0..4 {
        controller.enqueue("Workload/agent");
    }
    now = settle(&mut controller, now + Duration::from_millis(100)).await;
    assert_eq!(external.lock().unwrap().get("agent"), Some(&3));

    reconciler.cleanup_failures.store(1, Ordering::SeqCst);
    client.delete(Kind::Workload, "agent").await.unwrap();
    for index in 0..100 {
        put(&node, &format!("Noise/finalizer-{index:03}"), "overflow").await;
    }
    for _ in 0..4 {
        controller.enqueue("Workload/agent");
    }
    let failed = controller
        .sync(now + Duration::from_millis(100))
        .await
        .unwrap();
    assert_eq!(failed.failed, 1);
    assert!(external.lock().unwrap().get("agent").is_none());
    let Some(ResourceObject::Workload(terminating)) =
        client.get(Kind::Workload, "agent").await.unwrap()
    else {
        panic!("finalized before the injected cleanup acknowledgement loss");
    };
    assert!(terminating.metadata.deletion_timestamp.is_some());
    assert!(
        terminating
            .metadata
            .finalizers
            .contains(&FINALIZER.to_owned())
    );

    // A controller process restart loses the queued retry, not desired truth:
    // the finalizer keeps the object discoverable by the new informer's relist.
    drop(controller);
    let mut restarted = Controller::new(
        "sad42-finalizer-restarted",
        state.informer("Workload/"),
        reconciler.clone(),
        Arc::new(AlwaysLeader),
    )
    .with_backoff(Backoff {
        base: Duration::from_millis(1),
        max: Duration::from_millis(10),
    });
    settle(&mut restarted, now + Duration::from_millis(200)).await;

    assert!(client.get(Kind::Workload, "agent").await.unwrap().is_none());
    assert!(external.lock().unwrap().get("agent").is_none());
    assert!(reconciler.cleanup_attempts.load(Ordering::SeqCst) >= 2);
    assert!(
        state.receipts_len() >= 4,
        "finalizer mutations were admitted"
    );
    node.stop().await.unwrap();
}

struct CancelSignal(Arc<AtomicBool>);

impl Drop for CancelSignal {
    fn drop(&mut self) {
        self.0.store(true, Ordering::SeqCst);
    }
}

#[derive(Clone)]
struct NeverCompletes {
    started: Arc<Notify>,
    cancelled: Arc<AtomicBool>,
}

impl Reconciler for NeverCompletes {
    fn reconcile(&self, _key: &str) -> impl Future<Output = Result<Action, ReconcileError>> + Send {
        let started = Arc::clone(&self.started);
        let cancelled = Arc::clone(&self.cancelled);
        async move {
            let _signal = CancelSignal(cancelled);
            started.notify_one();
            pending::<Result<Action, ReconcileError>>().await
        }
    }
}

#[tokio::test]
async fn reconcile_deadline_cancels_and_dead_letters_hung_work() {
    let node = Arc::new(
        RaftNode::bootstrap(1, fresh_dir("saddle-sad42-deadline"))
            .await
            .unwrap(),
    );
    put(&node, "Desired/hung", "v1").await;
    let cancelled = Arc::new(AtomicBool::new(false));
    let reconciler = NeverCompletes {
        started: Arc::new(Notify::new()),
        cancelled: Arc::clone(&cancelled),
    };
    let mut controller = Controller::new(
        "sad42-deadline",
        node.informer(PREFIX),
        reconciler,
        Arc::new(AlwaysLeader),
    )
    .with_reconcile_timeout(Duration::from_millis(10))
    .with_max_retries(1);

    let stats = controller.sync(Instant::now()).await.unwrap();
    assert_eq!(stats.processed, 1);
    assert_eq!(stats.failed, 1);
    assert_eq!(stats.timed_out, 1);
    assert_eq!(stats.dead_lettered, 1);
    assert!(cancelled.load(Ordering::SeqCst));
    let dead = controller.dead_letters();
    assert_eq!(dead.len(), 1);
    assert_eq!(dead[0].key, "Desired/hung");
    assert!(dead[0].last_error.contains("deadline"));
    node.stop().await.unwrap();
}

#[tokio::test]
async fn shutdown_cancels_an_inflight_reconcile() {
    let node = Arc::new(
        RaftNode::bootstrap(1, fresh_dir("saddle-sad42-cancel"))
            .await
            .unwrap(),
    );
    put(&node, "Desired/hung", "v1").await;
    let started = Arc::new(Notify::new());
    let cancelled = Arc::new(AtomicBool::new(false));
    let reconciler = NeverCompletes {
        started: Arc::clone(&started),
        cancelled: Arc::clone(&cancelled),
    };
    let mut controller = Controller::new(
        "sad42-cancel",
        node.informer(PREFIX),
        reconciler,
        Arc::new(AlwaysLeader),
    )
    .with_reconcile_timeout(Duration::from_secs(60));
    let (shutdown_tx, shutdown_rx) = tokio::sync::watch::channel(false);
    let task =
        tokio::spawn(async move { controller.run(Duration::from_secs(60), shutdown_rx).await });

    tokio::time::timeout(Duration::from_secs(1), started.notified())
        .await
        .expect("reconcile started");
    shutdown_tx.send(true).unwrap();
    tokio::time::timeout(Duration::from_secs(1), task)
        .await
        .expect("shutdown cancelled the reconcile")
        .unwrap()
        .unwrap();
    assert!(cancelled.load(Ordering::SeqCst));
    node.stop().await.unwrap();
}
