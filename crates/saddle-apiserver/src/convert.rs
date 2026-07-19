//! Fail-closed estate version conversion.
//!
//! Stored objects are served through a single hub version. Conversion changes
//! only named structural identities; authority, UID, generation, resource
//! version, desired state, status, receipts, and opaque payloads remain byte-for-
//! byte equivalent as JSON values. Missing converters, non-advancing converters,
//! kind disagreement, and conversion cycles are errors rather than a request to
//! serve an unrecognized schema.

use std::collections::HashMap;

use saddle_estate::{API_VERSION, Kind};
use serde_json::{Map, Value};

const LEGACY_API_VERSION: &str = concat!("aog", ".islandmountain.io/v1");
const LEGACY_FINALIZER_PREFIX: &str = concat!("lo", "om", ".aog/");
const SADDLE_FINALIZER_PREFIX: &str = "saddle.islandmountain.io/";
const LEGACY_CORDON_LABEL: &str = concat!("lo", "om", ".io/unschedulable");
const SADDLE_CORDON_LABEL: &str = "saddle.islandmountain.io/unschedulable";

#[derive(Debug, thiserror::Error)]
pub enum ConversionError {
    #[error("resource kind is missing or does not match expected {expected}")]
    KindMismatch { expected: Kind },
    #[error("resource api_version is missing")]
    MissingVersion,
    #[error("no conversion from {version:?} to hub {hub:?} for {kind}")]
    UnsupportedVersion {
        kind: Kind,
        version: String,
        hub: String,
    },
    #[error("converter for {kind} did not advance api_version {version:?}")]
    DidNotAdvance { kind: Kind, version: String },
    #[error("conversion for {kind} exceeded the bounded chain length")]
    Cycle { kind: Kind },
    #[error("conversion rejected malformed structural state: {0}")]
    Malformed(String),
}

type Converter = Box<dyn Fn(Value) -> Result<Value, ConversionError> + Send + Sync>;

/// Per-kind single-step converters and the version served by the API.
pub struct ConversionRegistry {
    hub: String,
    converters: HashMap<(Kind, String), Converter>,
}

impl ConversionRegistry {
    /// Strict identity at the current hub. A non-hub object fails closed.
    #[must_use]
    pub fn identity() -> Self {
        Self {
            hub: API_VERSION.to_owned(),
            converters: HashMap::new(),
        }
    }

    /// The canonical Saddle v1 hub, including the bounded legacy estate-group
    /// conversion used during rolling reads of pre-cutover snapshots.
    #[must_use]
    pub fn saddle_v1() -> Self {
        let mut registry = Self::identity();
        for kind in Kind::ALL {
            registry = registry.with_fallible_converter(kind, LEGACY_API_VERSION, move |value| {
                convert_legacy_v1(kind, value)
            });
        }
        registry
    }

    #[must_use]
    pub fn new(hub: impl Into<String>) -> Self {
        Self {
            hub: hub.into(),
            converters: HashMap::new(),
        }
    }

    /// Register an infallible single-step converter.
    #[must_use]
    pub fn with_converter(
        self,
        kind: Kind,
        from: impl Into<String>,
        convert: impl Fn(Value) -> Value + Send + Sync + 'static,
    ) -> Self {
        self.with_fallible_converter(kind, from, move |value| Ok(convert(value)))
    }

    /// Register a fallible single-step converter.
    #[must_use]
    pub fn with_fallible_converter(
        mut self,
        kind: Kind,
        from: impl Into<String>,
        convert: impl Fn(Value) -> Result<Value, ConversionError> + Send + Sync + 'static,
    ) -> Self {
        self.converters
            .insert((kind, from.into()), Box::new(convert));
        self
    }

    #[must_use]
    pub fn hub(&self) -> &str {
        &self.hub
    }

    /// Convert a resource to the hub, refusing unknown or cyclic paths.
    pub fn convert(&self, kind: Kind, mut value: Value) -> Result<Value, ConversionError> {
        require_kind(kind, &value)?;
        for _ in 0..16 {
            let current = api_version(&value)?.to_owned();
            if current == self.hub {
                return Ok(value);
            }
            let convert = self
                .converters
                .get(&(kind, current.clone()))
                .ok_or_else(|| ConversionError::UnsupportedVersion {
                    kind,
                    version: current.clone(),
                    hub: self.hub.clone(),
                })?;
            value = convert(value)?;
            require_kind(kind, &value)?;
            if api_version(&value)? == current {
                return Err(ConversionError::DidNotAdvance {
                    kind,
                    version: current,
                });
            }
        }
        Err(ConversionError::Cycle { kind })
    }
}

