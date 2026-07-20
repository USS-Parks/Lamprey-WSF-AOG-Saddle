//! SAD-41 consensus truth and fencing gate.
//!
//! These tests exercise real openraft elections, quorum confirmation, CAS
//! histories, snapshot transfer, joint membership rotation, bounded-stale
//! informer recovery, and minority/removed-member fencing.

use std::collections::BTreeSet;
use std::sync::Arc;
use std::time::{Duration, Instant};

use saddle_controller::{LeaderGate, SharedGate};
use saddle_store::raft::types::RaftResponse;
use saddle_store::raft::{
    Cluster, MembershipError, NodeError, RaftNode, validate_membership_change,
};
use saddle_store::{Op, Precondition};

fn scratch(name: &str) -> std::path::PathBuf {
    let dir = std::env::temp_dir().join(name);
    let _ = std::fs::remove_dir_all(&dir);
    dir
}

fn put(key: &str, value: impl Into<Vec<u8>>, expected: Precondition) -> Op {
    Op::Put {
        key: key.to_owned(),
        value: value.into(),
        expected,
    }
}

async fn confirmed_leader(nodes: &[Arc<RaftNode>], timeout: Duration) -> Option<usize> {
    let deadline = Instant::now() + timeout;
    loop {
        for (index, node) in nodes.iter().enumerate() {
            if node.confirm_leadership(Duration::from_millis(200)).await {
                return Some(index);
            }
        }
        if Instant::now() >= deadline {
            return None;
        }
        tokio::time::sleep(Duration::from_millis(20)).await;
    }
}

async fn await_value(node: &RaftNode, key: &str, expected: &[u8]) -> bool {
    let deadline = Instant::now() + Duration::from_secs(10);
    loop {
        if node
            .get(key)
            .await
            .ok()
            .flatten()
            .is_some_and(|value| value.value == expected)
        {
            return true;
        }
        if Instant::now() >= deadline {
            return false;
        }
        tokio::time::sleep(Duration::from_millis(20)).await;
    }
}

async fn three_node_cluster(label: &str) -> (Arc<Cluster>, Vec<Arc<RaftNode>>) {
    let dir = scratch(label);
    let cluster = Arc::new(Cluster::new());
    let mut nodes = Vec::new();
    for id in 1..=3 {
        nodes.push(Arc::new(
            RaftNode::join(id, dir.join(format!("n{id}")), &cluster)
                .await
                .unwrap(),
        ));
    }
    nodes[0].initialize(BTreeSet::from([1])).await.unwrap();
    nodes[0]
        .wait_for_leader(Duration::from_secs(10))
        .await
        .unwrap();
    nodes[0].add_learner(2).await.unwrap();
    nodes[0].add_learner(3).await.unwrap();
    nodes[0]
        .change_membership(BTreeSet::from([1, 2, 3]))
        .await
        .unwrap();
    (cluster, nodes)
}

