//! `saddle-bridge` freezes the authority-bearing seams between WSF, Saddle,
//! and AOG. It verifies WSF authority; it does not sign tokens, compose policy,
//! or append receipts. Those responsibilities remain in `fabric-token`,
//! `fabric-revocation`, `mai-compliance`, and `wsf-ledger`.
//!
//! Authority-bearing values are serialize-only and have private fields. A wire
//! body can describe a requested narrowing, but cannot manufacture proof that
//! the narrowing was authorized:
//!
//! ```compile_fail
//! use saddle_bridge::AdmissionGrant;
//! let _: AdmissionGrant = serde_json::from_str("{}").unwrap();
//! ```
//!
//! ```compile_fail
//! use saddle_bridge::VerifiedSaddleRequest;
//! fn assert_deserializable<T: serde::de::DeserializeOwned>() {}
//! assert_deserializable::<VerifiedSaddleRequest>();
//! ```

use std::collections::{BTreeSet, HashSet};

use chrono::{DateTime, Utc};
use fabric_contracts::{Budget, RequestOperation, TrustToken, VerifiedRequestContext};
use fabric_crypto::Verifier;
use fabric_revocation::MonotonicRevocationStore;
use fabric_token::{Operation, VerificationContext, lineage_key, verify_in_context};
use mai_compliance::AggregateDecision;
use serde::{Deserialize, Serialize};

/// Stable version of the frozen cross-plane contract.
pub const CONTRACT_VERSION: &str = "saddle.bridge/v1";

/// One exact desired-state mutation.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AdmissionVerb {
    Create,
    Update,
    Delete,
}

/// One exact AOG action class.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ActionKind {
    Model,
    Tool,
    Control,
}

/// Stage supplied to the AOG policy adapter.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PolicyStage {
    Admission,
    Placement,
    Runtime,
    Action,
}

/// Independent replay namespaces for ingress requests and downstream actions.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ReplayClass {
    Request,
    Action,
}

/// Durable replay adapter seam. Implementations atomically consume a nonce and
/// return `true` exactly once. Storage failures must return `Err` and fence the
/// operation; production callers replace the in-memory implementation.
pub trait ReplayStore: Send {
    fn consume(
        &mut self,
        class: ReplayClass,
        tenant_id: &str,
        lineage: &str,
        nonce: &str,
    ) -> Result<bool, String>;
}

/// Single-process replay store for tests and explicitly local deployments.
#[derive(Debug, Default)]
pub struct InMemoryReplayStore {
    consumed: HashSet<(ReplayClass, String, String, String)>,
}

impl ReplayStore for InMemoryReplayStore {
    fn consume(
        &mut self,
        class: ReplayClass,
        tenant_id: &str,
        lineage: &str,
        nonce: &str,
    ) -> Result<bool, String> {
        Ok(self.consumed.insert((
            class,
            tenant_id.to_owned(),
            lineage.to_owned(),
            nonce.to_owned(),
        )))
    }
}

/// Metadata-only policy input. Payloads never cross this contract.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PolicyInput<'a> {
    pub stage: PolicyStage,
    pub tenant_id: &'a str,
    pub request_digest: &'a str,
    pub destination: Option<&'a str>,
}

/// Adapter seam implemented by the deployed AOG policy engine. The bridge
/// consumes its existing deny-wins aggregate rather than recomposing policy.
pub trait AogPolicy: Send + Sync {
    fn evaluate(&self, input: &PolicyInput<'_>) -> AggregateDecision;
}

/// Authority requested by a grant. Every set is interpreted as an allowlist.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CapabilityScope {
    #[serde(default)]
    pub resource_prefixes: BTreeSet<String>,
    #[serde(default)]
    pub models: BTreeSet<String>,
    #[serde(default)]
    pub tools: BTreeSet<String>,
}

impl CapabilityScope {
    fn is_within(&self, parent: &Self) -> bool {
        resource_subset(&self.resource_prefixes, &parent.resource_prefixes)
            && subset(&self.models, &parent.models)
            && subset(&self.tools, &parent.tools)
    }

    fn allows_resource(&self, resource: &str) -> bool {
        self.resource_prefixes.is_empty()
            || self
                .resource_prefixes
                .iter()
                .any(|prefix| resource.starts_with(prefix))
    }
}

