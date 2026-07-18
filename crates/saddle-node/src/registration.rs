//! Node registration. A node joins with a `fabric-identity` leaf signed by
//! the trust anchor, plus its declared attestation profile + capacity (the
//! [`Node`] spec). The control plane admits it only if the leaf verifies against
//! the roster's anchor key **and** names this node; a mis-signed, expired-kind,
//! or wrong-named identity is refused (fail-closed, I-4). A node that cannot
//! prove its identity does not join.

use chrono::{Duration, Utc};

use fabric_contracts::{Classification, Identity, IdentityKind, Signature};
use fabric_crypto::{Signer, Verifier};

use saddle_estate::{
    ATTESTATION_SIGNATURE_ANNOTATION, ATTESTATION_VERIFIED_AT_ANNOTATION,
    ATTESTATION_VERIFIED_UNTIL_ANNOTATION, AttestationPlatform, Node,
};

/// Mint a node identity leaf for `node_name` in `tenant`, signed by `issuer`
/// (the trust anchor). The leaf binds the node's name and PKI fingerprint; only
/// the anchor can produce one that verifies, so a node cannot self-assert its
/// membership. `ttl` bounds validity (zero standing privilege, I-1).
pub fn mint_node_identity(
    node_name: &str,
    tenant: &str,
    issuer: &dyn Signer,
    ttl: Duration,
) -> Result<Identity, RegistrationError> {
    let now = Utc::now();
    let identity = Identity {
        identity_id: format!("node:{node_name}"),
        kind: IdentityKind::Workload,
        tenant_id: tenant.to_owned(),
        subject_id: node_name.to_owned(),
        subject_hash: format!("node:{node_name}"),
        service_identity: Some(format!("saddle-node/{node_name}")),
        spiffe_id: format!("spiffe://saddle/node/{node_name}"),
        pki_cert_fingerprint: issuer.key_id().to_owned(),
        parent_id: None,
        issued_at: now.to_rfc3339(),
        expires_at: (now + ttl).to_rfc3339(),
        signature: Signature {
            alg: String::new(),
            key_id: String::new(),
            value: String::new(),
        },
    };
    fabric_identity::mint(identity, issuer).map_err(|e| RegistrationError::Mint(e.to_string()))
}

/// The payload a node presents to join: its declared [`Node`] (attestation
/// profile + capacity) and the identity leaf authorizing the registration.
#[derive(Debug, Clone)]
pub struct NodeRegistration {
    /// The node the agent is registering.
    pub node: Node,
    /// The anchor-signed identity leaf proving membership.
    pub identity: Identity,
    /// Anchor-signed statement binding the node's declared trust posture.
    pub attestation: NodeAttestation,
}

/// WSF trust-authority statement over one node's scheduling attestation.
#[derive(Debug, Clone)]
pub struct NodeAttestation {
    pub node: String,
    pub ring: u8,
    pub floor: Classification,
    pub platform: AttestationPlatform,
    pub measurement: Option<String>,
    pub issued_at: String,
    pub expires_at: String,
    signature: Vec<u8>,
}

impl NodeAttestation {
    fn canonical(&self) -> Vec<u8> {
        let platform = match self.platform {
            AttestationPlatform::None => "none",
            AttestationPlatform::Tpm => "tpm",
            AttestationPlatform::NitroEnclave => "nitro-enclave",
            AttestationPlatform::SevSnp => "sev-snp",
        };
        format!(
            "saddle.node-attestation/v1\0{}\0{}\0{:?}\0{}\0{}\0{}\0{}",
            self.node,
            self.ring,
            self.floor,
            platform,
            self.measurement.as_deref().unwrap_or_default(),
            self.issued_at,
            self.expires_at,
        )
        .into_bytes()
    }

    /// Attach this signed statement to the exact node it covers.
    pub fn stamp(&self, node: &mut Node) -> Result<(), RegistrationError> {
        if self.node != node.metadata.name
            || self.ring != node.spec.ring
            || self.floor != node.spec.attestation_floor
            || self.platform != node.spec.attestation.platform
            || self.measurement != node.spec.attestation.pcr
        {
            return Err(RegistrationError::AttestationMismatch);
        }
        node.metadata.annotations.insert(
            ATTESTATION_VERIFIED_AT_ANNOTATION.to_owned(),
            self.issued_at.clone(),
        );
        node.metadata.annotations.insert(
            ATTESTATION_VERIFIED_UNTIL_ANNOTATION.to_owned(),
            self.expires_at.clone(),
        );
        node.metadata.annotations.insert(
            ATTESTATION_SIGNATURE_ANNOTATION.to_owned(),
            hex::encode(&self.signature),
        );
        Ok(())
    }
}