#[tokio::test]
async fn concurrent_writes_remain_linearizable_across_leader_transition() {
    const KEY: &str = "Counter/sad41";
    let (cluster, nodes) = three_node_cluster("saddle-sad41-linearizable").await;
    nodes[0]
        .write(put(KEY, b"0".to_vec(), Precondition::Absent))
        .await
        .unwrap();

    let initial = confirmed_leader(&nodes, Duration::from_secs(10))
        .await
        .expect("initial confirmed leader");
    let fault_cluster = Arc::clone(&cluster);
    let fault_nodes = nodes.clone();
    let fault = tokio::spawn(async move {
        tokio::time::sleep(Duration::from_millis(40)).await;
        let victim = fault_nodes[initial].id();
        fault_cluster.isolate(victim);
        let survivors: Vec<_> = fault_nodes
            .iter()
            .filter(|node| node.id() != victim)
            .cloned()
            .collect();
        let replacement = confirmed_leader(&survivors, Duration::from_secs(10))
            .await
            .map(|index| survivors[index].id());
        tokio::time::sleep(Duration::from_millis(150)).await;
        fault_cluster.heal(victim);
        (victim, replacement)
    });

    let mut clients = Vec::new();
    for _ in 0..6 {
        let client_nodes = nodes.clone();
        clients.push(tokio::spawn(async move {
            let mut acknowledged = Vec::new();
            for _ in 0..32 {
                let Some(index) = confirmed_leader(&client_nodes, Duration::from_secs(2)).await
                else {
                    continue;
                };
                let node = &client_nodes[index];
                let Some(current) = node.get(KEY).await.unwrap() else {
                    continue;
                };
                let value = std::str::from_utf8(&current.value)
                    .unwrap()
                    .parse::<u64>()
                    .unwrap();
                if matches!(
                    node.write(put(
                        KEY,
                        (value + 1).to_string().into_bytes(),
                        Precondition::Revision(current.mod_revision),
                    ))
                    .await,
                    Ok(RaftResponse::Applied { .. })
                ) {
                    acknowledged.push(value + 1);
                }
                tokio::time::sleep(Duration::from_millis(2)).await;
            }
            acknowledged
        }));
    }

    let mut acknowledged = Vec::new();
    for client in clients {
        acknowledged.extend(client.await.unwrap());
    }
    let (victim, replacement) = fault.await.unwrap();
    assert_ne!(replacement, None, "the quorum side elected a replacement");
    assert_ne!(
        replacement,
        Some(victim),
        "leadership left the isolated node"
    );
    cluster.heal_all();

    let leader = confirmed_leader(&nodes, Duration::from_secs(10))
        .await
        .expect("confirmed leader after healing");
    let final_value = nodes[leader].get(KEY).await.unwrap().unwrap();
    let final_count = std::str::from_utf8(&final_value.value)
        .unwrap()
        .parse::<u64>()
        .unwrap();
    assert!(
        !acknowledged.is_empty(),
        "the history contains acknowledged writes"
    );
    let highest_acknowledged = *acknowledged.iter().max().unwrap();
    let unique_acknowledged = acknowledged.iter().copied().collect::<BTreeSet<_>>();
    assert!(
        highest_acknowledged <= final_count,
        "the most advanced acknowledged CAS write may not be lost"
    );
    assert_eq!(
        unique_acknowledged.len(),
        acknowledged.len(),
        "each acknowledged CAS value has one linearization point"
    );
    assert!(final_count <= 6 * 32, "a CAS attempt cannot apply twice");

    for node in nodes {
        node.stop().await.ok();
    }
}

