//! Local trust cache (BF-4).
//!
//! When the Lamprey Trust Bridge is unreachable, the appliance falls
//! back to the most recent signed policy bundle and revocation snapshot
//! held locally. This module is the in-memory state model for that
//! cache; the on-disk format and signature verification land with BF-3.
//!
//! # Connectivity derivation
//!
//! [`LocalTrustCache::evaluate`] returns the [`ConnectivityState`] the
//! policy runtime should use, given:
//!
//!   * the cache's last successful refresh timestamp,
//!   * the operator-configured warn and hard-expiry thresholds, and
//!   * the air-gap policy carried into the call.
//!
//! The hardware air-gap switch always wins — if the caller passes
//! [`ConnectivityState::AirGapped`], that's returned unchanged. The
//! freshness ladder is only consulted when the switch permits any
//! network traffic.
//!
//! ```text
//! AirGapped       (hardware switch wins)
//!     │
//!     ├─ now - last_refresh < warn    → Connected   (or Degraded if no live link)
//!     ├─ now - last_refresh < expiry  → StaleNotExpired
//!     └─ now - last_refresh >= expiry → Expired
//! ```
//!
//! # Emergency access
//!
//! [`LocalTrustCache::is_emergency_only`] returns true in
//! [`ConnectivityState::Expired`]. Callers that gate maintenance
//! endpoints on this method should require explicit admin
//! authentication; the emergency mode is intentionally narrow.
//!
//! # Offline audit queue
//!
//! Audit events generated while the cache is degraded, stale, or
//! air-gapped accumulate in an in-memory queue surfaced by
//! [`LocalTrustCache::offline_audit_backlog`]. The queue is flushed by
//! Session 42's audit subsystem when connectivity returns; the cache
//! itself does not transmit anything.

use std::collections::BTreeMap;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use mai_core::airgap::ConnectivityState;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Result of a revocation lookup at the time the cache was last
/// refreshed. Pessimistic — `Unknown` means we have not seen a fresh
/// snapshot and the policy runtime should treat the claim as if it
/// might be revoked.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SnapshotStatus {
    /// Snapshot present and the subject's claim was valid.
    Valid,
    /// Snapshot present and the subject's claim was revoked.
    Revoked,
    /// No snapshot recorded for this subject.
    Unknown,
}

/// A single revocation snapshot for one claim id.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RevocationSnapshot {
    /// Claim id this snapshot refers to.
    pub claim_id: String,
    /// Status at the snapshot time.
    pub status: SnapshotStatus,
    /// Unix epoch seconds when the snapshot was taken.
    pub recorded_at_secs: u64,
}

/// Configurable freshness thresholds for the trust cache.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CacheThresholds {
    /// Age past which the cache is considered degraded (warn).
    /// Cloud-route decisions may still proceed but should be logged.
    pub warn_after: Duration,
    /// Age past which the cache is hard-expired. Only emergency local
    /// operations should proceed.
    pub expire_after: Duration,
}

impl Default for CacheThresholds {
    /// Sensible defaults: warn after 1 hour, expire after 24 hours.
    /// Operators override per deployment profile (see
    /// `docs/LOCAL-TRUST-CACHE.md` §3).
    fn default() -> Self {
        Self {
            warn_after: Duration::from_secs(60 * 60),
            expire_after: Duration::from_secs(60 * 60 * 24),
        }
    }
}

/// Errors at cache-construction or update time.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum TrustCacheError {
    /// Caller supplied a refresh timestamp in the future relative to the
    /// cache's own clock; refused to prevent clock-skew exploits.
    #[error("refresh timestamp {0} is in the future")]
    FutureRefresh(u64),
    /// Caller supplied an expire-after smaller than warn-after, which
    /// would make the warn band empty.
    #[error("expire_after ({expire:?}) must be >= warn_after ({warn:?})")]
    ThresholdsInverted { warn: Duration, expire: Duration },
}

/// In-memory local trust cache.
///
/// Thread-unsafe by design — call sites that need concurrent access
/// wrap an `Arc<RwLock<LocalTrustCache>>`. The state model is small
/// enough that a single writer + many readers is the natural pattern.
#[derive(Debug, Clone)]
pub struct LocalTrustCache {
    thresholds: CacheThresholds,
    /// Unix epoch seconds of the most recent successful refresh from the
    /// upstream Trust Bridge. `None` until the first refresh lands.
    last_refresh_secs: Option<u64>,
    /// Currently held signed trust bundle version, if any.
    bundle_version: Option<String>,
    /// Per-claim revocation snapshots taken at the last refresh.
    revocations: BTreeMap<String, RevocationSnapshot>,
    /// Audit events that accumulated while degraded / stale / air-gapped.
    /// Cleared by [`Self::drain_offline_backlog`] when connectivity
    /// returns.
    offline_audit_backlog: Vec<String>,
}