fn resource_subset(child: &BTreeSet<String>, parent: &BTreeSet<String>) -> bool {
    parent.is_empty()
        || child
            .iter()
            .all(|value| parent.iter().any(|prefix| value.starts_with(prefix)))
}

fn subset(child: &BTreeSet<String>, parent: &BTreeSet<String>) -> bool {
    parent.is_empty() || child.is_subset(parent)
}

/// Budget reservation carried by placement/runtime/action grants.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct GrantBudget {
    pub tokens: u64,
    pub usd_cents: u64,
    pub tool_calls: u32,
}

impl GrantBudget {
    fn from_token(value: Option<&Budget>) -> Self {
        value.map_or(Self::default(), |budget| Self {
            tokens: budget.token_cap.saturating_sub(budget.tokens_spent),
            usd_cents: budget.usd_cap_cents.saturating_sub(budget.usd_spent_cents),
            tool_calls: budget.tool_call_cap.saturating_sub(budget.tool_calls_spent),
        })
    }

    fn is_within(self, parent: Self) -> bool {
        self.tokens <= parent.tokens
            && self.usd_cents <= parent.usd_cents
            && self.tool_calls <= parent.tool_calls
    }
}

/// Metadata that downstream `wsf-ledger` code turns into a durable receipt.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReceiptIntentSpec {
    pub receipt_id: String,
    pub request_digest: String,
}

/// Verified entry to the grant chain. Cannot be built from wire JSON.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct VerifiedSaddleRequest {
    context: VerifiedRequestContext,
    token_id: String,
    lineage: String,
    revocation_sequence: u64,
    nonce: String,
    correlation_id: String,
    expires_at: String,
    scope: CapabilityScope,
    budget: GrantBudget,
    #[serde(skip_serializing)]
    verified_token: TrustToken,
}

impl VerifiedSaddleRequest {
    pub fn context(&self) -> &VerifiedRequestContext {
        &self.context
    }
    pub fn tenant_id(&self) -> &str {
        &self.context.principal().tenant_id
    }
    pub fn token_id(&self) -> &str {
        &self.token_id
    }
    pub fn lineage(&self) -> &str {
        &self.lineage
    }
    pub fn revocation_sequence(&self) -> u64 {
        self.revocation_sequence
    }
    pub fn nonce(&self) -> &str {
        &self.nonce
    }
    pub fn correlation_id(&self) -> &str {
        &self.correlation_id
    }
    pub fn expires_at(&self) -> &str {
        &self.expires_at
    }
    pub fn scope(&self) -> &CapabilityScope {
        &self.scope
    }
    pub fn budget(&self) -> GrantBudget {
        self.budget
    }
}

/// Wire-safe request to narrow verified authority into an admission grant.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AdmissionSpec {
    pub verb: AdmissionVerb,
    pub object_uid: String,
    pub object_name: String,
    pub tenant_id: String,
    pub mutation_digest: String,
    pub expires_at: String,
    pub scope: CapabilityScope,
    pub receipt: ReceiptIntentSpec,
}

/// Exact authority to admit one desired-state mutation.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct AdmissionGrant {
    contract_version: &'static str,
    verb: AdmissionVerb,
    object_uid: String,
    object_name: String,
    tenant_id: String,
    mutation_digest: String,
    expires_at: String,
    scope: CapabilityScope,
    lineage: String,
    revocation_sequence: u64,
    receipt: ReceiptIntentSpec,
}

impl AdmissionGrant {
    pub fn verb(&self) -> AdmissionVerb {
        self.verb
    }
    pub fn object_uid(&self) -> &str {
        &self.object_uid
    }
    pub fn object_name(&self) -> &str {
        &self.object_name
    }
    pub fn tenant_id(&self) -> &str {
        &self.tenant_id
    }
    pub fn mutation_digest(&self) -> &str {
        &self.mutation_digest
    }
    pub fn expires_at(&self) -> &str {
        &self.expires_at
    }
    pub fn scope(&self) -> &CapabilityScope {
        &self.scope
    }
    pub fn lineage(&self) -> &str {
        &self.lineage
    }
    pub fn revocation_sequence(&self) -> u64 {
        self.revocation_sequence
    }
    pub fn receipt(&self) -> &ReceiptIntentSpec {
        &self.receipt
    }
}