#[tokio::test]
async fn snapshot_install_and_membership_rotation_preserve_exact_truth_and_fence_removed_member() {
    let dir = scratch("saddle-sad41-snapshot-membership");
    let cluster = Arc::new(Cluster::new());
    let mut nodes = Vec::new();
    for id in 1..=4 {
        nodes.push(Arc::new(
            RaftNode::join(id, dir.join(format!("n{id}")), &cluster)
                .await
                .unwrap(),
        ));
    }
    nodes[0].initialize(BTreeSet::from([1])).await.unwrap();
    nodes[0]
        .wait_for_leader(Duration::from_secs(10))
        .await
        .unwrap();
    nodes[0].add_learner(2).await.unwrap();
    nodes[0].add_learner(3).await.unwrap();
    nodes[0]
        .change_membership(BTreeSet::from([1, 2, 3]))
        .await
        .unwrap();

    // Expanding the voter set may legitimately elect a different leader before
    // this client issues its first write. Follow the quorum-confirmed leader
    // instead of assuming the single-node bootstrap leader retained authority.
    let initial_leader = confirmed_leader(&nodes[..3], Duration::from_secs(10))
        .await
        .expect("expanded membership elects a confirmed leader");
    let removed_node = Arc::clone(&nodes[initial_leader]);

    for index in 0..40 {
        removed_node
            .write(put(
                &format!("Workload/w{index:02}"),
                format!("v{index}").into_bytes(),
                Precondition::Absent,
            ))
            .await
            .unwrap();
    }
    removed_node
        .write(Op::Delete {
            key: "Workload/w05".to_owned(),
            expected: Precondition::Any,
        })
        .await
        .unwrap();
    let expected = removed_node.range("Workload/").await.unwrap();
    let expected_revision = removed_node.revision().await;
    assert_eq!(expected_revision, 41, "delete revisions are snapshot truth");
    removed_node
        .snapshot(Duration::from_secs(10))
        .await
        .unwrap();

    // With pre-snapshot logs purged, the late learner must install the versioned,
    // checksummed snapshot rather than reconstructing the estate from log zero.
    removed_node.add_learner(4).await.unwrap();
    let snapshot_deadline = Instant::now() + Duration::from_secs(10);
    loop {
        let restored = nodes[3].range("Workload/").await.unwrap();
        if restored == expected
            && nodes[3].revision().await == expected_revision
            && nodes[3].last_snapshot().is_some()
        {
            break;
        }
        assert!(
            Instant::now() < snapshot_deadline,
            "late learner did not install the exact snapshot before the deadline"
        );
        tokio::time::sleep(Duration::from_millis(20)).await;
    }
    assert!(
        nodes[3].last_snapshot().is_some(),
        "the late learner installed a snapshot"
    );

    let unsafe_change = removed_node
        .change_membership(BTreeSet::from([1, 2]))
        .await
        .unwrap_err();
    assert!(matches!(
        unsafe_change,
        NodeError::Membership(MembershipError::UnsafeVoterCount(2))
    ));

    let removed_gate = SharedGate::new(false);
    removed_gate.follow(removed_node.leadership());
    let gate_deadline = Instant::now() + Duration::from_secs(5);
    while !removed_gate.is_leader() && Instant::now() < gate_deadline {
        tokio::time::sleep(Duration::from_millis(20)).await;
    }
    assert!(
        removed_gate.is_leader(),
        "healthy quorum opens the confirmed gate"
    );

    let removed_id = removed_node.id();
    let rotated_members = nodes
        .iter()
        .map(|node| node.id())
        .filter(|id| *id != removed_id)
        .collect();
    removed_node
        .change_membership(rotated_members)
        .await
        .unwrap();
    let survivors = nodes
        .iter()
        .filter(|node| node.id() != removed_id)
        .cloned()
        .collect::<Vec<_>>();
    let leader = confirmed_leader(&survivors, Duration::from_secs(10))
        .await
        .expect("rotated membership elects a leader");
    let fence_deadline = Instant::now() + Duration::from_secs(5);
    while removed_gate.is_leader() && Instant::now() < fence_deadline {
        tokio::time::sleep(Duration::from_millis(20)).await;
    }
    assert!(
        !removed_gate.is_leader(),
        "removed member closes its action gate"
    );
    assert!(
        !removed_node
            .confirm_leadership(Duration::from_millis(500))
            .await,
        "removed member cannot confirm authority"
    );
    let removed_write = tokio::time::timeout(
        Duration::from_secs(2),
        removed_node.write(put(
            "Workload/removed",
            b"forged".to_vec(),
            Precondition::Any,
        )),
    )
    .await;
    assert!(
        !matches!(removed_write, Ok(Ok(RaftResponse::Applied { .. }))),
        "removed member cannot acknowledge a write"
    );

    survivors[leader]
        .write(put(
            "Workload/rotated",
            b"authoritative".to_vec(),
            Precondition::Absent,
        ))
        .await
        .unwrap();
    for node in &survivors {
        assert!(await_value(node, "Workload/rotated", b"authoritative").await);
    }

    for node in nodes {
        node.stop().await.ok();
    }
}

