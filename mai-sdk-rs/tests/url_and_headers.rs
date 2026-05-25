//! Additional request-shape integration tests for `mai-sdk-rs`.

use std::collections::HashMap;
use std::time::Duration;

use mai_sdk_rs::*;
use serde_json::json;
use wiremock::matchers::{header, method, path};
use wiremock::{Mock, MockServer, ResponseTemplate};

fn client_for(server: &MockServer, cfg: MaiClientConfig) -> MaiClient {
    let mut cfg = cfg;
    cfg.base_url = server.uri();
    MaiClient::new(cfg).expect("client construction must succeed")
}

fn base_cfg_with_key() -> MaiClientConfig {
    MaiClientConfig {
        base_url: "http://localhost:8420".to_string(),
        api_key: Some("test-key".to_string()),
        profile_id: String::new(),
        priority: RequestPriority::Normal,
        timeout: Duration::from_secs(2),
        extra_headers: HashMap::new(),
    }
}

fn chat_req() -> ChatCompletionRequest {
    ChatCompletionRequest {
        model: "phi-4-mini".to_string(),
        messages: vec![ChatMessage {
            role: "user".to_string(),
            content: "hello".to_string(),
            tool_call_id: None,
        }],
        max_tokens: None,
        temperature: None,
        top_p: None,
        stop: None,
        stream: false,
    }
}

#[tokio::test]
async fn base_url_trailing_slash_is_normalized() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/v1/chat/completions"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "id":"chatcmpl-1","object":"chat.completion","created":0,"model":"m",
            "choices":[{"index":0,"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}],
            "usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}
        })))
        .mount(&server)
        .await;

    let mut cfg = base_cfg_with_key();
    cfg.base_url = format!("{}/", server.uri());
    let client = MaiClient::new(cfg).unwrap();
    let resp = client.chat(chat_req()).await.unwrap();
    assert_eq!(resp.id, "chatcmpl-1");
}

#[tokio::test]
async fn request_includes_priority_header() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/v1/chat/completions"))
        .and(header("X-IM-Priority", "high"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "id":"chatcmpl-2","object":"chat.completion","created":0,"model":"m",
            "choices":[{"index":0,"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}],
            "usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}
        })))
        .mount(&server)
        .await;

    let mut cfg = base_cfg_with_key();
    cfg.priority = RequestPriority::High;
    let resp = client_for(&server, cfg).chat(chat_req()).await.unwrap();
    assert_eq!(resp.id, "chatcmpl-2");
}

#[tokio::test]
async fn extra_headers_are_forwarded() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/v1/chat/completions"))
        .and(header("X-Extra", "yes"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "id":"chatcmpl-3","object":"chat.completion","created":0,"model":"m",
            "choices":[{"index":0,"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}],
            "usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}
        })))
        .mount(&server)
        .await;

    let mut cfg = base_cfg_with_key();
    cfg.extra_headers
        .insert("X-Extra".to_string(), "yes".to_string());
    let resp = client_for(&server, cfg).chat(chat_req()).await.unwrap();
    assert_eq!(resp.id, "chatcmpl-3");
}

#[tokio::test]
async fn profile_header_is_allowed_when_api_key_absent() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/v1/chat/completions"))
        .and(header("X-IM-Profile", "admin:Admin"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "id":"chatcmpl-4","object":"chat.completion","created":0,"model":"m",
            "choices":[{"index":0,"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}],
            "usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}
        })))
        .mount(&server)
        .await;

    let cfg = MaiClientConfig {
        api_key: None,
        profile_id: "admin:Admin".to_string(),
        ..base_cfg_with_key()
    };
    let resp = client_for(&server, cfg).chat(chat_req()).await.unwrap();
    assert_eq!(resp.id, "chatcmpl-4");
}

#[tokio::test]
async fn api_key_and_profile_header_can_coexist() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/v1/chat/completions"))
        .and(header("X-IM-Auth-Token", "test-key"))
        .and(header("X-IM-Profile", "admin:Admin"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "id":"chatcmpl-5","object":"chat.completion","created":0,"model":"m",
            "choices":[{"index":0,"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}],
            "usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}
        })))
        .mount(&server)
        .await;

    let cfg = MaiClientConfig {
        profile_id: "admin:Admin".to_string(),
        ..base_cfg_with_key()
    };
    let resp = client_for(&server, cfg).chat(chat_req()).await.unwrap();
    assert_eq!(resp.id, "chatcmpl-5");
}
