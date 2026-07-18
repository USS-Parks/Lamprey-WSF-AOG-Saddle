//! Front-door WSF authentication.
//!
//! Every API request must carry a valid, in-budget, unrevoked WSF trust token,
//! verified **before** the admission chain runs (unauth /
//! over-budget / revoked is rejected pre-admission). Verification is **local
//! asymmetric crypto** — ML-DSA-87 over the token's canonical payload — so it is
//! sub-millisecond and offline, with no OpenBao round-trip on the hot path.
//! This is doctrine I-3 in force: authority is re-earned by verifying the token
//! on *every* request, never by trusting a prior session, and I-4: any
//! uncertainty (missing, malformed, unverifiable, expired, revoked) fails closed.
//!
//! The token is presented as `x-wsf-token: base64(json(TrustToken))`. The
//! verified [`Principal`] is stashed in request extensions for the handler and
//! the admission chain (its `mutate`/`receipt` stages stamp the token as
//! provenance and attenuate a child from it).

use std::collections::HashSet;
use std::sync::{Arc, Mutex, RwLock};

use axum::extract::{Request, State};
use axum::http::HeaderMap;
use axum::middleware::Next;
use axum::response::Response;
use base64::Engine;
use base64::engine::general_purpose::STANDARD as BASE64;
use fabric_contracts::{
    Budget, CanonicalResource, RequestOperation, TrustToken, VerifiedRequestContext,
};
use fabric_crypto::providers::MlDsa87Verifier;
use fabric_revocation::{MonotonicRevocationStore, RevocationError, RevocationSnapshot};
use mai_compliance::AggregateDecision;
use saddle_bridge::{
    AdmissionGrant, AdmissionSpec, AogPolicy, BridgeError, GrantIssuer, PolicyInput,
    VerifiedSaddleRequest,
};
use saddle_estate::Kind;

use crate::AppState;
use crate::admission::Principal;
use crate::error::ApiError;

/// Header carrying the base64-encoded JSON trust token.
pub const TOKEN_HEADER: &str = "x-wsf-token";
/// Required one-use nonce for every desired-state mutation.
pub const NONCE_HEADER: &str = "x-saddle-nonce";

const CURRENT_BUNDLE: &str = "2026.07.saddle";

struct FencePolicy;

impl AogPolicy for FencePolicy {
    fn evaluate(&self, _input: &PolicyInput<'_>) -> AggregateDecision {
        AggregateDecision {
            allowed: false,
            route: None,
            flags: Vec::new(),
            reasons: Vec::new(),
            modules_applied: Vec::new(),
        }
    }
}

/// The estate-driven kill view: what the declarative `RevocationIntent`
/// objects currently revoke, folded in by the revocation-indexing controller
/// and consulted by the front door on **every** request. This is the
/// kernel-local leg of I-9; the same intents fan out to signed
/// `fabric-revocation` snapshots for other replicas and air-gapped nodes.
#[derive(Debug, Default)]
pub struct RevocationView {
    pub tokens: HashSet<String>,
    pub subjects: HashSet<String>,
    pub tenants: HashSet<String>,
}

impl RevocationView {
    /// Does this view revoke `token`?
    #[must_use]
    pub fn revokes(&self, token: &TrustToken) -> bool {
        self.tokens.contains(&token.token_id)
            || self.subjects.contains(&token.subject_hash)
            || self.tenants.contains(&token.tenant_id)
    }
}

/// The front-door authenticator: the WSF trust-anchor public key every presented
/// token must verify under, plus two kill switches consulted on every request —
/// an optional (signature-verified) revocation snapshot, and the live
/// [`RevocationView`] the revocation-indexing controller keeps current from
/// declarative `RevocationIntent` objects.
pub struct Authenticator {
    token_public_key: Vec<u8>,
    revocation: MonotonicRevocationStore,
    request_issuer: Mutex<GrantIssuer<FencePolicy>>,
    current_bundle: String,
    live: Arc<RwLock<RevocationView>>,
}

impl Authenticator {
    /// Build an authenticator anchored on the WSF trust public key.
    #[must_use]
    pub fn new(token_public_key: Vec<u8>) -> Self {
        Self {
            token_public_key,
            revocation: MonotonicRevocationStore::new(),
            request_issuer: Mutex::new(GrantIssuer::new(FencePolicy)),
            current_bundle: CURRENT_BUNDLE.to_owned(),
            live: Arc::new(RwLock::new(RevocationView::default())),
        }
    }

    /// The shared live-revocation handle. The revocation-indexing controller
    /// writes it; [`authenticate`](Authenticator::authenticate) reads it on
    /// every request.
    #[must_use]
    pub fn live_revocation(&self) -> Arc<RwLock<RevocationView>> {
        Arc::clone(&self.live)
    }

    /// Attach a revocation snapshot (the kill switch). The snapshot's own
    /// signature is verified against the trust anchor here — a snapshot that does
    /// not verify is refused, never silently ignored (fail-closed, doctrine I-4).
    ///
    /// # Errors
    /// [`RevocationError`] if the snapshot signature does not verify.
    pub fn with_revocation(
        mut self,
        snapshot: RevocationSnapshot,
    ) -> Result<Self, RevocationError> {
        self.revocation
            .advance(snapshot, &MlDsa87Verifier, &self.token_public_key)?;
        Ok(self)
    }