/// Wire-safe requested narrowing into a placement grant.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PlacementSpec {
    pub placement_uid: String,
    pub workload_uid: String,
    pub generation: u64,
    pub eligible_nodes: BTreeSet<String>,
    pub resource_reservation: BTreeSet<String>,
    pub trust_constraints: BTreeSet<String>,
    pub expires_at: String,
    pub receipt: ReceiptIntentSpec,
}

/// Exact authority to place one workload generation.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct PlacementGrant {
    contract_version: &'static str,
    tenant_id: String,
    placement_uid: String,
    workload_uid: String,
    generation: u64,
    eligible_nodes: BTreeSet<String>,
    resource_reservation: BTreeSet<String>,
    trust_constraints: BTreeSet<String>,
    expires_at: String,
    lineage: String,
    revocation_sequence: u64,
    receipt: ReceiptIntentSpec,
}

impl PlacementGrant {
    pub fn tenant_id(&self) -> &str {
        &self.tenant_id
    }
    pub fn placement_uid(&self) -> &str {
        &self.placement_uid
    }
    pub fn workload_uid(&self) -> &str {
        &self.workload_uid
    }
    pub fn generation(&self) -> u64 {
        self.generation
    }
    pub fn eligible_nodes(&self) -> &BTreeSet<String> {
        &self.eligible_nodes
    }
    pub fn resource_reservation(&self) -> &BTreeSet<String> {
        &self.resource_reservation
    }
    pub fn trust_constraints(&self) -> &BTreeSet<String> {
        &self.trust_constraints
    }
    pub fn expires_at(&self) -> &str {
        &self.expires_at
    }
    pub fn lineage(&self) -> &str {
        &self.lineage
    }
    pub fn revocation_sequence(&self) -> u64 {
        self.revocation_sequence
    }
    pub fn receipt(&self) -> &ReceiptIntentSpec {
        &self.receipt
    }
}

/// Wire-safe requested narrowing into a runtime grant.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RuntimeSpec {
    pub node_identity: String,
    pub workload_digest: String,
    pub runtime_class: String,
    pub aog_permissions: BTreeSet<String>,
    pub budget: GrantBudget,
    pub expires_at: String,
    pub receipt: ReceiptIntentSpec,
}

/// Exact authority for one node to launch one immutable workload.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct RuntimeGrant {
    contract_version: &'static str,
    tenant_id: String,
    placement_uid: String,
    node_identity: String,
    workload_digest: String,
    runtime_class: String,
    aog_permissions: BTreeSet<String>,
    budget: GrantBudget,
    expires_at: String,
    lineage: String,
    revocation_sequence: u64,
    receipt: ReceiptIntentSpec,
}

impl RuntimeGrant {
    pub fn tenant_id(&self) -> &str {
        &self.tenant_id
    }
    pub fn placement_uid(&self) -> &str {
        &self.placement_uid
    }
    pub fn node_identity(&self) -> &str {
        &self.node_identity
    }
    pub fn workload_digest(&self) -> &str {
        &self.workload_digest
    }
    pub fn runtime_class(&self) -> &str {
        &self.runtime_class
    }
    pub fn aog_permissions(&self) -> &BTreeSet<String> {
        &self.aog_permissions
    }
    pub fn budget(&self) -> GrantBudget {
        self.budget
    }
    pub fn expires_at(&self) -> &str {
        &self.expires_at
    }
    pub fn lineage(&self) -> &str {
        &self.lineage
    }
    pub fn revocation_sequence(&self) -> u64 {
        self.revocation_sequence
    }
    pub fn receipt(&self) -> &ReceiptIntentSpec {
        &self.receipt
    }
}

/// Wire-safe requested narrowing into a single-action grant.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ActionSpec {
    pub kind: ActionKind,
    pub action: String,
    pub arguments_digest: String,
    pub request_digest: String,
    pub destination: String,
    pub budget: GrantBudget,
    pub nonce: String,
    pub expires_at: String,
    pub receipt: ReceiptIntentSpec,
}

