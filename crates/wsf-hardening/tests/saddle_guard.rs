//! The Saddle production guard blocks any dev fixture and a single-node
//! quorum in production, and passes a production-ready deployment. It reuses the
//! base WSF dev-fixture guard (dev OpenBao root token / plaintext transport) and
//! adds Saddle's HA (>= 3 voters) and signed-bundle requirements. A no-op in dev.

use wsf_hardening::{
    DeployMode, DeploymentConfig, GuardViolation, SaddleDeployment, assert_saddle_production_ready,
    saddle_production_guard,
};

fn prod_config() -> DeploymentConfig {
    DeploymentConfig {
        mode: DeployMode::Production,
        openbao_address: "https://openbao.internal:8200".to_owned(),
        openbao_token: "s.prod-approle-token".to_owned(),
        subject_hmac_key: (0u8..32).collect(),
    }
}

fn has(violations: &[GuardViolation], code: &str) -> bool {
    violations.iter().any(|v| v.code == code)
}

#[test]
fn the_guard_is_a_no_op_in_dev() {
    let mut cfg = prod_config();
    cfg.mode = DeployMode::Dev;
    let dep = SaddleDeployment {
        config: &cfg,
        voter_count: 1,
        bundles_signed: false,
    };
    assert!(
        saddle_production_guard(&dep).is_empty(),
        "even a single-node, unsigned-bundle deployment is fine in dev"
    );
}

#[test]
fn a_production_ready_deployment_passes() {
    let cfg = prod_config();
    let dep = SaddleDeployment {
        config: &cfg,
        voter_count: 3,
        bundles_signed: true,
    };
    assert!(
        assert_saddle_production_ready(&dep).is_ok(),
        "https OpenBao, a real token, a strong HMAC key, 3 voters, signed bundles"
    );
}

#[test]
fn a_single_node_quorum_is_blocked_in_production() {
    let cfg = prod_config();
    let dep = SaddleDeployment {
        config: &cfg,
        voter_count: 1,
        bundles_signed: true,
    };
    assert!(
        has(&saddle_production_guard(&dep), "single_node_quorum"),
        "a single-node quorum is not HA and is rejected in production"
    );
    assert!(assert_saddle_production_ready(&dep).is_err());
}

#[test]
fn an_unsigned_bundle_is_blocked_in_production() {
    let cfg = prod_config();
    let dep = SaddleDeployment {
        config: &cfg,
        voter_count: 3,
        bundles_signed: false,
    };
    assert!(
        has(&saddle_production_guard(&dep), "unsigned_bundle"),
        "an unsigned policy bundle is rejected in production"
    );
}

#[test]
fn a_dev_openbao_fixture_is_blocked_in_production() {
    // The base WSF guard is reused: a dev root token + plaintext transport are
    // rejected even when the Saddle-specific facts are fine.
    let cfg = DeploymentConfig {
        mode: DeployMode::Production,
        openbao_address: "http://127.0.0.1:8200".to_owned(),
        openbao_token: "root".to_owned(),
        subject_hmac_key: (0u8..32).collect(),
    };
    let dep = SaddleDeployment {
        config: &cfg,
        voter_count: 3,
        bundles_signed: true,
    };
    let violations = saddle_production_guard(&dep);
    assert!(
        has(&violations, "dev_root_token") && has(&violations, "insecure_transport"),
        "dev OpenBao fixtures are blocked (the base PROD guard is reused)"
    );
}
