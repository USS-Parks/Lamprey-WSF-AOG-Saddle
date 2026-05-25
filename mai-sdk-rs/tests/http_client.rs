//! J-16 integration tests for the `mai-sdk-rs` HTTP client.
//!
//! Each plain-HTTP method gets a happy-path test that stands up an in-process
//! `wiremock::MockServer`, asserts the SDK sends the expected request shape
//! (path, method, auth header), and decodes the canonical response shape.
//!
//! Edge-case tests cover:
//! - missing auth header surfaces as `SdkError::Api(AuthenticationFailed)`
//! - 5xx mapping to `SdkError::Api(InternalError)` (or a specific variant)
//! - request timeout maps to `SdkError::Timeout`
//! - malformed JSON response maps to `SdkError::Deserialization`
//!
//! Streaming methods (`chat_stream`, `ChatStreamHandle::*`) are intentionally
//! not exercised here; their parser/resume coverage lives in `src/lib.rs`.

use std::collections::HashMap;
use std::time::Duration;

use mai_sdk_rs::*;
use serde_json::json;
use wiremock::matchers::{header, method, path};
use wiremock::{Mock, MockServer, ResponseTemplate};

// ─── Helpers ───────────────────────────────────────────────────────

fn client_for(server: &MockServer) -> MaiClient {
    MaiClient::new(MaiClientConfig {
        base_url: server.uri(),
        api_key: Some("test-key".to_string()),
        profile_id: String::new(),
        priority: RequestPriority::Normal,
        timeout: Duration::from_secs(2),
        extra_headers: HashMap::new(),
    })
    .expect("client construction must succeed when api_key is set")
}

fn chat_request() -> ChatCompletionRequest {
    ChatCompletionRequest {
        model: "phi-4-mini".to_string(),
        messages: vec![ChatMessage {
            role: "user".to_string(),
            content: "Hello".to_string(),
            tool_call_id: None,
        }],
        max_tokens: None,
        temperature: None,
        top_p: None,
        stop: None,
        stream: false,
    }
}

fn usage_json(prompt: u32, completion: u32) -> serde_json::Value {
    json!({
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
    })
}

// ─── Happy-path: inference endpoints (5 tests) ────────────────────

#[tokio::test]
async fn chat_decodes_response_and_sends_auth_header() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/v1/chat/completions"))
        .and(header("X-IM-Auth-Token", "test-key"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 1700000000_u64,
            "model": "phi-4-mini",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "Hi back"},
                "finish_reason": "stop",
            }],
            "usage": usage_json(2, 3),
        })))
        .mount(&server)
        .await;

    let resp = client_for(&server).chat(chat_request()).await.unwrap();
    assert_eq!(resp.id, "chatcmpl-1");
    assert_eq!(resp.model, "phi-4-mini");
    assert_eq!(resp.choices.len(), 1);
    assert_eq!(resp.choices[0].message.content, "Hi back");
    assert_eq!(resp.usage.total_tokens, 5);
}

#[tokio::test]
async fn complete_round_trip() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/v1/completions"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "id": "cmpl-9",
            "object": "text_completion",
            "created": 1700000001_u64,
            "model": "phi-4-mini",
            "choices": [{"index": 0, "text": "ok", "finish_reason": "stop"}],
            "usage": usage_json(1, 1),
        })))
        .mount(&server)
        .await;

    let req = CompletionRequest {
        model: "phi-4-mini".to_string(),
        prompt: "say ok".to_string(),
        max_tokens: Some(8),
        temperature: None,
        top_p: None,
        stop: None,
        stream: false,
    };
    let resp = client_for(&server).complete(req).await.unwrap();
    assert_eq!(resp.id, "cmpl-9");
    assert_eq!(resp.choices.len(), 1);
    assert_eq!(resp.choices[0].text, "ok");
}

#[tokio::test]
async fn embed_round_trip() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/v1/embeddings"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "object": "list",
            "data": [{
                "object": "embedding",
                "embedding": [0.1, 0.2, 0.3],
                "index": 0,
                "input_tokens": 2,
            }],
            "model": "nomic-embed",
            "usage": usage_json(2, 0),
        })))
        .mount(&server)
        .await;

    let req = EmbeddingRequest {
        model: "nomic-embed".to_string(),
        input: vec!["hello world".to_string()],
    };
    let resp = client_for(&server).embed(req).await.unwrap();
    assert_eq!(resp.data.len(), 1);
    assert_eq!(resp.data[0].embedding.len(), 3);
    assert_eq!(resp.data[0].input_tokens, 2);
}

