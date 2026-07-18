mod common;

use axum::http::StatusCode;
use chrono::{Duration, Utc};
use fabric_contracts::{Caveat, CaveatType};
use fabric_revocation::{RevocationSnapshot, sign as sign_revocation};

use common::*;

#[tokio::test]
async fn missing_nonce_and_replayed_authority_fail_closed() {
    let signer = anchor();
    let app = app_anchored("saddle-sad31-nonce", &signer, None).await;
    let token = header_for(&mint(&signer));
    let collection = format!("{BASE}/PolicyBundle");

    let (status, _) = send_with_nonce(
        &app,
        "POST",
        &collection,
        Some(&token),
        Some(bundle("missing", 1)),
        None,
    )
    .await;
    assert_eq!(status, StatusCode::UNAUTHORIZED);

    let (status, _) = send_with_nonce(
        &app,
        "POST",
        &collection,
        Some(&token),
        Some(bundle("first", 1)),
        Some("one-use-authority"),
    )
    .await;
    assert_eq!(status, StatusCode::CREATED);
    let (status, _) = send_with_nonce(
        &app,
        "POST",
        &collection,
        Some(&token),
        Some(bundle("replay", 1)),
        Some("one-use-authority"),
    )
    .await;
    assert_eq!(status, StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn stale_bundle_and_stale_revocation_fail_closed_on_mutation() {
    let signer = anchor();
    let app = app_anchored("saddle-sad31-stale-bundle", &signer, None).await;
    let stale_bundle = header_for(&mint_with(&signer, |token| {
        token.trust_bundle_version = "2026.06.stale".to_owned();
    }));
    let (status, _) = send(
        &app,
        "POST",
        &format!("{BASE}/PolicyBundle"),
        Some(&stale_bundle),
        Some(bundle("stale-bundle", 1)),
    )
    .await;
    assert_eq!(status, StatusCode::UNAUTHORIZED);

    let expired = sign_revocation(
        RevocationSnapshot::new(
            "stale-revocation",
            (Utc::now() - Duration::hours(2)).to_rfc3339(),
            (Utc::now() - Duration::hours(1)).to_rfc3339(),
        )
        .with_sequence(1),
        &signer,
    )
    .unwrap();
    let app = app_anchored("saddle-sad31-stale-revocation", &signer, Some(expired)).await;
    let (status, _) = send(
        &app,
        "POST",
        &format!("{BASE}/PolicyBundle"),
        Some(&header_for(&mint(&signer))),
        Some(bundle("stale-revocation", 1)),
    )
    .await;
    assert_eq!(status, StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn spoofed_anchor_and_out_of_scope_resource_fail_closed() {
    let signer = anchor();
    let app = app_anchored("saddle-sad31-spoof", &signer, None).await;
    let rogue = anchor();
    let (status, _) = send(
        &app,
        "POST",
        &format!("{BASE}/PolicyBundle"),
        Some(&header_for(&mint(&rogue))),
        Some(bundle("spoofed", 1)),
    )
    .await;
    assert_eq!(status, StatusCode::UNAUTHORIZED);

    let scoped = header_for(&mint_with(&signer, |token| {
        token.attenuation.caveats.push(Caveat {
            caveat_type: CaveatType::ResourcePrefix,
            value: "tenants/".to_owned(),
        });
    }));
    let (status, _) = send(
        &app,
        "POST",
        &format!("{BASE}/PolicyBundle"),
        Some(&scoped),
        Some(bundle("outside-scope", 1)),
    )
    .await;
    assert_eq!(status, StatusCode::FORBIDDEN);
}

#[tokio::test]
async fn cross_tenant_authority_cannot_mutate_the_final_resource() {
    let signer = anchor();
    let app = app_anchored("saddle-sad31-cross-tenant", &signer, None).await;
    let owner = header_for(&mint(&signer));
    let intruder = header_for(&mint_with(&signer, |token| {
        token.token_id = "tok-intruder".to_owned();
        token.tenant_id = "tenant-intruder".to_owned();
        token.subject_hash = "hmac:intruder".to_owned();
    }));
    let collection = format!("{BASE}/PolicyBundle");
    let (status, mut object) = send(
        &app,
        "POST",
        &collection,
        Some(&owner),
        Some(bundle("tenant-bound", 1)),
    )
    .await;
    assert_eq!(status, StatusCode::CREATED);
    object["spec"]["version"] = 2.into();
    let (status, _) = send(
        &app,
        "PUT",
        &format!("{collection}/tenant-bound"),
        Some(&intruder),
        Some(object),
    )
    .await;
    assert_eq!(status, StatusCode::FORBIDDEN);
}
