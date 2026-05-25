//! Expanded integration tests for non-streaming endpoints.

use std::collections::HashMap;
use std::time::Duration;

use mai_sdk_rs::*;
use serde_json::json;
use wiremock::matchers::{header, method, path, query_param};
use wiremock::{Mock, MockServer, ResponseTemplate};

fn client_for(server: &MockServer) -> MaiClient {
    MaiClient::new(MaiClientConfig {
        base_url: server.uri(),
        api_key: Some("test-key".to_string()),
        profile_id: String::new(),
        priority: RequestPriority::Normal,
        timeout: Duration::from_secs(2),
        extra_headers: HashMap::new(),
    })
    .unwrap()
}

#[tokio::test]
async fn list_models_decodes_envelope() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/models"))
        .and(header("X-IM-Auth-Token", "test-key"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "object":"list",
            "data":[{
                "id":"m1",
                "object":"model",
                "created":0_u64,
                "owned_by":"im",
                "name":"phi-4-mini",
                "version":"1",
                "format":"GGUF",
                "size_bytes": 1_u64,
                "required_vram_bytes": 2_u64,
                "status":"loaded",
                "capabilities":{
                    "chat": true,
                    "completion": true,
                    "embedding": false,
                    "vision": false,
                    "structured_output": false,
                    "max_context_tokens": 8192,
                    "supported_languages":[]
                },
                "compatible_backends": [],
            }]
        })))
        .mount(&server)
        .await;

    let models = client_for(&server).list_models().await.unwrap();
    assert_eq!(models.len(), 1);
    assert_eq!(models[0].id, "m1");
}

#[tokio::test]
async fn get_model_fetches_by_id() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/models/phi"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "id":"phi",
            "object":"model",
            "created":0_u64,
            "owned_by":"im",
            "name":"phi-4-mini",
            "version":"1",
            "format":"GGUF",
            "size_bytes":1_u64,
            "required_vram_bytes":2_u64,
            "status":"loaded",
            "capabilities":{
                "chat": true,
                "completion": true,
                "embedding": false,
                "vision": false,
                "structured_output": false,
                "max_context_tokens": 8192,
                "supported_languages":[]
            },
            "compatible_backends": [],
            "adapter_assignment": null,
            "vram_allocated_bytes": 0_u64,
            "request_count": 0_u64,
            "last_used": null
        })))
        .mount(&server)
        .await;

    let m = client_for(&server).get_model("phi").await.unwrap();
    assert_eq!(m.base.id, "phi");
    assert_eq!(m.base.size_bytes, 1);
}

#[tokio::test]
async fn health_endpoint_decodes() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/health"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "status":"healthy",
            "air_gap_verified": true,
            "power_state": "full_inference",
            "uptime_seconds": 1_u64,
            "adapters":{"total":1_u32,"healthy":1_u32,"degraded":0_u32,"unhealthy":0_u32},
            "hardware":{"gpus":0_u32,"total_vram_bytes":0_u64,"used_vram_bytes":0_u64,"thermal_state":"normal"},
            "system":{"cpu_load_percent": 0.0, "ram_used_bytes": 0_u64, "ram_total_bytes": 0_u64, "disk_vault_free_bytes": 0_u64}
        })))
        .mount(&server)
        .await;

    let h = client_for(&server).health().await.unwrap();
    assert_eq!(h.status, SystemHealthStatus::Healthy);
    assert!(h.uptime_seconds >= 1);
}

#[tokio::test]
async fn adapter_health_endpoint_decodes_map() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/health/adapters"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "adapters": {
                "ollama": {
                    "status": "healthy",
                    "last_heartbeat": "now",
                    "missed_heartbeats": 0,
                    "avg_latency_ms": 1.0,
                    "error_rate_5min": 0.0,
                    "vram_usage_bytes": 0,
                    "active_requests": 0
                }
            }
        })))
        .mount(&server)
        .await;

    let map = client_for(&server).adapter_health().await.unwrap();
    let entry = map.adapters.get("ollama").unwrap();
    assert_eq!(entry.status, AdapterStatus::Healthy);
}

#[tokio::test]
async fn hardware_health_endpoint_decodes() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/health/hardware"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "gpus": {},
            "power_draw_watts": 0.0,
            "thermal_state": "normal",
            "network_state": "air_gap_compliant"
        })))
        .mount(&server)
        .await;

    let hw = client_for(&server).hardware_health().await.unwrap();
    assert!(hw.gpus.is_empty());
}

#[tokio::test]
async fn power_state_endpoint_decodes() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/power/state"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "state":"full_inference",
            "estimated_power_watts": 10.0,
            "auto_demotion": {"enabled": false, "idle_minutes_remaining": null, "next_state": null},
            "promotion_available": true,
            "promotion_latency_target_ms": 250_u32
        })))
        .mount(&server)
        .await;

    let ps = client_for(&server).power_state().await.unwrap();
    assert_eq!(ps.state, PowerState::FullInference);
}