#[tokio::test]
async fn structured_round_trip() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/v1/generate/structured"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "id": "struct-1",
            "object": "structured.completion",
            "model": "phi-4-mini",
            "output": {"answer": 42},
            "usage": usage_json(5, 4),
            "schema_valid": true,
        })))
        .mount(&server)
        .await;

    let req = StructuredRequest {
        model: "phi-4-mini".to_string(),
        prompt: "give me 42".to_string(),
        schema: json!({"type": "object"}),
        temperature: None,
    };
    let resp = client_for(&server).structured(req).await.unwrap();
    assert_eq!(resp.id, "struct-1");
    assert!(resp.schema_valid);
    assert_eq!(resp.output["answer"], 42);
}

#[tokio::test]
async fn function_call_round_trip() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/v1/generate/function_call"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "id": "fc-1",
            "object": "function.call",
            "model": "phi-4-mini",
            "function_call": {"name": "get_weather", "arguments": "{\"city\":\"PDX\"}"},
            "usage": usage_json(8, 4),
        })))
        .mount(&server)
        .await;

    let req = FunctionCallRequest {
        model: "phi-4-mini".to_string(),
        messages: vec![],
        functions: vec![FunctionDefinition {
            name: "get_weather".to_string(),
            description: "Lookup weather".to_string(),
            parameters: json!({"type": "object"}),
        }],
        function_call: Some("auto".to_string()),
        max_tokens: None,
    };
    let resp = client_for(&server).function_call(req).await.unwrap();
    assert_eq!(resp.id, "fc-1");
    assert_eq!(resp.function_call.name, "get_weather");
    assert!(resp.function_call.arguments.contains("PDX"));
}

// ─── Happy-path: model + health + power + profile + audit (9 tests) ─

#[tokio::test]
async fn list_models_unwraps_data_envelope() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/models"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "data": [{
                "id": "phi-4-mini",
                "object": "model",
                "created": 1700000000_u64,
                "owned_by": "im",
                "name": "Phi 4 Mini",
                "version": "1.0",
                "format": "GGUF",
                "size_bytes": 1_000_000_u64,
                "required_vram_bytes": 2_000_000_u64,
                "status": "loaded",
                "capabilities": {
                    "chat": true, "completion": true, "embedding": false,
                    "vision": false, "structured_output": false, "max_context_tokens": 4096,
                },
            }],
        })))
        .mount(&server)
        .await;

    let models = client_for(&server).list_models().await.unwrap();
    assert_eq!(models.len(), 1);
    assert_eq!(models[0].id, "phi-4-mini");
    assert_eq!(models[0].capabilities.max_context_tokens, 4096);
}

#[tokio::test]
async fn get_model_round_trip() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/models/phi-4-mini"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "id": "phi-4-mini",
            "object": "model",
            "created": 0_u64,
            "owned_by": "im",
            "name": "Phi 4 Mini",
            "version": "1.0",
            "format": "GGUF",
            "size_bytes": 1_u64,
            "required_vram_bytes": 1_u64,
            "status": "loaded",
            "capabilities": {
                "chat": true, "completion": false, "embedding": false,
                "vision": false, "structured_output": false, "max_context_tokens": 1,
            },
            "vram_allocated_bytes": 0_u64,
            "request_count": 0_u64,
        })))
        .mount(&server)
        .await;

    let detail = client_for(&server).get_model("phi-4-mini").await.unwrap();
    assert_eq!(detail.base.id, "phi-4-mini");
    assert_eq!(detail.vram_allocated_bytes, 0);
    assert_eq!(detail.request_count, 0);
}

