//! SEC-95 integration tests: token-bucket rate-limit middleware.
//!
//! These tests exercise the live `axum::Router` stack and verify that
//! the middleware short-circuits requests with `429 Too Many Requests`
//! + `Retry-After` when the configured bucket is exhausted.

use std::sync::Arc;

use tokio::sync::{Mutex, RwLock};

use axum::body::Body;
use axum::http::{Request, StatusCode};
use tower::ServiceExt; // for `oneshot`

use mai_api::audit::MemoryAuditWriter;
use mai_api::auth::{ApiKeyStore, AuthState, RateLimiter as AuthRateLimiter};
use mai_api::config::ServerConfig;
use mai_api::rate_limit::{BucketConfig, RateLimiter};
use mai_api::routes::build_router;
use mai_api::state::AppState;

use mai_core::health::{HealthConfig, HealthMonitor};
use mai_core::hotswap::HotSwapManager;
use mai_core::power::{PowerConfig, PowerStateMachine};
use mai_core::registry::ModelRegistry;
use mai_core::vault::VaultInterface;
use mai_scheduler::DefaultScheduler;

use mai_adapters::config::FrameworkConfig;
use mai_adapters::manager::AdapterManager;

// -- Test Vault Stub -------------------------------------------------------

struct TestVault;

#[async_trait::async_trait]
impl VaultInterface for TestVault {
    async fn load_model_weights(
        &self,
        model_id: &str,
    ) -> Result<Vec<u8>, mai_core::vault::VaultError> {
        Err(mai_core::vault::VaultError::ModelNotFound(
            model_id.to_string(),
        ))
    }

    async fn store_model_package(
        &self,
        _model_id: &str,
        _data: &[u8],
    ) -> Result<(), mai_core::vault::VaultError> {
        Ok(())
    }

    async fn append_audit_entry(&self, _entry: &[u8]) -> Result<(), mai_core::vault::VaultError> {
        Ok(())
    }

    async fn verify_signature(
        &self,
        _data: &[u8],
        _sig: &[u8],
    ) -> Result<bool, mai_core::vault::VaultError> {
        Ok(true)
    }
}

fn build_base_state() -> AppState {
    let scheduler: Arc<dyn mai_scheduler::Scheduler> = Arc::new(DefaultScheduler::new(
        mai_scheduler::SchedulerConfig::default(),
    ));

    let registry = ModelRegistry::new(Box::new(TestVault));
    let registry = Arc::new(RwLock::new(registry));
    let health = Arc::new(RwLock::new(HealthMonitor::new(HealthConfig::default())));
    let power = Arc::new(RwLock::new(PowerStateMachine::new(PowerConfig::default())));

    let legacy_scheduler =
        mai_core::scheduler::Scheduler::new(mai_core::scheduler::SchedulerConfig::default())
            .unwrap();
    let legacy_scheduler = Arc::new(RwLock::new(legacy_scheduler));
    let hotswap = HotSwapManager::new(legacy_scheduler, registry.clone(), health.clone());
    let hotswap = Arc::new(RwLock::new(hotswap));

    let audit_writer = Arc::new(MemoryAuditWriter::new());
    let config = Arc::new(RwLock::new(ServerConfig::default()));

    // Auth is irrelevant to these tests (we rate-limit an auth-exempt path),
    // but the router requires an AuthState.
    let store = ApiKeyStore::new();
    let auth = AuthState::new(store, AuthRateLimiter::default_per_minute());

    let adapter_manager = AdapterManager::new(FrameworkConfig::default());
    let adapter_manager = Arc::new(Mutex::new(adapter_manager));
    let metrics_collector = Arc::new(mai_scheduler::metrics::MetricsCollector::new(
        mai_scheduler::metrics::MetricsConfig::default(),
    ));

    AppState::new(
        scheduler,
        registry,
        health,
        power,
        hotswap,
        audit_writer,
        config,
        auth,
        adapter_manager,
        metrics_collector,
    )
}

fn request(method: &str, uri: &str) -> Request<Body> {
    Request::builder()
        .method(method)
        .uri(uri)
        .body(Body::empty())
        .unwrap()
}