impl LocalTrustCache {
    /// Construct an empty cache with the given freshness thresholds.
    pub fn new(thresholds: CacheThresholds) -> Result<Self, TrustCacheError> {
        if thresholds.expire_after < thresholds.warn_after {
            return Err(TrustCacheError::ThresholdsInverted {
                warn: thresholds.warn_after,
                expire: thresholds.expire_after,
            });
        }
        Ok(Self {
            thresholds,
            last_refresh_secs: None,
            bundle_version: None,
            revocations: BTreeMap::new(),
            offline_audit_backlog: Vec::new(),
        })
    }

    /// Record a successful refresh from the upstream Trust Bridge.
    ///
    /// `refresh_secs` must be at-or-before `now_secs`. Snapshots replace
    /// any previously-held entries for the same `claim_id`.
    pub fn record_refresh(
        &mut self,
        bundle_version: impl Into<String>,
        snapshots: Vec<RevocationSnapshot>,
        refresh_secs: u64,
        now_secs: u64,
    ) -> Result<(), TrustCacheError> {
        if refresh_secs > now_secs {
            return Err(TrustCacheError::FutureRefresh(refresh_secs));
        }
        self.bundle_version = Some(bundle_version.into());
        self.last_refresh_secs = Some(refresh_secs);
        for snap in snapshots {
            self.revocations.insert(snap.claim_id.clone(), snap);
        }
        Ok(())
    }

    /// Look up the revocation status for a claim id. Returns
    /// [`SnapshotStatus::Unknown`] when no snapshot exists.
    #[must_use]
    pub fn revocation_status(&self, claim_id: &str) -> SnapshotStatus {
        self.revocations
            .get(claim_id)
            .map_or(SnapshotStatus::Unknown, |s| s.status)
    }

    /// Currently-held bundle version, if any.
    #[must_use]
    pub fn bundle_version(&self) -> Option<&str> {
        self.bundle_version.as_deref()
    }

    /// Most recent refresh time as Unix epoch seconds.
    #[must_use]
    pub fn last_refresh_secs(&self) -> Option<u64> {
        self.last_refresh_secs
    }

    /// Age of the most recent refresh, in seconds, relative to `now_secs`.
    /// Returns `None` if the cache has never been refreshed.
    #[must_use]
    pub fn age_secs(&self, now_secs: u64) -> Option<u64> {
        self.last_refresh_secs.map(|r| now_secs.saturating_sub(r))
    }

    /// Compute the connectivity state given `switch_state` (the hardware
    /// air-gap policy) and the current wall-clock time.
    ///
    /// `switch_state` wins when it is `AirGapped`. Otherwise the cache
    /// age decides between `Connected`, `Degraded`, `StaleNotExpired`,
    /// and `Expired`. A `live_link` flag distinguishes `Connected`
    /// (network reachable, cache fresh) from `Degraded` (cache fresh
    /// but live validation unavailable).
    #[must_use]
    pub fn evaluate(
        &self,
        switch_state: ConnectivityState,
        live_link: bool,
        now_secs: u64,
    ) -> ConnectivityState {
        if switch_state.is_air_gapped() {
            return ConnectivityState::AirGapped;
        }
        let Some(age) = self.age_secs(now_secs) else {
            // Never refreshed → treat as expired.
            return ConnectivityState::Expired;
        };
        let age = Duration::from_secs(age);
        if age >= self.thresholds.expire_after {
            return ConnectivityState::Expired;
        }
        if age >= self.thresholds.warn_after {
            return ConnectivityState::StaleNotExpired;
        }
        if live_link {
            ConnectivityState::Connected
        } else {
            ConnectivityState::Degraded
        }
    }

    /// True when the cache is in emergency-only mode (Expired). Callers
    /// that gate maintenance endpoints on this should additionally
    /// require explicit admin authentication.
    #[must_use]
    pub fn is_emergency_only(
        &self,
        switch_state: ConnectivityState,
        live_link: bool,
        now_secs: u64,
    ) -> bool {
        matches!(
            self.evaluate(switch_state, live_link, now_secs),
            ConnectivityState::Expired
        )
    }

    /// Push an audit event onto the offline backlog. The cache stores
    /// these as opaque strings; Session 42 defines the JSON shape.
    pub fn enqueue_offline_audit(&mut self, event: impl Into<String>) {
        self.offline_audit_backlog.push(event.into());
    }

    /// Number of audit events waiting to be flushed.
    #[must_use]
    pub fn offline_audit_backlog(&self) -> usize {
        self.offline_audit_backlog.len()
    }

    /// Drain the offline audit backlog. Returns every queued event in
    /// FIFO order. The caller (Session 42 audit) is responsible for
    /// re-queueing on flush failure.
    pub fn drain_offline_backlog(&mut self) -> Vec<String> {
        std::mem::take(&mut self.offline_audit_backlog)
    }

    /// Wall-clock helper for callers that don't have a clock injected.
    /// Returns Unix epoch seconds.
    #[must_use]
    pub fn now_secs() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_or(0, |d| d.as_secs())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn thresholds(warn: u64, expire: u64) -> CacheThresholds {
        CacheThresholds {
            warn_after: Duration::from_secs(warn),
            expire_after: Duration::from_secs(expire),
        }
    }