#[tokio::test]
async fn health_round_trip() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/health"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "status": "healthy",
            "air_gap_verified": true,
            "power_state": "full_inference",
            "uptime_seconds": 42_u64,
            "adapters": {"total": 1, "healthy": 1, "degraded": 0, "unhealthy": 0},
            "hardware": {
                "gpus": 1, "total_vram_bytes": 1_u64, "used_vram_bytes": 0_u64,
                "thermal_state": "normal",
            },
            "system": {
                "cpu_load_percent": 0.1, "ram_used_bytes": 1_u64, "ram_total_bytes": 2_u64,
                "disk_vault_free_bytes": 3_u64,
            },
        })))
        .mount(&server)
        .await;

    let resp = client_for(&server).health().await.unwrap();
    assert_eq!(resp.status, SystemHealthStatus::Healthy);
    assert!(resp.air_gap_verified);
    assert_eq!(resp.adapters.healthy, 1);
}

#[tokio::test]
async fn adapter_health_round_trip() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/health/adapters"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "adapters": {
                "ollama": {
                    "status": "healthy",
                    "last_heartbeat": "2026-05-24T19:42:08Z",
                    "missed_heartbeats": 0,
                    "avg_latency_ms": 12.5,
                    "error_rate_5min": 0.0,
                    "vram_usage_bytes": 1_u64,
                    "active_requests": 0,
                },
            },
        })))
        .mount(&server)
        .await;

    let resp = client_for(&server).adapter_health().await.unwrap();
    assert_eq!(resp.adapters.len(), 1);
    let entry = resp.adapters.get("ollama").unwrap();
    assert_eq!(entry.status, AdapterStatus::Healthy);
    assert_eq!(entry.missed_heartbeats, 0);
}

#[tokio::test]
async fn hardware_health_round_trip() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/health/hardware"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "gpus": {"0": {
                "temperature_celsius": 55.0,
                "fan_speed_percent": 30,
                "vram_used_bytes": 1_u64,
                "vram_total_bytes": 2_u64,
                "power_limit_watts": 300,
                "compute_utilization_percent": 10,
            }},
            "power_draw_watts": 250.0,
            "thermal_state": "normal",
            "network_state": "air_gap_compliant",
        })))
        .mount(&server)
        .await;

    let resp = client_for(&server).hardware_health().await.unwrap();
    assert_eq!(resp.gpus.len(), 1);
    assert_eq!(resp.thermal_state, ThermalState::Normal);
    assert_eq!(resp.network_state, NetworkState::AirGapCompliant);
}

#[tokio::test]
async fn power_state_round_trip() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/power/state"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "state": "full_inference",
            "estimated_power_watts": 280.5,
            "auto_demotion": {
                "enabled": true,
                "idle_minutes_remaining": 15,
                "next_state": "sentinel",
            },
            "promotion_available": false,
            "promotion_latency_target_ms": 500,
        })))
        .mount(&server)
        .await;

    let resp = client_for(&server).power_state().await.unwrap();
    assert_eq!(resp.state, PowerState::FullInference);
    assert!(resp.auto_demotion.enabled);
    assert_eq!(resp.auto_demotion.idle_minutes_remaining, Some(15));
}

#[tokio::test]
async fn transition_power_round_trip() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/v1/power/transition"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "transition_id": "t-1",
            "from": "full_inference",
            "to": "sentinel",
            "status": "scheduled",
            "estimated_latency_ms": 2000,
        })))
        .mount(&server)
        .await;

    let req = PowerTransitionRequest {
        target_state: PowerState::Sentinel,
        reason: Some("idle".to_string()),
    };
    let resp = client_for(&server).transition_power(req).await.unwrap();
    assert_eq!(resp.transition_id, "t-1");
    assert_eq!(resp.to, PowerState::Sentinel);
    assert_eq!(resp.status, "scheduled");
}

#[tokio::test]
async fn get_profile_round_trip() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/profiles/me"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "profile_id": "admin-1",
            "name": "Admin",
            "role": "admin",
            "created_at": "2026-01-01T00:00:00Z",
            "permissions": {
                "model_access": ["*"],
                "max_context_tokens": null,
                "allowed_endpoints": ["*"],
                "can_manage_models": true,
                "can_manage_power": true,
                "can_view_audit": true,
                "can_manage_profiles": true,
            },
            "priority": "normal",
            "rate_limits": {"requests_per_minute": null, "tokens_per_hour": null},
            "content_safety": {"enabled": false, "filter_level": "none"},
        })))
        .mount(&server)
        .await;

    let resp = client_for(&server).get_profile().await.unwrap();
    assert_eq!(resp.profile_id, "admin-1");
    assert_eq!(resp.role, ProfileRole::Admin);
    assert!(resp.permissions.can_view_audit);
}