/// Verify the stamped WSF attestation over the node's exact current profile.
#[must_use]
pub fn verify_stamped_attestation(
    node: &Node,
    verifier: &dyn Verifier,
    anchor_public_key: &[u8],
    now: chrono::DateTime<Utc>,
) -> bool {
    let Some(issued_at) = node
        .metadata
        .annotations
        .get(ATTESTATION_VERIFIED_AT_ANNOTATION)
    else {
        return false;
    };
    let Some(expires_at) = node
        .metadata
        .annotations
        .get(ATTESTATION_VERIFIED_UNTIL_ANNOTATION)
    else {
        return false;
    };
    let Some(signature) = node
        .metadata
        .annotations
        .get(ATTESTATION_SIGNATURE_ANNOTATION)
        .and_then(|value| hex::decode(value).ok())
    else {
        return false;
    };
    let Ok(expiry) = chrono::DateTime::parse_from_rfc3339(expires_at) else {
        return false;
    };
    if expiry.with_timezone(&Utc) <= now {
        return false;
    }
    let evidence = NodeAttestation {
        node: node.metadata.name.clone(),
        ring: node.spec.ring,
        floor: node.spec.attestation_floor,
        platform: node.spec.attestation.platform,
        measurement: node.spec.attestation.pcr.clone(),
        issued_at: issued_at.clone(),
        expires_at: expires_at.clone(),
        signature,
    };
    verifier
        .verify(
            &evidence.canonical(),
            &evidence.signature,
            anchor_public_key,
        )
        .unwrap_or(false)
}

/// Mint a bounded WSF attestation statement over the exact node trust profile.
pub fn mint_node_attestation(
    node: &Node,
    issuer: &dyn Signer,
    ttl: Duration,
) -> Result<NodeAttestation, RegistrationError> {
    let now = Utc::now();
    let mut evidence = NodeAttestation {
        node: node.metadata.name.clone(),
        ring: node.spec.ring,
        floor: node.spec.attestation_floor,
        platform: node.spec.attestation.platform,
        measurement: node.spec.attestation.pcr.clone(),
        issued_at: now.to_rfc3339(),
        expires_at: (now + ttl).to_rfc3339(),
        signature: Vec::new(),
    };
    evidence.signature = issuer
        .sign(&evidence.canonical())
        .map_err(|error| RegistrationError::Mint(error.to_string()))?;
    Ok(evidence)
}

/// Admits node registrations, verifying each identity against the trust roster's
/// anchor public key.
#[derive(Debug, Clone)]
pub struct Registrar {
    anchor_public_key: Vec<u8>,
}

impl Registrar {
    /// Build a registrar that trusts `anchor_public_key` (the roster key).
    #[must_use]
    pub fn new(anchor_public_key: Vec<u8>) -> Self {
        Self { anchor_public_key }
    }

    /// Verify a registration and return the [`Node`] to admit. Fails closed: a
    /// non-workload identity, one that does not name this node, or one that does
    /// not verify against the anchor is refused — the estate never records a node
    /// whose identity was not proven.
    pub fn admit(
        &self,
        registration: &NodeRegistration,
        verifier: &dyn Verifier,
    ) -> Result<Node, RegistrationError> {
        let identity = &registration.identity;
        if identity.kind != IdentityKind::Workload {
            return Err(RegistrationError::WrongKind);
        }
        if identity.subject_id != registration.node.metadata.name {
            return Err(RegistrationError::SubjectMismatch {
                identity: identity.subject_id.clone(),
                node: registration.node.metadata.name.clone(),
            });
        }
        fabric_identity::verify(identity, verifier, &self.anchor_public_key)
            .map_err(|e| RegistrationError::Unverified(e.to_string()))?;
        let evidence = &registration.attestation;
        let node = &registration.node;
        if evidence.node != node.metadata.name
            || evidence.ring != node.spec.ring
            || evidence.floor != node.spec.attestation_floor
            || evidence.platform != node.spec.attestation.platform
            || evidence.measurement != node.spec.attestation.pcr
        {
            return Err(RegistrationError::AttestationMismatch);
        }
        let expires_at = chrono::DateTime::parse_from_rfc3339(&evidence.expires_at)
            .map_err(|_| RegistrationError::AttestationExpired)?
            .with_timezone(&Utc);
        if expires_at <= Utc::now() {
            return Err(RegistrationError::AttestationExpired);
        }
        let verified = verifier
            .verify(
                &evidence.canonical(),
                &evidence.signature,
                &self.anchor_public_key,
            )
            .map_err(|error| RegistrationError::Unverified(error.to_string()))?;
        if !verified {
            return Err(RegistrationError::Unverified(
                "node attestation signature invalid".to_owned(),
            ));
        }
        let mut admitted = node.clone();
        evidence.stamp(&mut admitted)?;
        Ok(admitted)
    }
}

