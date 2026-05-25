//! Unit-style tests for `MaiClientConfig` construction and helpers.

use std::collections::HashMap;
use std::time::Duration;

use mai_sdk_rs::{MaiClient, MaiClientConfig, RequestPriority, SdkError};

#[test]
fn client_requires_api_key_or_profile_id() {
    let cfg = MaiClientConfig {
        api_key: None,
        profile_id: String::new(),
        ..MaiClientConfig::default()
    };
    match MaiClient::new(cfg) {
        Err(SdkError::Config(msg)) => {
            assert!(msg.contains("either api_key or profile_id must be set"));
        }
        Err(other) => panic!("unexpected error: {other:?}"),
        Ok(_) => panic!("expected config error"),
    }
}

#[test]
fn auth_headers_empty_when_no_auth_fields_set() {
    let cfg = MaiClientConfig::default();
    assert!(cfg.auth_headers().is_empty());
}

#[test]
fn auth_headers_includes_api_key_when_set() {
    let cfg = MaiClientConfig {
        api_key: Some("k".to_string()),
        profile_id: String::new(),
        ..MaiClientConfig::default()
    };
    let headers = cfg.auth_headers();
    assert_eq!(headers.len(), 1);
    assert_eq!(headers[0].0, "X-IM-Auth-Token");
    assert_eq!(headers[0].1, "k");
}

#[test]
fn auth_headers_includes_profile_when_set() {
    let cfg = MaiClientConfig {
        api_key: None,
        profile_id: "admin:Admin".to_string(),
        ..MaiClientConfig::default()
    };
    let headers = cfg.auth_headers();
    assert_eq!(headers.len(), 1);
    assert_eq!(headers[0].0, "X-IM-Profile");
    assert!(headers[0].1.starts_with("admin:"));
}

#[test]
fn auth_headers_stable_order_api_key_then_profile() {
    let cfg = MaiClientConfig {
        api_key: Some("k".to_string()),
        profile_id: "p".to_string(),
        ..MaiClientConfig::default()
    };
    let headers = cfg.auth_headers();
    assert_eq!(headers.len(), 2);
    assert_eq!(headers[0].0, "X-IM-Auth-Token");
    assert_eq!(headers[1].0, "X-IM-Profile");
}

#[test]
fn default_base_url_is_localhost_8420() {
    let cfg = MaiClientConfig::default();
    assert_eq!(cfg.base_url, "http://localhost:8420");
}

#[test]
fn default_timeout_is_reasonable() {
    let cfg = MaiClientConfig::default();
    assert!(cfg.timeout >= Duration::from_secs(5));
    assert!(cfg.timeout <= Duration::from_secs(120));
}

#[test]
fn extra_headers_can_be_set() {
    let mut extra = HashMap::new();
    extra.insert("X-Test".to_string(), "1".to_string());
    let cfg = MaiClientConfig {
        api_key: Some("k".to_string()),
        extra_headers: extra,
        ..MaiClientConfig::default()
    };
    let client = MaiClient::new(cfg).expect("client should construct");
    // We can't read the built request headers without issuing a request, but
    // we can assert construction succeeds with extra headers.
    drop(client);
}

#[test]
fn priority_variants_are_distinct() {
    let low = format!("{:?}", RequestPriority::Low);
    let normal = format!("{:?}", RequestPriority::Normal);
    let high = format!("{:?}", RequestPriority::High);
    let critical = format!("{:?}", RequestPriority::Critical);
    assert_ne!(low, normal);
    assert_ne!(normal, high);
    assert_ne!(high, critical);
}

#[test]
fn client_constructs_with_profile_only() {
    let cfg = MaiClientConfig {
        api_key: None,
        profile_id: "admin:Admin".to_string(),
        ..MaiClientConfig::default()
    };
    MaiClient::new(cfg).expect("profile-only construction should be allowed");
}

#[test]
fn default_priority_is_normal() {
    let cfg = MaiClientConfig::default();
    assert_eq!(cfg.priority, RequestPriority::Normal);
}

#[test]
fn config_clone_preserves_auth_fields() {
    let cfg = MaiClientConfig {
        api_key: Some("k".to_string()),
        profile_id: "p".to_string(),
        ..MaiClientConfig::default()
    };
    let c2 = cfg.clone();
    assert_eq!(c2.api_key.as_deref(), Some("k"));
    assert_eq!(c2.profile_id, "p");
}

#[test]
fn config_debug_includes_base_url() {
    let cfg = MaiClientConfig::default();
    let s = format!("{cfg:?}");
    assert!(s.contains("base_url"));
}

#[test]
fn auth_headers_are_owned_strings() {
    let cfg = MaiClientConfig {
        api_key: Some("k".to_string()),
        profile_id: "p".to_string(),
        ..MaiClientConfig::default()
    };
    let headers = cfg.auth_headers();
    assert_eq!(headers[0].1, "k".to_string());
    assert_eq!(headers[1].1, "p".to_string());
}