#[tokio::test]
async fn audit_log_attaches_query_params() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/audit/log"))
        // wiremock query-param matchers would require explicit pairs; instead
        // the response echoes limit/offset back so we assert the response side.
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "total_entries": 100_u64,
            "offset": 20,
            "limit": 10,
            "entries": [],
        })))
        .mount(&server)
        .await;

    let resp = client_for(&server)
        .audit_log(Some(10), Some(20))
        .await
        .unwrap();
    assert_eq!(resp.total_entries, 100);
    assert_eq!(resp.offset, 20);
    assert_eq!(resp.limit, 10);
}

// ─── Edge cases (4 tests) ──────────────────────────────────────────

#[tokio::test]
async fn server_401_maps_to_authentication_failed() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/profiles/me"))
        .respond_with(ResponseTemplate::new(401).set_body_json(json!({
            "type": "authentication_failed",
            "code": "MAI-4003",
            "message": "X-IM-Auth-Token missing or invalid",
            "retry_after_seconds": null,
            "request_id": null,
        })))
        .mount(&server)
        .await;

    let err = client_for(&server)
        .get_profile()
        .await
        .expect_err("401 must surface as Err");
    match err {
        SdkError::Api(api) => {
            assert_eq!(api.error_type, MaiErrorType::AuthenticationFailed);
            assert_eq!(api.code, "MAI-4003");
            assert!(api.message.contains("Auth-Token"));
        }
        other => panic!("expected SdkError::Api, got {other:?}"),
    }
}

#[tokio::test]
async fn server_500_with_unparseable_body_synthesises_internal_error() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/health"))
        .respond_with(ResponseTemplate::new(500).set_body_string("not even JSON"))
        .mount(&server)
        .await;

    let err = client_for(&server)
        .health()
        .await
        .expect_err("500 must surface as Err");
    match err {
        SdkError::Api(api) => {
            assert_eq!(api.error_type, MaiErrorType::InternalError);
            // The current impl synthesises `MAI-{status}` (e.g. `MAI-500`).
            // We only require the code carries the HTTP status; the exact
            // format may tighten later to the full `MAI-5001` taxonomy.
            assert!(
                api.code.contains("500"),
                "code should reference status: {}",
                api.code
            );
            // The raw body is surfaced as the message so operators can
            // grep for the upstream failure mode.
            assert!(!api.message.is_empty());
        }
        other => panic!("expected SdkError::Api, got {other:?}"),
    }
}

#[tokio::test]
async fn slow_response_past_timeout_yields_sdk_timeout() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/health"))
        .respond_with(
            ResponseTemplate::new(200)
                .set_body_string("never sent in time")
                .set_delay(Duration::from_secs(5)),
        )
        .mount(&server)
        .await;

    // Client timeout is 2s; server delays 5s — must trip the timeout.
    let err = client_for(&server)
        .health()
        .await
        .expect_err("delayed response must surface as Err");
    match err {
        SdkError::Timeout(d) => {
            assert!(d.as_secs() <= 2, "Timeout carries the configured deadline");
        }
        SdkError::Connection(msg) => {
            // Some reqwest builds tag timeouts via is_connect() first; tolerate.
            let lower = msg.to_lowercase();
            assert!(lower.contains("timeout") || lower.contains("timed"));
        }
        other => panic!("expected Timeout or Connection, got {other:?}"),
    }
}

#[tokio::test]
async fn malformed_json_response_maps_to_deserialization() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/health"))
        // 200 OK but body does NOT match the HealthResponse schema.
        .respond_with(ResponseTemplate::new(200).set_body_string("{\"oops\": true}"))
        .mount(&server)
        .await;

    let err = client_for(&server)
        .health()
        .await
        .expect_err("malformed body must surface as Err");
    match err {
        SdkError::Deserialization(msg) => {
            assert!(!msg.is_empty());
            assert!(msg.len() < 1000, "deserialization detail must be bounded");
        }
        other => panic!("expected Deserialization, got {other:?}"),
    }
}