#[tokio::test]
async fn get_profile_defaults_to_me_when_profile_id_empty() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/profiles/me"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "profile_id":"me",
            "name":"me",
            "role":"admin",
            "created_at":"2026-01-01T00:00:00Z",
            "permissions": {
                "model_access": ["*"],
                "max_context_tokens": null,
                "allowed_endpoints": ["*"],
                "can_manage_models": true,
                "can_manage_power": true,
                "can_view_audit": true,
                "can_manage_profiles": true
            },
            "priority": "normal",
            "rate_limits": {"requests_per_minute": null, "tokens_per_hour": null},
            "content_safety": {"enabled": true, "filter_level": "moderate"}
        })))
        .mount(&server)
        .await;

    let p = client_for(&server).get_profile().await.unwrap();
    assert_eq!(p.profile_id, "me");
}

#[tokio::test]
async fn audit_log_builds_query_params() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/audit/log"))
        .and(query_param("limit", "10"))
        .and(query_param("offset", "5"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "total_entries": 0_u64,
            "offset":5_u32,
            "limit":10_u32,
            "entries":[]
        })))
        .mount(&server)
        .await;

    let log = client_for(&server)
        .audit_log(Some(10), Some(5))
        .await
        .unwrap();
    assert_eq!(log.limit, 10);
    assert_eq!(log.offset, 5);
    assert!(log.entries.is_empty());
}

#[tokio::test]
async fn audit_log_without_query_params_works() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/audit/log"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "total_entries": 0_u64,
            "offset":0_u32,
            "limit":25_u32,
            "entries":[]
        })))
        .mount(&server)
        .await;

    let log = client_for(&server).audit_log(None, None).await.unwrap();
    assert_eq!(log.offset, 0);
    assert_eq!(log.limit, 25);
}

#[tokio::test]
async fn transition_power_posts_body() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/v1/power/transition"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "transition_id":"t-1",
            "from":"sentinel",
            "to":"full_inference",
            "status":"accepted",
            "estimated_latency_ms": 100_u32
        })))
        .mount(&server)
        .await;

    let resp = client_for(&server)
        .transition_power(PowerTransitionRequest {
            target_state: PowerState::FullInference,
            reason: None,
        })
        .await
        .unwrap();
    assert_eq!(resp.transition_id, "t-1");
    assert_eq!(resp.to, PowerState::FullInference);
}

#[tokio::test]
async fn get_profile_uses_profile_id_when_set() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/profiles/kid"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "profile_id":"kid",
            "name":"kid",
            "role":"child",
            "created_at":"2026-01-01T00:00:00Z",
            "permissions": {
                "model_access": ["*"],
                "max_context_tokens": 2048_u32,
                "allowed_endpoints": ["/v1/chat/completions", "/v1/health*"],
                "can_manage_models": false,
                "can_manage_power": false,
                "can_view_audit": false,
                "can_manage_profiles": false
            },
            "priority": "low",
            "rate_limits": {"requests_per_minute": 60_u32, "tokens_per_hour": 10000_u64},
            "content_safety": {"enabled": true, "filter_level": "strict"}
        })))
        .mount(&server)
        .await;

    let client = MaiClient::new(MaiClientConfig {
        base_url: server.uri(),
        api_key: Some("test-key".to_string()),
        profile_id: "kid".to_string(),
        priority: RequestPriority::Normal,
        timeout: Duration::from_secs(2),
        extra_headers: HashMap::new(),
    })
    .unwrap();

    let p = client.get_profile().await.unwrap();
    assert_eq!(p.profile_id, "kid");
}

#[tokio::test]
async fn model_list_empty_is_ok() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/models"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "object":"list",
            "data":[]
        })))
        .mount(&server)
        .await;
    let models = client_for(&server).list_models().await.unwrap();
    assert!(models.is_empty());
}

#[tokio::test]
async fn adapter_health_empty_map_is_ok() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/health/adapters"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "adapters": {}
        })))
        .mount(&server)
        .await;
    let map = client_for(&server).adapter_health().await.unwrap();
    assert!(map.adapters.is_empty());
}

#[tokio::test]
async fn power_state_auto_demotion_enabled_decodes() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/power/state"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "state":"sentinel",
            "estimated_power_watts": 2.0,
            "auto_demotion": {"enabled": true, "idle_minutes_remaining": 5_u32, "next_state": "deep_vault_sleep"},
            "promotion_available": false,
            "promotion_latency_target_ms": 500_u32
        })))
        .mount(&server)
        .await;
    let ps = client_for(&server).power_state().await.unwrap();
    assert_eq!(ps.state, PowerState::Sentinel);
    assert!(ps.auto_demotion.enabled);
    assert_eq!(ps.auto_demotion.idle_minutes_remaining, Some(5));
    assert_eq!(
        ps.auto_demotion.next_state,
        Some(PowerState::DeepVaultSleep)
    );
}
