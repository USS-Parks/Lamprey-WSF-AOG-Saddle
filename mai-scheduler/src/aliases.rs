//! Model alias resolution.
//!
//! Maps user-facing model names (like "lamprey/fast") to backend model
//! identifiers (like "llama3-8b") with an ordered list of preferred
//! adapter types. The alias resolver also handles the fallback chain:
//! if no preferred backend has an instance, any available instance for
//! the backend model is acceptable.
//!
//! Aliases are loaded from the `[aliases]` section of scheduler.toml.

use std::collections::HashMap;
use std::sync::RwLock;

use tracing::{debug, info};

use crate::types::ModelAlias;

/// Resolution result: the backend model name and ordered backend preferences.
#[derive(Debug, Clone)]
pub struct ResolvedAlias {
    /// The backend model name (e.g., "llama3-8b").
    pub model: String,
    /// Ordered list of preferred adapter types. Empty = no preference.
    pub preferred_backends: Vec<String>,
}

/// Thread-safe alias resolver. Uses `RwLock` for read-heavy workload
/// (resolves on every request, reloads rarely on config change).
pub struct AliasResolver {
    /// Alias map: user-facing name -> ModelAlias.
    aliases: RwLock<HashMap<String, ModelAlias>>,
}

impl AliasResolver {
    /// Create an empty resolver.
    pub fn new() -> Self {
        Self {
            aliases: RwLock::new(HashMap::new()),
        }
    }

    /// Create a resolver pre-loaded with aliases.
    pub fn from_config(aliases: HashMap<String, ModelAlias>) -> Self {
        info!(count = aliases.len(), "Alias resolver loaded");
        Self {
            aliases: RwLock::new(aliases),
        }
    }

    /// Resolve a user-facing model alias to a backend model name.
    ///
    /// If the alias is not found, the input is treated as a literal backend
    /// model name (passthrough). This allows users to directly specify
    /// backend model names if they know them.
    pub fn resolve(&self, alias: &str) -> ResolvedAlias {
        let aliases = self.aliases.read().expect("alias lock poisoned");

        if let Some(mapping) = aliases.get(alias) {
            debug!(alias = alias, model = %mapping.model, "Alias resolved");
            ResolvedAlias {
                model: mapping.model.clone(),
                preferred_backends: mapping.preferred_backends.clone(),
            }
        } else {
            // Passthrough: treat the alias as a literal model name
            debug!(
                alias = alias,
                "No alias found, treating as literal model name"
            );
            ResolvedAlias {
                model: alias.to_string(),
                preferred_backends: Vec::new(),
            }
        }
    }

    /// Check if an alias exists in the configuration.
    pub fn has_alias(&self, alias: &str) -> bool {
        let aliases = self.aliases.read().expect("alias lock poisoned");
        aliases.contains_key(alias)
    }

    /// Reload aliases from a new configuration. Called on config hot-reload.
    pub fn reload(&self, new_aliases: HashMap<String, ModelAlias>) {
        let mut aliases = self.aliases.write().expect("alias lock poisoned");
        let old_count = aliases.len();
        *aliases = new_aliases;
        info!(
            old_count = old_count,
            new_count = aliases.len(),
            "Alias resolver reloaded"
        );
    }

    /// Number of configured aliases.
    pub fn count(&self) -> usize {
        let aliases = self.aliases.read().expect("alias lock poisoned");
        aliases.len()
    }

    /// List all alias names. Used by health/debug endpoints.
    pub fn list_aliases(&self) -> Vec<String> {
        let aliases = self.aliases.read().expect("alias lock poisoned");
        aliases.keys().cloned().collect()
    }
}

impl Default for AliasResolver {
    fn default() -> Self {
        Self::new()
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn test_aliases() -> HashMap<String, ModelAlias> {
        let mut map = HashMap::new();
        map.insert(
            "lamprey/fast".to_string(),
            ModelAlias {
                model: "llama3-8b".to_string(),
                preferred_backends: vec!["ollama".to_string(), "vllm".to_string()],
            },
        );
        map.insert(
            "lamprey/reason".to_string(),
            ModelAlias {
                model: "qwen3-70b".to_string(),
                preferred_backends: vec!["vllm".to_string()],
            },
        );
        map.insert(
            "lamprey/embed".to_string(),
            ModelAlias {
                model: "nomic-embed-text".to_string(),
                preferred_backends: vec!["ollama".to_string()],
            },
        );
        map
    }

    #[test]
    fn test_resolve_known_alias() {
        let resolver = AliasResolver::from_config(test_aliases());
        let resolved = resolver.resolve("lamprey/fast");
        assert_eq!(resolved.model, "llama3-8b");
        assert_eq!(resolved.preferred_backends, vec!["ollama", "vllm"]);
    }

    #[test]
    fn test_resolve_unknown_passthrough() {
        let resolver = AliasResolver::from_config(test_aliases());
        let resolved = resolver.resolve("some-raw-model-name");
        assert_eq!(resolved.model, "some-raw-model-name");
        assert!(resolved.preferred_backends.is_empty());
    }

    #[test]
    fn test_has_alias() {
        let resolver = AliasResolver::from_config(test_aliases());
        assert!(resolver.has_alias("lamprey/fast"));
        assert!(!resolver.has_alias("nonexistent"));
    }

    #[test]
    fn test_reload() {
        let resolver = AliasResolver::from_config(test_aliases());
        assert_eq!(resolver.count(), 3);

        let mut new_map = HashMap::new();
        new_map.insert(
            "new/alias".to_string(),
            ModelAlias {
                model: "new-model".to_string(),
                preferred_backends: vec![],
            },
        );
        resolver.reload(new_map);

        assert_eq!(resolver.count(), 1);
        assert!(resolver.has_alias("new/alias"));
        assert!(!resolver.has_alias("lamprey/fast"));
    }

    #[test]
    fn test_list_aliases() {
        let resolver = AliasResolver::from_config(test_aliases());
        let mut names = resolver.list_aliases();
        names.sort();
        assert_eq!(
            names,
            vec!["lamprey/embed", "lamprey/fast", "lamprey/reason"]
        );
    }

    #[test]
    fn test_empty_resolver() {
        let resolver = AliasResolver::new();
        assert_eq!(resolver.count(), 0);
        let resolved = resolver.resolve("anything");
        assert_eq!(resolved.model, "anything");
    }
}
