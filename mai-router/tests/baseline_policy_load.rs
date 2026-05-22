//! Smoke test: the three baseline policy TOMLs ship-with-product load
//! cleanly and contribute rules at expected priorities.

use std::path::PathBuf;

use mai_router::PolicyModuleRegistry;

fn config_path(name: &str) -> PathBuf {
    let mut path = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    path.push("rules-config");
    path.push(name);
    path
}

#[test]
fn session37_hipaa_baseline_loads_and_contributes_rules() {
    let reg = PolicyModuleRegistry::new();
    reg.load_from_path("hipaa_baseline", &config_path("hipaa.toml"))
        .expect("hipaa.toml must load");
    let rules = reg.enabled_rules();
    assert!(!rules.is_empty(), "hipaa baseline must contribute rules");
    assert!(rules.iter().any(|r| r.name.contains("phi")));
}

#[test]
fn session37_itar_baseline_loads_critical_rule() {
    let reg = PolicyModuleRegistry::new();
    reg.load_from_path("itar_baseline", &config_path("itar.toml"))
        .expect("itar.toml must load");
    let rules = reg.enabled_rules();
    assert!(rules.iter().any(|r| r.name.contains("export_controlled")));
}

#[test]
fn session37_ocap_baseline_loads_and_contributes_rules() {
    let reg = PolicyModuleRegistry::new();
    reg.load_from_path("ocap_baseline", &config_path("ocap.toml"))
        .expect("ocap.toml must load");
    let rules = reg.enabled_rules();
    assert!(rules.iter().any(|r| r.name.contains("tribal")));
}

#[test]
fn session37_all_three_baselines_compose() {
    let reg = PolicyModuleRegistry::new();
    for (name, file) in [
        ("hipaa_baseline", "hipaa.toml"),
        ("itar_baseline", "itar.toml"),
        ("ocap_baseline", "ocap.toml"),
    ] {
        reg.load_from_path(name, &config_path(file))
            .expect("baseline must load");
    }
    let rules = reg.enabled_rules();
    // Sanity: all three modules contributed something.
    assert!(rules.iter().any(|r| r.name.starts_with("hipaa")));
    assert!(rules.iter().any(|r| r.name.starts_with("itar")));
    assert!(rules.iter().any(|r| r.name.starts_with("ocap")));
}
