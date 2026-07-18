// A CLI legitimately writes to stdout/stderr.
#![allow(clippy::print_stdout, clippy::print_stderr)]
//! `saddlectl` binary — a formatting shell over [`saddlectl::Client`] (kernel subset).
//!
//! Usage:
//!   saddlectl apply -f <file>          create-or-update a resource from a JSON file
//!   saddlectl get <Kind> [name]        fetch one, or list a kind
//!   saddlectl describe <Kind> <name>   fetch one as pretty JSON
//!   saddlectl delete <Kind> <name>     remove a resource
//!   saddlectl migrate <MODE> ...       migrate an offline versioned snapshot
//!
//! Server + token come from `SADDLECTL_SERVER` (default `http://127.0.0.1:8080`) and
//! `SADDLECTL_TOKEN`. `--output json` selects JSON; the default is a compact table.

use std::process::ExitCode;
use std::{fs::OpenOptions, io::Write};

use saddlectl::Client;
use saddlectl::migration::{
    EstateSnapshot, MigrationJournal, apply as apply_migration, dry_run, inspect, rollback, verify,
};
use serde::Serialize;
use serde_json::Value;

#[tokio::main]
async fn main() -> ExitCode {
    match run().await {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("saddlectl: {e}");
            ExitCode::from(2)
        }
    }
}

async fn run() -> Result<(), String> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let positional = positional(&args);
    let cmd = positional.first().map(String::as_str).ok_or_else(usage)?;
    if cmd == "migrate" {
        return run_migration(&args, &positional);
    }

    let server =
        std::env::var("SADDLECTL_SERVER").unwrap_or_else(|_| "http://127.0.0.1:8080".to_owned());
    let token = std::env::var("SADDLECTL_TOKEN").unwrap_or_default();
    let json_output = flag(&args, "--output")
        .or_else(|| flag(&args, "-o"))
        .as_deref()
        == Some("json");
    let client = Client::new(server, token);

    match cmd {
        "apply" => {
            let file = flag(&args, "-f")
                .or_else(|| flag(&args, "--file"))
                .ok_or("apply requires -f <file>")?;
            let text = std::fs::read_to_string(&file).map_err(|e| e.to_string())?;
            let body: Value = serde_json::from_str(&text).map_err(|e| e.to_string())?;
            let kind = body
                .get("kind")
                .and_then(Value::as_str)
                .ok_or("the resource body has no `kind`")?;
            let out = client.apply(kind, &body).await.map_err(|e| e.to_string())?;
            emit(&out, json_output);
        }
        "get" => {
            let kind = positional.get(1).ok_or("get <Kind> [name]")?;
            let out = match positional.get(2) {
                Some(name) => client.get(kind, name).await,
                None => client.list(kind).await,
            }
            .map_err(|e| e.to_string())?;
            emit(&out, json_output);
        }
        "describe" => {
            let kind = positional.get(1).ok_or("describe <Kind> <name>")?;
            let name = positional.get(2).ok_or("describe <Kind> <name>")?;
            let out = client.get(kind, name).await.map_err(|e| e.to_string())?;
            println!("{}", serde_json::to_string_pretty(&out).unwrap_or_default());
        }
        "delete" => {
            let kind = positional.get(1).ok_or("delete <Kind> <name>")?;
            let name = positional.get(2).ok_or("delete <Kind> <name>")?;
            client.delete(kind, name).await.map_err(|e| e.to_string())?;
            println!("{kind}/{name} deleted");
        }
        _ => return Err(usage()),
    }
    Ok(())
}

fn run_migration(args: &[String], positional: &[String]) -> Result<(), String> {
    let mode = positional
        .get(1)
        .map(String::as_str)
        .ok_or_else(migration_usage)?;
    let input = flag(args, "-f")
        .or_else(|| flag(args, "--file"))
        .ok_or_else(migration_usage)?;
    let snapshot: EstateSnapshot = read_json(&input)?;

    match mode {
        "inspect" => emit_json(&inspect(&snapshot).map_err(|error| error.to_string())?)?,
        "dry-run" => {
            let (_, report) = dry_run(&snapshot).map_err(|error| error.to_string())?;
            emit_json(&report)?;
        }
        "apply" => {
            let output = required_flag(args, "--out", mode)?;
            let journal_path = required_flag(args, "--journal", mode)?;
            ensure_distinct(&input, &output, &journal_path)?;
            ensure_absent(&output)?;
            ensure_absent(&journal_path)?;
            let (migrated, journal, report) =
                apply_migration(&snapshot).map_err(|error| error.to_string())?;
            write_json(&journal_path, &journal)?;
            write_json(&output, &migrated)?;
            emit_json(&report)?;
        }
        "verify" => {
            let journal_path = required_flag(args, "--journal", mode)?;
            let journal: MigrationJournal = read_json(&journal_path)?;
            emit_json(&verify(&snapshot, &journal).map_err(|error| error.to_string())?)?;
        }
        "rollback" => {
            let output = required_flag(args, "--out", mode)?;
            let journal_path = required_flag(args, "--journal", mode)?;
            ensure_distinct(&input, &output, &journal_path)?;
            ensure_absent(&output)?;
            let journal: MigrationJournal = read_json(&journal_path)?;
            let restored = rollback(&snapshot, &journal).map_err(|error| error.to_string())?;
            write_json(&output, &restored)?;
            emit_json(&verify(&snapshot, &journal).map_err(|error| error.to_string())?)?;
        }
        _ => return Err(migration_usage()),
    }
    Ok(())
}