#[tokio::test]
async fn bounded_stale_watch_fails_closed_and_recovers_from_lag() {
    let dir = scratch("saddle-sad41-watch");
    let node = RaftNode::bootstrap(1, &dir).await.unwrap();
    node.write(put("Tenant/acme", b"v1".to_vec(), Precondition::Absent))
        .await
        .unwrap();
    let mut informer = node.informer("Tenant/");
    informer.resync().await.unwrap();
    assert!(informer.snapshot_if_fresh(Duration::from_secs(1)).is_some());

    tokio::time::sleep(Duration::from_millis(25)).await;
    assert!(
        informer
            .snapshot_if_fresh(Duration::from_millis(5))
            .is_none(),
        "an expired cache fails closed"
    );
    informer
        .poll_bounded(Duration::from_millis(5))
        .await
        .unwrap();
    assert!(informer.snapshot_if_fresh(Duration::from_secs(1)).is_some());

    // Overflow the 64-event stream. poll_bounded must detect Lagged, re-list,
    // and return a current complete cache with the authoritative revision.
    for index in 0..100 {
        node.write(put(
            &format!("Tenant/t{index:03}"),
            b"v".to_vec(),
            Precondition::Any,
        ))
        .await
        .unwrap();
    }
    informer.poll_bounded(Duration::from_secs(1)).await.unwrap();
    assert_eq!(informer.snapshot().len(), 101);
    assert_eq!(informer.revision(), node.revision().await);
    assert!(informer.snapshot_if_fresh(Duration::from_secs(1)).is_some());

    node.shutdown().await.unwrap();
}

#[test]
fn membership_validation_rejects_unknown_and_non_quorum_rotations() {
    let current = BTreeSet::from([1, 2, 3]);
    let known = BTreeSet::from([1, 2, 3, 4, 5]);
    assert!(matches!(
        validate_membership_change(&BTreeSet::from([1]), &known, &BTreeSet::from([1, 2, 3, 4])),
        Err(MembershipError::UnsafeVoterCount(4))
    ));
    assert!(matches!(
        validate_membership_change(&current, &known, &BTreeSet::from([2, 3, 99])),
        Err(MembershipError::UnknownVoter(99))
    ));
    assert!(matches!(
        validate_membership_change(&current, &known, &BTreeSet::from([3, 4, 5])),
        Err(MembershipError::InsufficientOverlap {
            retained: 1,
            required: 2
        })
    ));
}

#[tokio::test]
async fn minority_partition_closes_confirmed_gate_and_serves_no_authoritative_write() {
    let (cluster, nodes) = three_node_cluster("saddle-sad41-minority").await;
    let leader = confirmed_leader(&nodes, Duration::from_secs(10))
        .await
        .expect("initial leader");
    let victim = nodes[leader].id();
    let gate = SharedGate::new(false);
    gate.follow(nodes[leader].leadership());
    let open_deadline = Instant::now() + Duration::from_secs(5);
    while !gate.is_leader() && Instant::now() < open_deadline {
        tokio::time::sleep(Duration::from_millis(20)).await;
    }
    assert!(gate.is_leader());

    cluster.isolate(victim);
    let close_deadline = Instant::now() + Duration::from_secs(5);
    while gate.is_leader() && Instant::now() < close_deadline {
        tokio::time::sleep(Duration::from_millis(20)).await;
    }
    assert!(
        !gate.is_leader(),
        "minority gate closes without metric demotion"
    );
    assert!(
        !nodes[leader]
            .confirm_leadership(Duration::from_millis(500))
            .await
    );
    let fenced = tokio::time::timeout(
        Duration::from_secs(2),
        nodes[leader].write(put(
            "Capability/minority",
            b"allow".to_vec(),
            Precondition::Any,
        )),
    )
    .await;
    assert!(!matches!(fenced, Ok(Ok(RaftResponse::Applied { .. }))));

    let majority: Vec<_> = nodes
        .iter()
        .filter(|node| node.id() != victim)
        .cloned()
        .collect();
    let majority_leader = confirmed_leader(&majority, Duration::from_secs(10))
        .await
        .expect("majority leader");
    majority[majority_leader]
        .write(put(
            "Capability/majority",
            b"deny-wins".to_vec(),
            Precondition::Absent,
        ))
        .await
        .unwrap();
    assert!(
        await_value(
            &majority[1 - majority_leader],
            "Capability/majority",
            b"deny-wins"
        )
        .await
    );

    cluster.heal_all();
    for node in nodes {
        node.stop().await.ok();
    }
}