    fn snap(claim: &str, status: SnapshotStatus, at: u64) -> RevocationSnapshot {
        RevocationSnapshot {
            claim_id: claim.to_string(),
            status,
            recorded_at_secs: at,
        }
    }

    #[test]
    fn thresholds_inverted_rejected() {
        let err = LocalTrustCache::new(thresholds(120, 60)).unwrap_err();
        assert!(matches!(err, TrustCacheError::ThresholdsInverted { .. }));
    }

    #[test]
    fn future_refresh_rejected() {
        let mut cache = LocalTrustCache::new(thresholds(60, 120)).unwrap();
        let err = cache.record_refresh("v1", vec![], 1000, 500).unwrap_err();
        assert_eq!(err, TrustCacheError::FutureRefresh(1000));
    }

    #[test]
    fn unknown_revocation_for_unseen_claim() {
        let cache = LocalTrustCache::new(thresholds(60, 120)).unwrap();
        assert_eq!(cache.revocation_status("c1"), SnapshotStatus::Unknown);
    }

    #[test]
    fn revocation_recorded_after_refresh() {
        let mut cache = LocalTrustCache::new(thresholds(60, 120)).unwrap();
        cache
            .record_refresh(
                "bundle-2026.05.22",
                vec![
                    snap("c1", SnapshotStatus::Valid, 1000),
                    snap("c2", SnapshotStatus::Revoked, 1000),
                ],
                1000,
                1000,
            )
            .unwrap();
        assert_eq!(cache.revocation_status("c1"), SnapshotStatus::Valid);
        assert_eq!(cache.revocation_status("c2"), SnapshotStatus::Revoked);
        assert_eq!(cache.revocation_status("c3"), SnapshotStatus::Unknown);
        assert_eq!(cache.bundle_version(), Some("bundle-2026.05.22"));
    }

    #[test]
    fn evaluate_never_refreshed_is_expired() {
        let cache = LocalTrustCache::new(thresholds(60, 120)).unwrap();
        assert_eq!(
            cache.evaluate(ConnectivityState::Connected, true, 1000),
            ConnectivityState::Expired
        );
    }

    #[test]
    fn evaluate_connected_when_fresh_and_live() {
        let mut cache = LocalTrustCache::new(thresholds(60, 120)).unwrap();
        cache.record_refresh("v1", vec![], 1000, 1000).unwrap();
        assert_eq!(
            cache.evaluate(ConnectivityState::Connected, true, 1010),
            ConnectivityState::Connected
        );
    }

    #[test]
    fn evaluate_degraded_when_fresh_but_no_live_link() {
        let mut cache = LocalTrustCache::new(thresholds(60, 120)).unwrap();
        cache.record_refresh("v1", vec![], 1000, 1000).unwrap();
        assert_eq!(
            cache.evaluate(ConnectivityState::Connected, false, 1010),
            ConnectivityState::Degraded
        );
    }

    #[test]
    fn evaluate_stale_in_warn_band() {
        let mut cache = LocalTrustCache::new(thresholds(60, 120)).unwrap();
        cache.record_refresh("v1", vec![], 1000, 1000).unwrap();
        // Age 90s > warn (60s) but < expire (120s).
        assert_eq!(
            cache.evaluate(ConnectivityState::Connected, true, 1090),
            ConnectivityState::StaleNotExpired
        );
    }

    #[test]
    fn evaluate_expired_past_hard_threshold() {
        let mut cache = LocalTrustCache::new(thresholds(60, 120)).unwrap();
        cache.record_refresh("v1", vec![], 1000, 1000).unwrap();
        // Age 150s >= expire (120s).
        assert_eq!(
            cache.evaluate(ConnectivityState::Connected, true, 1150),
            ConnectivityState::Expired
        );
        assert!(cache.is_emergency_only(ConnectivityState::Connected, true, 1150));
    }

    #[test]
    fn evaluate_air_gapped_overrides_everything() {
        let mut cache = LocalTrustCache::new(thresholds(60, 120)).unwrap();
        cache.record_refresh("v1", vec![], 1000, 1000).unwrap();
        // Even with a perfectly fresh cache, AirGapped wins.
        assert_eq!(
            cache.evaluate(ConnectivityState::AirGapped, true, 1005),
            ConnectivityState::AirGapped
        );
    }

    #[test]
    fn offline_audit_backlog_drains_in_order() {
        let mut cache = LocalTrustCache::new(thresholds(60, 120)).unwrap();
        cache.enqueue_offline_audit("event-1");
        cache.enqueue_offline_audit("event-2");
        assert_eq!(cache.offline_audit_backlog(), 2);
        let drained = cache.drain_offline_backlog();
        assert_eq!(drained, vec!["event-1".to_string(), "event-2".to_string()]);
        assert_eq!(cache.offline_audit_backlog(), 0);
    }
}
