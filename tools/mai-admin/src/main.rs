//! `mai-admin` CLI entry point.
//!
//! SHIP-09 wires `backup create` and `backup verify`; the remaining
//! `restore`, `audit`, `trust`, and `vault` subcommands ship in later
//! sessions and stub here with a clear exit-with-message so the
//! operator UX of `mai-admin --help` reflects the whole roadmap.
//!
//! Exit codes (stable, mirror SHIP-HARDENING-PLAN.md §13):
//!   0  ok
//!   1  backup or verification failed
//!   2  config / inputs unreadable
//!   3  state unreadable (manifest missing, paths gone)
//!   4  internal error

use std::path::{Path, PathBuf};
use std::process::ExitCode;

use clap::{Parser, Subcommand};
use mai_admin::manifest::MLDSA87_PK_LEN;
use mai_admin::profile::load_backup_source_profile;
use mai_admin::{
    BackupOptions, BackupReport, VerifyOutcome, VerifyReport, create_backup, verify_backup,
};

#[derive(Parser, Debug)]
#[command(name = "mai-admin", version, about = "MAI operator tooling")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand, Debug)]
enum Command {
    /// Backup management. SHIP-09.
    #[command(subcommand)]
    Backup(BackupCmd),
    /// Restore management. SHIP-10 (pending).
    Restore,
    /// Audit chain verification. Pending session.
    Audit,
    /// Trust bundle verification. Pending session.
    Trust,
    /// Vault status report. Pending session.
    Vault,
}

#[derive(Subcommand, Debug)]
enum BackupCmd {
    /// Take a new backup against a loaded ship profile.
    Create {
        /// Path to the ship profile TOML.
        #[arg(long)]
        profile: PathBuf,
        /// Parent directory; backup will be created at
        /// `<output>/<backup_id>/`.
        #[arg(long)]
        output: PathBuf,
        /// Optional override for the backup id; default
        /// `mai-backup-<rfc3339-stamp>`.
        #[arg(long)]
        backup_id: Option<String>,
        /// Path to a 4896-byte ML-DSA-87 secret key. When present the
        /// manifest is signed; ship profile requires it.
        #[arg(long)]
        signing_key: Option<PathBuf>,
        /// Stable identifier the verifier looks up the matching
        /// public key under. Required when `--signing-key` is set.
        #[arg(long)]
        anchor_id: Option<String>,
    },
    /// Verify a backup directory: manifest signature + per-component
    /// digests + audit chain replay.
    Verify {
        /// Backup directory (the one containing `manifest.json`).
        #[arg(long)]
        backup_dir: PathBuf,
        /// Path to a 2592-byte ML-DSA-87 public key file matching the
        /// `anchor_id` recorded in the manifest. When omitted the
        /// signature check is skipped (and `--require-signed` becomes a
        /// hard failure).
        #[arg(long)]
        verifying_key: Option<PathBuf>,
        /// Fail if the manifest is unsigned. Recommended in ship mode.
        #[arg(long, default_value_t = false)]
        require_signed: bool,
        /// Emit machine-readable JSON instead of the human report.
        #[arg(long, default_value_t = false)]
        json: bool,
    },
}

fn main() -> ExitCode {
    let cli = Cli::parse();
    match cli.command {
        Command::Backup(BackupCmd::Create {
            profile,
            output,
            backup_id,
            signing_key,
            anchor_id,
        }) => run_backup_create(&profile, &output, backup_id, signing_key, anchor_id),
        Command::Backup(BackupCmd::Verify {
            backup_dir,
            verifying_key,
            require_signed,
            json,
        }) => run_backup_verify(&backup_dir, verifying_key, require_signed, json),
        Command::Restore => {
            eprintln!("`mai-admin restore` lands in SHIP-10. Pending.");
            ExitCode::from(2)
        }
        Command::Audit => {
            eprintln!("`mai-admin audit verify` lands in a later session. Pending.");
            ExitCode::from(2)
        }
        Command::Trust => {
            eprintln!("`mai-admin trust verify` lands in a later session. Pending.");
            ExitCode::from(2)
        }
        Command::Vault => {
            eprintln!("`mai-admin vault status` lands in a later session. Pending.");
            ExitCode::from(2)
        }
    }
}