/// Exact authority for one immutable AOG action.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ActionGrant {
    contract_version: &'static str,
    tenant_id: String,
    kind: ActionKind,
    action: String,
    arguments_digest: String,
    request_digest: String,
    destination: String,
    budget: GrantBudget,
    nonce: String,
    expires_at: String,
    lineage: String,
    revocation_sequence: u64,
    receipt: ReceiptIntentSpec,
}

impl ActionGrant {
    pub fn tenant_id(&self) -> &str {
        &self.tenant_id
    }
    pub fn kind(&self) -> ActionKind {
        self.kind
    }
    pub fn action(&self) -> &str {
        &self.action
    }
    pub fn arguments_digest(&self) -> &str {
        &self.arguments_digest
    }
    pub fn request_digest(&self) -> &str {
        &self.request_digest
    }
    pub fn destination(&self) -> &str {
        &self.destination
    }
    pub fn budget(&self) -> GrantBudget {
        self.budget
    }
    pub fn nonce(&self) -> &str {
        &self.nonce
    }
    pub fn expires_at(&self) -> &str {
        &self.expires_at
    }
    pub fn lineage(&self) -> &str {
        &self.lineage
    }
    pub fn revocation_sequence(&self) -> u64 {
        self.revocation_sequence
    }
    pub fn receipt(&self) -> &ReceiptIntentSpec {
        &self.receipt
    }
}