impl Default for ConversionRegistry {
    fn default() -> Self {
        Self::saddle_v1()
    }
}

fn api_version(value: &Value) -> Result<&str, ConversionError> {
    value
        .get("api_version")
        .and_then(Value::as_str)
        .ok_or(ConversionError::MissingVersion)
}

fn require_kind(kind: Kind, value: &Value) -> Result<(), ConversionError> {
    let expected = kind.to_string();
    if value.get("kind").and_then(Value::as_str) == Some(expected.as_str()) {
        Ok(())
    } else {
        Err(ConversionError::KindMismatch { expected: kind })
    }
}

/// Convert exactly the retired estate v1 structural identities to Saddle v1.
/// No desired-state or authority-bearing field is otherwise interpreted.
pub fn convert_legacy_v1(kind: Kind, mut value: Value) -> Result<Value, ConversionError> {
    require_kind(kind, &value)?;
    if api_version(&value)? != LEGACY_API_VERSION {
        return Err(ConversionError::UnsupportedVersion {
            kind,
            version: api_version(&value)?.to_owned(),
            hub: API_VERSION.to_owned(),
        });
    }
    value["api_version"] = Value::String(API_VERSION.to_owned());
    rewrite_metadata(
        &mut value,
        LEGACY_FINALIZER_PREFIX,
        SADDLE_FINALIZER_PREFIX,
        LEGACY_CORDON_LABEL,
        SADDLE_CORDON_LABEL,
    )?;
    Ok(value)
}

/// Exact structural inverse used to prove legacy-state rollback. Callers use
/// this only for a value known to have come from [`convert_legacy_v1`].
pub fn rollback_legacy_v1(kind: Kind, mut value: Value) -> Result<Value, ConversionError> {
    require_kind(kind, &value)?;
    if api_version(&value)? != API_VERSION {
        return Err(ConversionError::UnsupportedVersion {
            kind,
            version: api_version(&value)?.to_owned(),
            hub: LEGACY_API_VERSION.to_owned(),
        });
    }
    value["api_version"] = Value::String(LEGACY_API_VERSION.to_owned());
    rewrite_metadata(
        &mut value,
        SADDLE_FINALIZER_PREFIX,
        LEGACY_FINALIZER_PREFIX,
        SADDLE_CORDON_LABEL,
        LEGACY_CORDON_LABEL,
    )?;
    Ok(value)
}

fn rewrite_metadata(
    value: &mut Value,
    old_finalizer: &str,
    new_finalizer: &str,
    old_label: &str,
    new_label: &str,
) -> Result<(), ConversionError> {
    let Some(metadata) = value.get_mut("metadata").and_then(Value::as_object_mut) else {
        return Err(ConversionError::Malformed("metadata is missing".to_owned()));
    };
    if let Some(finalizers) = metadata.get_mut("finalizers") {
        let finalizers = finalizers
            .as_array_mut()
            .ok_or_else(|| ConversionError::Malformed("finalizers is not an array".to_owned()))?;
        for finalizer in finalizers {
            let text = finalizer.as_str().ok_or_else(|| {
                ConversionError::Malformed("finalizer is not a string".to_owned())
            })?;
            if let Some(suffix) = text.strip_prefix(old_finalizer) {
                *finalizer = Value::String(format!("{new_finalizer}{suffix}"));
            }
        }
    }
    if let Some(labels) = metadata.get_mut("labels") {
        let labels = labels
            .as_object_mut()
            .ok_or_else(|| ConversionError::Malformed("labels is not an object".to_owned()))?;
        rewrite_label(labels, old_label, new_label)?;
    }
    Ok(())
}

fn rewrite_label(
    labels: &mut Map<String, Value>,
    old: &str,
    new: &str,
) -> Result<(), ConversionError> {
    let Some(value) = labels.remove(old) else {
        return Ok(());
    };
    if labels.get(new).is_some_and(|current| current != &value) {
        labels.insert(old.to_owned(), value);
        return Err(ConversionError::Malformed(
            "legacy and Saddle cordon labels conflict".to_owned(),
        ));
    }
    labels.insert(new.to_owned(), value);
    Ok(())
}