fn run_backup_create(
    profile_path: &Path,
    output_root: &Path,
    backup_id: Option<String>,
    signing_key_path: Option<PathBuf>,
    anchor_id: Option<String>,
) -> ExitCode {
    let profile = match load_backup_source_profile(profile_path) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("error: {e}");
            return ExitCode::from(2);
        }
    };

    let mut options = BackupOptions::from_env(output_root);
    options.backup_id = backup_id;
    if let Some(sk_path) = signing_key_path {
        match std::fs::read(&sk_path) {
            Ok(bytes) => {
                options.signing_key = Some(bytes);
                options.anchor_id = anchor_id.clone();
                if options.anchor_id.is_none() {
                    eprintln!("error: --anchor-id is required with --signing-key");
                    return ExitCode::from(2);
                }
            }
            Err(e) => {
                eprintln!(
                    "error: could not read signing key {}: {e}",
                    sk_path.display()
                );
                return ExitCode::from(2);
            }
        }
    }

    match create_backup(&profile, options) {
        Ok(report) => {
            print_create_report(&report);
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("backup create failed: {e}");
            ExitCode::from(1)
        }
    }
}

fn run_backup_verify(
    backup_dir: &Path,
    verifying_key_path: Option<PathBuf>,
    require_signed: bool,
    json: bool,
) -> ExitCode {
    let verifying_key = match verifying_key_path {
        Some(path) => match std::fs::read(&path) {
            Ok(bytes) => {
                if bytes.len() != MLDSA87_PK_LEN {
                    eprintln!(
                        "error: verifying key {} has length {} != {MLDSA87_PK_LEN}",
                        path.display(),
                        bytes.len()
                    );
                    return ExitCode::from(2);
                }
                Some(bytes)
            }
            Err(e) => {
                eprintln!(
                    "error: could not read verifying key {}: {e}",
                    path.display()
                );
                return ExitCode::from(2);
            }
        },
        None => None,
    };

    let report = match verify_backup(backup_dir, verifying_key.as_deref(), require_signed) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("verify failed: {e}");
            return ExitCode::from(3);
        }
    };

    if json {
        match serde_json::to_string_pretty(&VerifyJson::from(&report)) {
            Ok(s) => println!("{s}"),
            Err(e) => {
                eprintln!("error: could not serialize verify report: {e}");
                return ExitCode::from(4);
            }
        }
    } else {
        print_verify_report(&report);
    }

    if report.is_clean() {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(1)
    }
}

fn print_create_report(report: &BackupReport) {
    println!("backup created: {}", report.backup_id);
    println!("  dir       : {}", report.backup_dir.display());
    println!("  manifest  : {}", report.manifest_path.display());
    println!("  components: {}", report.component_count);
    println!("  signed    : {}", report.signed);
    if !report.warnings.is_empty() {
        println!("  warnings  :");
        for w in &report.warnings {
            println!("    - {w}");
        }
    }
}

fn print_verify_report(report: &VerifyReport) {
    println!("verify backup: {}", report.backup_id);
    println!("  dir       : {}", report.backup_dir.display());
    println!("  signature : {}", outcome_str(&report.signature_outcome));
    println!("  components: {}", report.component_count);
    if !report.warnings.is_empty() {
        println!("  warnings  :");
        for w in &report.warnings {
            println!("    - {w}");
        }
    }
    if report.failures.is_empty() {
        println!("  result    : OK");
    } else {
        println!("  result    : FAIL");
        for f in &report.failures {
            println!("    - {f}");
        }
    }
}

fn outcome_str(o: &VerifyOutcome) -> String {
    match o {
        VerifyOutcome::Signed { anchor_id } => format!("signed by anchor {anchor_id}"),
        VerifyOutcome::Unsigned => "unsigned".to_string(),
    }
}

#[derive(serde::Serialize)]
struct VerifyJson<'a> {
    backup_id: &'a str,
    backup_dir: String,
    signature_outcome: &'static str,
    anchor_id: Option<&'a str>,
    component_count: usize,
    failures: &'a [String],
    warnings: &'a [String],
    ok: bool,
}

impl<'a> From<&'a VerifyReport> for VerifyJson<'a> {
    fn from(r: &'a VerifyReport) -> Self {
        let (outcome, anchor) = match &r.signature_outcome {
            VerifyOutcome::Signed { anchor_id } => ("signed", Some(anchor_id.as_str())),
            VerifyOutcome::Unsigned => ("unsigned", None),
        };
        VerifyJson {
            backup_id: &r.backup_id,
            backup_dir: r.backup_dir.display().to_string(),
            signature_outcome: outcome,
            anchor_id: anchor,
            component_count: r.component_count,
            failures: &r.failures,
            warnings: &r.warnings,
            ok: r.is_clean(),
        }
    }
}