/// Fail-closed cross-plane error contract.
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum BridgeError {
    #[error("wrong Saddle operation: expected {expected:?}, got {got:?}")]
    WrongOperation {
        expected: RequestOperation,
        got: RequestOperation,
    },
    #[error("WSF token verification failed: {0}")]
    Token(String),
    #[error("revocation state denied authority: {0}")]
    Revocation(String),
    #[error("tenant isolation violation")]
    TenantIsolation,
    #[error("token lineage does not match authenticated principal")]
    LineageMismatch,
    #[error("replayed nonce")]
    Replay,
    #[error("replay store unavailable: {0}")]
    ReplayUnavailable(String),
    #[error("empty or ambiguous authority field: {0}")]
    Ambiguous(&'static str),
    #[error("grant expiry widens parent authority")]
    ExpiryWidens,
    #[error("grant scope widens parent authority")]
    ScopeWidens,
    #[error("grant budget widens parent authority")]
    BudgetWidens,
    #[error("node is outside the placement grant")]
    NodeNotEligible,
    #[error("action is outside the runtime AOG permission set")]
    ActionNotPermitted,
    #[error("AOG policy denied the request")]
    PolicyDenied,
    #[error("AOG policy supplied no applied module; request fenced")]
    PolicyFenced,
}

/// Stateful issuer. Replay memory is held here; revocation freshness remains
/// owned by the caller's monotonic `fabric-revocation` store.
pub struct GrantIssuer<P, R = InMemoryReplayStore> {
    policy: P,
    replay: R,
}

impl<P: AogPolicy> GrantIssuer<P, InMemoryReplayStore> {
    pub fn new(policy: P) -> Self {
        Self {
            policy,
            replay: InMemoryReplayStore::default(),
        }
    }
}

impl<P: AogPolicy, R: ReplayStore> GrantIssuer<P, R> {
    pub fn with_replay_store(policy: P, replay: R) -> Self {
        Self { policy, replay }
    }

    #[allow(clippy::too_many_arguments)]
    pub fn verify_request(
        &mut self,
        context: VerifiedRequestContext,
        token: &TrustToken,
        nonce: impl Into<String>,
        now: DateTime<Utc>,
        verifier: &dyn Verifier,
        issuer_public_key: &[u8],
        current_bundle: &str,
        revocation: &MonotonicRevocationStore,
    ) -> Result<VerifiedSaddleRequest, BridgeError> {
        let got = context.operation();
        if got != RequestOperation::SaddleAdmission {
            return Err(BridgeError::WrongOperation {
                expected: RequestOperation::SaddleAdmission,
                got,
            });
        }
        if context.principal().tenant_id != token.tenant_id {
            return Err(BridgeError::TenantIsolation);
        }
        let lineage = lineage_key(token).to_owned();
        if context
            .principal()
            .token_lineage
            .as_deref()
            .is_some_and(|value| value != lineage)
        {
            return Err(BridgeError::LineageMismatch);
        }
        let sequence = revocation
            .ensure_current(now)
            .map_err(|error| BridgeError::Revocation(error.to_string()))?;
        revocation
            .authorize(token, now)
            .map_err(|error| BridgeError::Revocation(error.to_string()))?;
        let snapshot = revocation
            .current()
            .ok_or_else(|| BridgeError::Revocation("revocation state unavailable".into()))?;
        let verification =
            VerificationContext::new(verifier, issuer_public_key, now, Operation::Saddle)
                .expect_tenant(&context.principal().tenant_id)
                .require_current_bundle(current_bundle)
                .with_revocation(snapshot);
        verify_in_context(token, &verification)
            .map_err(|error| BridgeError::Token(error.to_string()))?;
        let nonce = nonce.into();
        require_nonempty(&nonce, "nonce")?;
        let consumed = self
            .replay
            .consume(ReplayClass::Request, &token.tenant_id, &lineage, &nonce)
            .map_err(BridgeError::ReplayUnavailable)?;
        if !consumed {
            return Err(BridgeError::Replay);
        }
        parse_time(&token.expires_at, "token expires_at")?;
        let scope = scope_from_token(token);
        Ok(VerifiedSaddleRequest {
            correlation_id: context.principal().correlation_id.clone(),
            context,
            token_id: token.token_id.clone(),
            lineage,
            revocation_sequence: sequence,
            nonce,
            expires_at: token.expires_at.clone(),
            scope,
            budget: GrantBudget::from_token(token.budget.as_ref()),
            verified_token: token.clone(),
        })
    }

    pub fn issue_admission(
        &self,
        request: &VerifiedSaddleRequest,
        spec: AdmissionSpec,
        now: DateTime<Utc>,
        revocation: &MonotonicRevocationStore,
    ) -> Result<AdmissionGrant, BridgeError> {
        ensure_current_authority(request, now, revocation)?;
        require_nonempty(&spec.object_uid, "object_uid")?;
        require_nonempty(&spec.object_name, "object_name")?;
        require_nonempty(&spec.mutation_digest, "mutation_digest")?;
        validate_receipt(&spec.receipt)?;
        if spec.tenant_id != request.tenant_id() {
            return Err(BridgeError::TenantIsolation);
        }
        if spec.object_name != request.context.resource().name() {
            return Err(BridgeError::TenantIsolation);
        }
        let resource = format!(
            "{}s/{}",
            request.context.resource().kind().to_ascii_lowercase(),
            request.context.resource().name()
        );
        if !request.scope.allows_resource(&resource) {
            return Err(BridgeError::ScopeWidens);
        }
        ensure_expiry(&spec.expires_at, &request.expires_at)?;
        if !spec.scope.is_within(&request.scope) {
            return Err(BridgeError::ScopeWidens);
        }
        self.require_policy(
            PolicyStage::Admission,
            &spec.tenant_id,
            &spec.mutation_digest,
            None,
        )?;
        Ok(AdmissionGrant {
            contract_version: CONTRACT_VERSION,
            verb: spec.verb,
            object_uid: spec.object_uid,
            object_name: spec.object_name,
            tenant_id: spec.tenant_id,
            mutation_digest: spec.mutation_digest,
            expires_at: spec.expires_at,
            scope: spec.scope,
            lineage: request.lineage.clone(),
            revocation_sequence: request.revocation_sequence,
            receipt: spec.receipt,
        })
    }

    pub fn issue_placement(
        &self,
        request: &VerifiedSaddleRequest,
        admission: &AdmissionGrant,
        spec: PlacementSpec,
        now: DateTime<Utc>,
        revocation: &MonotonicRevocationStore,
    ) -> Result<PlacementGrant, BridgeError> {
        ensure_current_authority(request, now, revocation)?;
        if admission.tenant_id != request.tenant_id() {
            return Err(BridgeError::TenantIsolation);
        }
        if admission.lineage != request.lineage {
            return Err(BridgeError::LineageMismatch);
        }
        require_nonempty(&spec.workload_uid, "workload_uid")?;
        require_nonempty(&spec.placement_uid, "placement_uid")?;
        validate_set(&spec.eligible_nodes, "eligible_nodes")?;
        validate_receipt(&spec.receipt)?;
        ensure_expiry(&spec.expires_at, &admission.expires_at)?;
        self.require_policy(
            PolicyStage::Placement,
            &admission.tenant_id,
            &spec.receipt.request_digest,
            None,
        )?;
        Ok(PlacementGrant {
            contract_version: CONTRACT_VERSION,
            tenant_id: admission.tenant_id.clone(),
            placement_uid: spec.placement_uid,
            workload_uid: spec.workload_uid,
            generation: spec.generation,
            eligible_nodes: spec.eligible_nodes,
            resource_reservation: spec.resource_reservation,
            trust_constraints: spec.trust_constraints,
            expires_at: spec.expires_at,
            lineage: admission.lineage.clone(),
            revocation_sequence: admission.revocation_sequence,
            receipt: spec.receipt,
        })
    }

    pub fn issue_runtime(
        &self,
        request: &VerifiedSaddleRequest,
        placement: &PlacementGrant,
        spec: RuntimeSpec,
        now: DateTime<Utc>,
        revocation: &MonotonicRevocationStore,
    ) -> Result<RuntimeGrant, BridgeError> {
        ensure_current_authority(request, now, revocation)?;
        require_nonempty(&spec.node_identity, "node_identity")?;
        require_nonempty(&spec.workload_digest, "workload_digest")?;
        require_nonempty(&spec.runtime_class, "runtime_class")?;
        validate_receipt(&spec.receipt)?;
        if placement.tenant_id != request.tenant_id() {
            return Err(BridgeError::TenantIsolation);
        }
        if placement.lineage != request.lineage {
            return Err(BridgeError::LineageMismatch);
        }
        if !placement.eligible_nodes.contains(&spec.node_identity) {
            return Err(BridgeError::NodeNotEligible);
        }
        ensure_expiry(&spec.expires_at, &placement.expires_at)?;
        ensure_expiry(&spec.expires_at, &request.expires_at)?;
        if !spec.budget.is_within(request.budget) {
            return Err(BridgeError::BudgetWidens);
        }
        self.require_policy(
            PolicyStage::Runtime,
            request.tenant_id(),
            &spec.workload_digest,
            Some(&spec.node_identity),
        )?;
        Ok(RuntimeGrant {
            contract_version: CONTRACT_VERSION,
            tenant_id: request.tenant_id().to_owned(),
            placement_uid: placement.placement_uid.clone(),
            node_identity: spec.node_identity,
            workload_digest: spec.workload_digest,
            runtime_class: spec.runtime_class,
            aog_permissions: spec.aog_permissions,
            budget: spec.budget,
            expires_at: spec.expires_at,
            lineage: request.lineage.clone(),
            revocation_sequence: request.revocation_sequence,
            receipt: spec.receipt,
        })
    }

    pub fn issue_action(
        &mut self,
        request: &VerifiedSaddleRequest,
        runtime: &RuntimeGrant,
        spec: ActionSpec,
        now: DateTime<Utc>,
        revocation: &MonotonicRevocationStore,
    ) -> Result<ActionGrant, BridgeError> {
        ensure_current_authority(request, now, revocation)?;
        if runtime.tenant_id != request.tenant_id() {
            return Err(BridgeError::TenantIsolation);
        }
        if runtime.lineage != request.lineage {
            return Err(BridgeError::LineageMismatch);
        }
        require_nonempty(&spec.action, "action")?;
        require_nonempty(&spec.arguments_digest, "arguments_digest")?;
        require_nonempty(&spec.request_digest, "request_digest")?;
        require_nonempty(&spec.destination, "destination")?;
        require_nonempty(&spec.nonce, "action nonce")?;
        validate_receipt(&spec.receipt)?;
        ensure_expiry(&spec.expires_at, &runtime.expires_at)?;
        if !spec.budget.is_within(runtime.budget) {
            return Err(BridgeError::BudgetWidens);
        }
        if !runtime.aog_permissions.is_empty() && !runtime.aog_permissions.contains(&spec.action) {
            return Err(BridgeError::ActionNotPermitted);
        }
        self.require_policy(
            PolicyStage::Action,
            &runtime.tenant_id,
            &spec.request_digest,
            Some(&spec.destination),
        )?;
        let consumed = self
            .replay
            .consume(
                ReplayClass::Action,
                &runtime.tenant_id,
                &runtime.lineage,
                &spec.nonce,
            )
            .map_err(BridgeError::ReplayUnavailable)?;
        if !consumed {
            return Err(BridgeError::Replay);
        }
        Ok(ActionGrant {
            contract_version: CONTRACT_VERSION,
            tenant_id: runtime.tenant_id.clone(),
            kind: spec.kind,
            action: spec.action,
            arguments_digest: spec.arguments_digest,
            request_digest: spec.request_digest,
            destination: spec.destination,
            budget: spec.budget,
            nonce: spec.nonce,
            expires_at: spec.expires_at,
            lineage: runtime.lineage.clone(),
            revocation_sequence: runtime.revocation_sequence,
            receipt: spec.receipt,
        })
    }

    fn require_policy(
        &self,
        stage: PolicyStage,
        tenant: &str,
        digest: &str,
        destination: Option<&str>,
    ) -> Result<(), BridgeError> {
        let decision = self.policy.evaluate(&PolicyInput {
            stage,
            tenant_id: tenant,
            request_digest: digest,
            destination,
        });
        if decision.modules_applied.is_empty() {
            return Err(BridgeError::PolicyFenced);
        }
        if !decision.allowed {
            return Err(BridgeError::PolicyDenied);
        }
        Ok(())
    }
}

fn parse_time(value: &str, field: &'static str) -> Result<DateTime<Utc>, BridgeError> {
    DateTime::parse_from_rfc3339(value)
        .map(|time| time.with_timezone(&Utc))
        .map_err(|_| BridgeError::Ambiguous(field))
}

fn ensure_expiry(child: &str, parent: &str) -> Result<(), BridgeError> {
    let child = parse_time(child, "grant expires_at")?;
    let parent = parse_time(parent, "parent expires_at")?;
    if child > parent {
        Err(BridgeError::ExpiryWidens)
    } else {
        Ok(())
    }
}

fn ensure_current_authority(
    request: &VerifiedSaddleRequest,
    now: DateTime<Utc>,
    revocation: &MonotonicRevocationStore,
) -> Result<(), BridgeError> {
    let sequence = revocation
        .ensure_current(now)
        .map_err(|error| BridgeError::Revocation(error.to_string()))?;
    if sequence < request.revocation_sequence {
        return Err(BridgeError::Revocation(format!(
            "stale snapshot sequence {sequence} < verified {}",
            request.revocation_sequence
        )));
    }
    revocation
        .authorize(&request.verified_token, now)
        .map_err(|error| BridgeError::Revocation(error.to_string()))
}

fn require_nonempty(value: &str, field: &'static str) -> Result<(), BridgeError> {
    if value.trim().is_empty() {
        Err(BridgeError::Ambiguous(field))
    } else {
        Ok(())
    }
}

fn validate_set(values: &BTreeSet<String>, field: &'static str) -> Result<(), BridgeError> {
    if values.is_empty() || values.iter().any(|value| value.trim().is_empty()) {
        Err(BridgeError::Ambiguous(field))
    } else {
        Ok(())
    }
}

fn validate_receipt(receipt: &ReceiptIntentSpec) -> Result<(), BridgeError> {
    require_nonempty(&receipt.receipt_id, "receipt_id")?;
    require_nonempty(&receipt.request_digest, "receipt request_digest")
}

fn scope_from_token(token: &TrustToken) -> CapabilityScope {
    let mut scope = CapabilityScope {
        models: token.allowed_models.iter().cloned().collect(),
        ..CapabilityScope::default()
    };
    for caveat in &token.attenuation.caveats {
        match caveat.caveat_type {
            fabric_contracts::CaveatType::ResourcePrefix => {
                scope.resource_prefixes.insert(caveat.value.clone());
            }
            fabric_contracts::CaveatType::ToolAllowlist => {
                scope.tools.extend(
                    caveat
                        .value
                        .split(',')
                        .map(str::trim)
                        .filter(|value| !value.is_empty())
                        .map(str::to_owned),
                );
            }
            fabric_contracts::CaveatType::ModelAllowlist => {
                scope.models.extend(
                    caveat
                        .value
                        .split(',')
                        .map(str::trim)
                        .filter(|value| !value.is_empty())
                        .map(str::to_owned),
                );
            }
            _ => {}
        }
    }
    scope
}