fn read_json<T: serde::de::DeserializeOwned>(path: &str) -> Result<T, String> {
    let text = std::fs::read_to_string(path).map_err(|error| format!("{path}: {error}"))?;
    serde_json::from_str(&text).map_err(|error| format!("{path}: {error}"))
}

fn write_json<T: Serialize>(path: &str, value: &T) -> Result<(), String> {
    let mut encoded = serde_json::to_vec_pretty(value).map_err(|error| error.to_string())?;
    encoded.push(b'\n');
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)
        .map_err(|error| format!("{path}: {error}"))?;
    file.write_all(&encoded)
        .and_then(|()| file.sync_all())
        .map_err(|error| format!("{path}: {error}"))
}

fn emit_json<T: Serialize>(value: &T) -> Result<(), String> {
    println!(
        "{}",
        serde_json::to_string_pretty(value).map_err(|error| error.to_string())?
    );
    Ok(())
}

fn required_flag(args: &[String], name: &str, mode: &str) -> Result<String, String> {
    flag(args, name).ok_or_else(|| format!("migrate {mode} requires {name} <file>"))
}

fn ensure_distinct(input: &str, output: &str, journal: &str) -> Result<(), String> {
    let input = normalized_path(input)?;
    let output = normalized_path(output)?;
    let journal = normalized_path(journal)?;
    if input == output || input == journal || output == journal {
        Err("migration input, output, and journal paths must be distinct".to_owned())
    } else {
        Ok(())
    }
}

fn normalized_path(path: &str) -> Result<String, String> {
    let path = std::path::Path::new(path);
    let absolute = if path.exists() {
        std::fs::canonicalize(path).map_err(|error| format!("{path:?}: {error}"))?
    } else {
        let parent = path
            .parent()
            .filter(|parent| !parent.as_os_str().is_empty())
            .unwrap_or_else(|| std::path::Path::new("."));
        let parent =
            std::fs::canonicalize(parent).map_err(|error| format!("{parent:?}: {error}"))?;
        let file = path
            .file_name()
            .ok_or_else(|| format!("invalid output path {path:?}"))?;
        parent.join(file)
    };
    Ok(absolute.to_string_lossy().to_lowercase())
}

fn ensure_absent(path: &str) -> Result<(), String> {
    match std::fs::symlink_metadata(path) {
        Ok(_) => Err(format!("migration output already exists: {path}")),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(format!("cannot inspect migration output {path}: {error}")),
    }
}

/// Positional arguments with known flag values removed.
fn positional(args: &[String]) -> Vec<String> {
    let mut out = Vec::new();
    let mut it = args.iter();
    while let Some(a) = it.next() {
        if matches!(
            a.as_str(),
            "-f" | "--file" | "-o" | "--output" | "--out" | "--journal"
        ) {
            it.next(); // consume the flag's value
        } else if !a.starts_with('-') {
            out.push(a.clone());
        }
    }
    out
}

/// The value following `name` (`--name value` or `--name=value`).
fn flag(args: &[String], name: &str) -> Option<String> {
    let prefix = format!("{name}=");
    let mut it = args.iter();
    while let Some(a) = it.next() {
        if a == name {
            return it.next().cloned();
        }
        if let Some(rest) = a.strip_prefix(&prefix) {
            return Some(rest.to_owned());
        }
    }
    None
}

/// Print `value` as pretty JSON, or a compact `KIND NAME REV` table.
fn emit(value: &Value, json_output: bool) {
    if json_output {
        println!(
            "{}",
            serde_json::to_string_pretty(value).unwrap_or_default()
        );
        return;
    }
    println!("{:<18} {:<24} {:<8}", "KIND", "NAME", "REV");
    if let Some(items) = value.get("items").and_then(Value::as_array) {
        for item in items {
            print_row(item);
        }
    } else if !value.is_null() {
        print_row(value);
    }
}

fn print_row(item: &Value) {
    let kind = item.get("kind").and_then(Value::as_str).unwrap_or("-");
    let meta = item.get("metadata");
    let name = meta
        .and_then(|m| m.get("name"))
        .and_then(Value::as_str)
        .unwrap_or("-");
    let rev = meta
        .and_then(|m| m.get("resource_version"))
        .and_then(Value::as_u64)
        .unwrap_or(0);
    println!("{kind:<18} {name:<24} {rev:<8}");
}

fn usage() -> String {
    "usage: saddlectl <apply -f FILE | get KIND [NAME] | describe KIND NAME | delete KIND NAME | migrate MODE ...> [--output json]"
        .to_owned()
}

fn migration_usage() -> String {
    "usage: saddlectl migrate <inspect|dry-run> -f SNAPSHOT | apply -f SNAPSHOT --out MIGRATED --journal JOURNAL | verify -f MIGRATED --journal JOURNAL | rollback -f MIGRATED --journal JOURNAL --out RESTORED"
        .to_owned()
}