/// Why a node registration was refused.
#[derive(Debug, thiserror::Error)]
pub enum RegistrationError {
    /// The identity leaf could not be signed.
    #[error("identity mint failed: {0}")]
    Mint(String),
    /// The identity did not verify against the trust roster anchor.
    #[error("identity did not verify against the trust roster: {0}")]
    Unverified(String),
    /// The identity is not a workload/node identity.
    #[error("identity is not a workload identity")]
    WrongKind,
    /// The identity names a different node than the one registering.
    #[error("identity subject {identity:?} does not name node {node:?}")]
    SubjectMismatch {
        /// The subject the identity claims.
        identity: String,
        /// The node actually registering.
        node: String,
    },
    /// The signed statement does not bind the submitted node trust profile.
    #[error("attestation statement does not match the node trust profile")]
    AttestationMismatch,
    /// The statement is absent, malformed, or expired at admission time.
    #[error("node attestation statement is expired or malformed")]
    AttestationExpired,
}

#[cfg(test)]
mod tests {
    use super::*;
    use fabric_crypto::providers::{MlDsa87Verifier, RustCryptoMlDsa87};
    use saddle_estate::{AttestationProfile, Capacity, NodeSpec, Resource};

    fn node(name: &str) -> Node {
        Resource::new(
            name,
            NodeSpec {
                ring: 1,
                attestation_floor: Classification::Secret,
                attestation: AttestationProfile::default(),
                capacity: Capacity::default(),
            },
        )
    }

    fn hour() -> Duration {
        Duration::hours(1)
    }

    #[test]
    fn an_anchor_signed_identity_joins() {
        let anchor = RustCryptoMlDsa87::generate("anchor").unwrap();
        let identity = mint_node_identity("node-a", "acme", &anchor, hour()).unwrap();
        let node = node("node-a");
        let registration = NodeRegistration {
            attestation: mint_node_attestation(&node, &anchor, hour()).unwrap(),
            node,
            identity,
        };
        let registrar = Registrar::new(anchor.public_key().to_vec());
        assert!(registrar.admit(&registration, &MlDsa87Verifier).is_ok());
    }

    #[test]
    fn a_spoofed_identity_is_rejected() {
        // The leaf is signed by an attacker key, not the anchor.
        let anchor = RustCryptoMlDsa87::generate("anchor").unwrap();
        let attacker = RustCryptoMlDsa87::generate("attacker").unwrap();
        let identity = mint_node_identity("node-a", "acme", &attacker, hour()).unwrap();
        let node = node("node-a");
        let registration = NodeRegistration {
            attestation: mint_node_attestation(&node, &attacker, hour()).unwrap(),
            node,
            identity,
        };
        let registrar = Registrar::new(anchor.public_key().to_vec());
        assert!(matches!(
            registrar.admit(&registration, &MlDsa87Verifier),
            Err(RegistrationError::Unverified(_))
        ));
    }

    #[test]
    fn an_identity_naming_another_node_is_rejected() {
        let anchor = RustCryptoMlDsa87::generate("anchor").unwrap();
        // A valid anchor-signed leaf, but for node-b — presented to register node-a.
        let identity = mint_node_identity("node-b", "acme", &anchor, hour()).unwrap();
        let node = node("node-a");
        let registration = NodeRegistration {
            attestation: mint_node_attestation(&node, &anchor, hour()).unwrap(),
            node,
            identity,
        };
        let registrar = Registrar::new(anchor.public_key().to_vec());
        assert!(matches!(
            registrar.admit(&registration, &MlDsa87Verifier),
            Err(RegistrationError::SubjectMismatch { .. })
        ));
    }

    #[test]
    fn a_tampered_node_profile_does_not_inherit_verified_attestation() {
        let anchor = RustCryptoMlDsa87::generate("anchor").unwrap();
        let mut submitted = node("node-a");
        let attestation = mint_node_attestation(&submitted, &anchor, hour()).unwrap();
        submitted.spec.ring = 2;
        let registration = NodeRegistration {
            node: submitted,
            identity: mint_node_identity("node-a", "acme", &anchor, hour()).unwrap(),
            attestation,
        };
        let registrar = Registrar::new(anchor.public_key().to_vec());
        assert!(matches!(
            registrar.admit(&registration, &MlDsa87Verifier),
            Err(RegistrationError::AttestationMismatch)
        ));
    }

    #[test]
    fn an_attacker_signed_attestation_is_rejected() {
        let anchor = RustCryptoMlDsa87::generate("anchor").unwrap();
        let attacker = RustCryptoMlDsa87::generate("attacker").unwrap();
        let submitted = node("node-a");
        let registration = NodeRegistration {
            attestation: mint_node_attestation(&submitted, &attacker, hour()).unwrap(),
            identity: mint_node_identity("node-a", "acme", &anchor, hour()).unwrap(),
            node: submitted,
        };
        let registrar = Registrar::new(anchor.public_key().to_vec());
        assert!(matches!(
            registrar.admit(&registration, &MlDsa87Verifier),
            Err(RegistrationError::Unverified(_))
        ));
    }
}