#[tokio::test]
async fn sec_95_rate_limit_middleware_returns_429_with_retry_after() {
    let limiter = Arc::new(RateLimiter::new(&[(
        "/v1/health".to_string(),
        BucketConfig {
            capacity: 2,
            refill_per_sec: 0.01,
        },
    )]));
    let app = build_router(build_base_state().with_rate_limiter(limiter));

    let first = app
        .clone()
        .oneshot(request("GET", "/v1/health"))
        .await
        .unwrap();
    assert_ne!(first.status(), StatusCode::TOO_MANY_REQUESTS);

    let second = app
        .clone()
        .oneshot(request("GET", "/v1/health"))
        .await
        .unwrap();
    assert_ne!(second.status(), StatusCode::TOO_MANY_REQUESTS);

    let third = app.oneshot(request("GET", "/v1/health")).await.unwrap();
    assert_eq!(third.status(), StatusCode::TOO_MANY_REQUESTS);

    let retry_after = third
        .headers()
        .get("retry-after")
        .expect("429 response must include Retry-After")
        .to_str()
        .expect("Retry-After must be valid ASCII");
    let secs: u64 = retry_after
        .parse()
        .expect("Retry-After must parse as an integer seconds value");
    assert!(secs >= 1, "Retry-After must be >= 1 second");
}

#[tokio::test]
async fn sec_95_rate_limit_is_no_op_when_not_installed() {
    let app = build_router(build_base_state());
    for _ in 0..50 {
        let resp = app
            .clone()
            .oneshot(request("GET", "/v1/health"))
            .await
            .unwrap();
        assert_ne!(resp.status(), StatusCode::TOO_MANY_REQUESTS);
    }
}

#[tokio::test]
async fn sec_95_rate_limit_does_not_affect_non_matching_routes() {
    let limiter = Arc::new(RateLimiter::new(&[(
        "/v1/health".to_string(),
        BucketConfig {
            capacity: 1,
            refill_per_sec: 0.01,
        },
    )]));
    let app = build_router(build_base_state().with_rate_limiter(limiter));
    for _ in 0..10 {
        let resp = app
            .clone()
            .oneshot(request("GET", "/v1/models"))
            .await
            .unwrap();
        assert_ne!(resp.status(), StatusCode::TOO_MANY_REQUESTS);
    }
}

#[tokio::test]
async fn sec_95_rate_limit_longest_prefix_wins() {
    let limiter = Arc::new(RateLimiter::new(&[
        (
            "/v1".to_string(),
            BucketConfig {
                capacity: 1,
                refill_per_sec: 0.01,
            },
        ),
        (
            "/v1/health".to_string(),
            BucketConfig {
                capacity: 3,
                refill_per_sec: 0.01,
            },
        ),
    ]));
    let app = build_router(build_base_state().with_rate_limiter(limiter));
    let a = app
        .clone()
        .oneshot(request("GET", "/v1/health"))
        .await
        .unwrap();
    let b = app
        .clone()
        .oneshot(request("GET", "/v1/health"))
        .await
        .unwrap();
    let c = app
        .clone()
        .oneshot(request("GET", "/v1/health"))
        .await
        .unwrap();
    assert_ne!(a.status(), StatusCode::TOO_MANY_REQUESTS);
    assert_ne!(b.status(), StatusCode::TOO_MANY_REQUESTS);
    assert_ne!(c.status(), StatusCode::TOO_MANY_REQUESTS);
    let d = app.oneshot(request("GET", "/v1/health")).await.unwrap();
    assert_eq!(d.status(), StatusCode::TOO_MANY_REQUESTS);
}

#[tokio::test]
async fn sec_95_rate_limit_429_is_counted_in_metrics() {
    let limiter = Arc::new(RateLimiter::new(&[(
        "/v1/health".to_string(),
        BucketConfig {
            capacity: 1,
            refill_per_sec: 0.01,
        },
    )]));
    let app = build_router(build_base_state().with_rate_limiter(limiter));

    let _ = app
        .clone()
        .oneshot(request("GET", "/v1/health"))
        .await
        .unwrap();
    let _ = app
        .clone()
        .oneshot(request("GET", "/v1/health"))
        .await
        .unwrap();

    let resp = app.oneshot(request("GET", "/v1/metrics")).await.unwrap();
    assert_eq!(resp.status(), StatusCode::OK);
    let body = axum::body::to_bytes(resp.into_body(), 64 * 1024)
        .await
        .unwrap();
    let text = String::from_utf8_lossy(&body);
    assert!(
        text.contains("mai_rate_limited_total"),
        "metrics must include rate-limited counter"
    );
}