    /// Verify a presented token and yield the authenticated principal, or refuse.
    /// Every failure resolves toward *less* privilege (doctrine I-4).
    ///
    /// # Errors
    /// [`ApiError::Unauthenticated`] when the token is missing, malformed, fails
    /// signature/expiry, or is revoked; [`ApiError::BudgetExhausted`] when over
    /// budget.
    pub fn authenticate(&self, headers: &HeaderMap) -> Result<Principal, ApiError> {
        let raw = headers
            .get(TOKEN_HEADER)
            .and_then(|v| v.to_str().ok())
            .ok_or(ApiError::Unauthenticated)?;
        let bytes = BASE64
            .decode(raw.trim())
            .map_err(|_| ApiError::Unauthenticated)?;
        let token: TrustToken =
            serde_json::from_slice(&bytes).map_err(|_| ApiError::Unauthenticated)?;

        // Signature + on-token revocation status (local ML-DSA verify).
        fabric_token::verify(&token, &MlDsa87Verifier, &self.token_public_key)
            .map_err(|_| ApiError::Unauthenticated)?;

        // Expiry (the token's own expiry caveat).
        if fabric_token::is_expired(&token, chrono::Utc::now())
            .map_err(|_| ApiError::Unauthenticated)?
        {
            return Err(ApiError::Unauthenticated);
        }

        // Kill switch, snapshot leg: any revocation dimension (token, subject,
        // signing key, issuer, bundle version, tenant, service identity) halts
        // the next call — matching the gateway's complete predicate.
        if let Some(snap) = self.revocation.current()
            && snap.revokes(&token).is_some()
        {
            return Err(ApiError::Unauthenticated);
        }

        // Kill switch, estate leg: the live RevocationIntent view. A
        // poisoned lock is uncertainty — fail closed (doctrine I-4).
        let revoked = self.live.read().map_or(true, |view| view.revokes(&token));
        if revoked {
            return Err(ApiError::Unauthenticated);
        }

        // Budget pre-flight — reject an exhausted token before it acts.
        if let Some(budget) = &token.budget
            && budget_exhausted(budget)
        {
            return Err(ApiError::BudgetExhausted);
        }

        Ok(Principal::authenticated(token))
    }

    /// Bind one authenticated token to the server-resolved Saddle operation,
    /// tenant, resource identity, current revocation sequence, and a one-use
    /// nonce. The returned proof value cannot be constructed from wire JSON.
    pub fn verify_saddle_request(
        &self,
        principal: &Principal,
        kind: Kind,
        name: &str,
        headers: &HeaderMap,
    ) -> Result<VerifiedSaddleRequest, ApiError> {
        let token = principal.token().ok_or(ApiError::Unauthenticated)?;
        if token.budget.as_ref().is_some_and(budget_exhausted) {
            return Err(ApiError::BudgetExhausted);
        }
        let nonce = headers
            .get(NONCE_HEADER)
            .and_then(|value| value.to_str().ok())
            .filter(|value| !value.trim().is_empty())
            .ok_or(ApiError::Unauthenticated)?;
        let resource = CanonicalResource::resolved(
            kind.to_string(),
            name,
            principal.tenant().map(str::to_owned),
        )
        .map_err(|error| ApiError::Forbidden(error.to_string()))?;
        let context = VerifiedRequestContext::establish(
            principal.request_principal().clone(),
            RequestOperation::SaddleAdmission,
            resource,
        )
        .map_err(|error| ApiError::Forbidden(error.to_string()))?;
        self.request_issuer
            .lock()
            .map_err(|_| ApiError::Unauthenticated)?
            .verify_request(
                context,
                token,
                nonce,
                chrono::Utc::now(),
                &MlDsa87Verifier,
                &self.token_public_key,
                &self.current_bundle,
                &self.revocation,
            )
            .map_err(map_bridge_auth_error)
    }

    /// Recheck current revocation and narrow a verified request into one exact
    /// admission grant using the already-composed deny-wins AOG decision.
    pub fn issue_admission_grant(
        &self,
        request: &VerifiedSaddleRequest,
        spec: AdmissionSpec,
        decision: AggregateDecision,
    ) -> Result<AdmissionGrant, ApiError> {
        struct DecisionPolicy(AggregateDecision);
        impl AogPolicy for DecisionPolicy {
            fn evaluate(&self, _input: &PolicyInput<'_>) -> AggregateDecision {
                self.0.clone()
            }
        }
        GrantIssuer::new(DecisionPolicy(decision))
            .issue_admission(request, spec, chrono::Utc::now(), &self.revocation)
            .map_err(map_bridge_grant_error)
    }
}

fn map_bridge_auth_error(_error: BridgeError) -> ApiError {
    ApiError::Unauthenticated
}

fn map_bridge_grant_error(error: BridgeError) -> ApiError {
    match error {
        BridgeError::Token(_)
        | BridgeError::Revocation(_)
        | BridgeError::Replay
        | BridgeError::ReplayUnavailable(_)
        | BridgeError::LineageMismatch => ApiError::Unauthenticated,
        other => ApiError::Forbidden(other.to_string()),
    }
}

/// Any budget dimension exhausted (a cap of 0 means that axis is unused).
fn budget_exhausted(b: &Budget) -> bool {
    (b.token_cap > 0 && b.tokens_spent >= b.token_cap)
        || (b.usd_cap_cents > 0 && b.usd_spent_cents >= b.usd_cap_cents)
        || (b.tool_call_cap > 0 && b.tool_calls_spent >= b.tool_call_cap)
}

/// axum middleware: authenticate an API request before its handler runs, and
/// stash the verified [`Principal`] in request extensions for the handler +
/// admission chain. Applied only to `/apis/**` — health probes stay open.
///
/// # Errors
/// Propagates the [`Authenticator::authenticate`] refusal as the response.
pub async fn require_token(
    State(state): State<AppState>,
    mut req: Request,
    next: Next,
) -> Result<Response, ApiError> {
    let principal = state.authenticator.authenticate(req.headers())?;
    req.extensions_mut().insert(principal);
    Ok(next.run(req).await)
}
