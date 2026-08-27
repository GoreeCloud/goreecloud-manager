# GoreeCloud Manager Everkeep Integration

GoreeCloud Manager consumes only a sanitized, versioned Everkeep resilience-status document. Source systems and approved Everkeep runtime adapters remain authoritative for backup, restore, preservation, continuity, portability, succession, and recovery behavior.

Manager is a read-only observer. It must not ingest backup contents, file inventories, recovery codes, encryption keys, credentials, private paths, personal records, raw succession or legacy records, or raw adapter exceptions.

The current contract accepts schema version 1 and requires explicit producer/runtime authority, generation time, resilience states, acceptance metadata, unique capability identifiers, and negative declarations for all prohibited sensitive-content classes. Missing or ambiguous declarations fail closed to an unavailable integration state.

`EVERKEEP_STATUS_FILE` identifies the local sanitized status artifact. This Development slice does not activate a producer, production mount, network endpoint, recovery operation, backup/restore workflow, or Stable classification.
