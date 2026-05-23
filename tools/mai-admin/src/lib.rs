//! MAI operator tooling. SHIP-09 lands `backup create` and
//! `backup verify`; SHIP-10 will add `restore plan/apply`. Library
//! surface area is kept narrow on purpose so the CLI binary and the
//! SHIP-14 burn-in scripts can drive backups without re-spawning the
//! process.

pub mod audit;
pub mod backup;
pub mod manifest;
pub mod profile;

pub use audit::{AuditEntry, GENESIS_HASH, verify_chain};
pub use backup::{
    BackupError, BackupOptions, BackupReport, VerifyReport, create_backup, verify_backup,
};
pub use manifest::{
    BackupManifest, MLDSA87_PK_LEN, MLDSA87_SIG_LEN, MLDSA87_SK_LEN, ManifestComponent,
    ManifestError, ManifestSignatures, VerifyOutcome, sha3_file, sha3_hex, sha3_tree,
};
pub use profile::{
    BackupSourceProfile, ProfileLoadError, load_backup_source_profile, parse_backup_source_profile,
};
