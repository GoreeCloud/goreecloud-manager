# GoreeCloud Manager Platform Overview

## Purpose

Manager's authenticated `/platform/` surface provides one read-only view of GoreeCloud component lifecycle, Platform System results, declared dependencies, runtime state, canonical conformance evidence, continuity evidence, and evidence freshness. The source is the authority-preserving GoreeCloud Mesh Platform Registry v1 read API.

This feature reduces platform-status fragmentation. It does not make Manager the authoritative database for producer lifecycle, security, privacy, recovery, health, Glaze UI, Identity, Mesh, canonical conformance, or release facts.

## Integration contract

Manager uses only:

- `GET /v1/platform-registry`
- a GoreeCloud Identity service credential carrying `mesh.platform-registry.read`
- normalized `goreecloud.mesh.platform-record.v1` records using GoreeCloud Platform Contract schema `0.2`

Manager does **not** require or request `mesh.platform-registry.write`. It does not call a producer database or filesystem and does not mutate a Mesh registry record.

Configuration is opt-in through:

- `MESH_ENABLED`
- `MESH_API_URL`
- exactly one of `MESH_ACCESS_TOKEN` or `MESH_ACCESS_TOKEN_FILE`
- `MESH_TIMEOUT_SECONDS`
- `MESH_PLATFORM_RECORD_MAX_AGE_SECONDS`

A direct token is intended only for isolated development. The file-backed source is reread on every request so an approved external GoreeCloud Identity credential lifecycle can replace the credential without storing it in Manager's database. Production identity issuance, refresh/rotation, secret mounting, network publication, and acceptance remain separately governed.

When Mesh is enabled, the deployment must explicitly choose `MESH_PLATFORM_RECORD_MAX_AGE_SECONDS`. Manager intentionally has no hidden platform-evidence freshness threshold. This keeps freshness policy visible and deployment-specific instead of silently converting an implementation constant into GoreeCloud governance.

## Normalized fields

Manager accepts and displays only the platform fields needed by this feature:

- component ID, product name, kind, repository, exact source revision, version, lifecycle, and supported platforms;
- declared capabilities, dependencies, and explicit relationships;
- the seven Integral Platform System `result` values using the exact Platform Contract v0.2 machine vocabulary;
- runtime, health, and readiness state;
- backup status and restore status as separate facts;
- last verified restore time only when restore state is `verified`;
- export/portability state;
- repository-declared conformance;
- canonical evaluator-computed conformance, Stable eligibility, evaluator repository/revision/time, blockers, and missing mandatory evidence identifiers;
- producer observation time and Manager-local freshness classification.

Mesh evidence payloads, bearer credentials, private keys, arbitrary producer payloads, raw user activity, browsing/DNS history, and raw upstream error bodies are not presented by this integration.

## Authority and fail-closed rules

The adapter rejects a record when:

- the source requests authority transfer;
- the source repository differs from the component repository;
- the source or evaluator revision is not an exact lowercase 40-character Git revision;
- the Platform Contract schema is not `0.2`;
- lifecycle or Platform System vocabulary is legacy or unsupported;
- the seven-system result set is incomplete or extended;
- the evaluator repository is not exactly `GoreeCloud/GoreeCloud`;
- backup/restore/export verification vocabulary is unsupported;
- recovery semantics are contradictory;
- a verified-restore timestamp is in the future;
- producer observation or canonical evaluation evidence is future-dated;
- nonconformant or unverified state claims Stable eligibility; or
- a `stable` lifecycle record lacks current canonical `conformant` status and Stable eligibility.

Manager also rejects non-loopback plain-HTTP Mesh configuration and malformed, oversized, or multiline service credentials before network use.

A healthy HTTP transport is not enough to make invalid data displayable. Unsupported or malformed responses become a sanitized `schema-invalid` integration condition.

Authentication establishes access to Mesh, not truth for every field. The originating component remains authoritative for its declaration and evidence; `GoreeCloud/GoreeCloud` remains authoritative for the computed conformance result bound to the evaluator revision represented by the record.

## Freshness and stale favorable state

Freshness is a Manager presentation decision, not a producer-state rewrite.

For each accepted record, Manager calculates age from both:

- `observed_at`, representing the producer observation carried in the Mesh record; and
- `conformance.evaluated_at`, representing the canonical conformance evaluation time.

If either age exceeds the explicitly configured `MESH_PLATFORM_RECORD_MAX_AGE_SECONDS`, the record is marked `stale` and the Platform snapshot becomes `degraded` with condition `stale-records`.

A stale record remains visible with its exact producer and canonical-evaluator values for investigation. Manager does **not** replace `conformant` with `nonconformant`, change lifecycle, remove Stable eligibility from the producer record, or manufacture a new recovery result. Instead, stale favorable records are excluded from Manager's current summary counts for:

- canonical-evaluator conformant components;
- Stable-eligible components; and
- verified restore evidence.

This prevents an old favorable record from appearing as current platform truth while preserving provenance and producer authority. The UI labels stale records as historical producer state and prompts operators to refresh or republish the source evidence.

## Continuity Health

Manager deliberately presents backup and restore evidence separately.

A `backup_status: verified` value does not cause Manager to say that a component is restorable. The Platform page treats continuity as verified only when `restore_status` is `verified` **and** a concrete `last_verified_restore` timestamp is present. This preserves Everkeep authority and prevents backup-job success from being presented as restoration proof.

Even a correctly formed historical verified-restore record is excluded from the current verified-restore summary when the platform record is stale. The original restore status and timestamp remain visible as historical producer evidence.

## Failure behavior

The Mesh adapter participates in Manager's existing bounded integration executor and request budget. Disabled, misconfigured, unreachable, authentication-rejected, authorization-denied, endpoint-unavailable, oversized, and schema-invalid conditions fail soft: the authenticated Manager shell remains available and presents a sanitized source-unavailable state instead of inventing platform facts.

A stale but structurally valid registry is different from an unavailable source. Manager keeps the records visible in a degraded presentation state so operators can understand exactly what evidence became old without presenting it as current.

Unexpected adapter exceptions are contained by the same integration fault-isolation boundary as Manager's other adapters. Logs contain the integration key, request correlation identifier, and exception class only; protected exception text and credentials are not intentionally logged or rendered.

## Glaze UI presentation status

The Platform page uses Manager's current repository-local presentation shell and adds only a bounded page stylesheet. It does **not** claim current Stable GLAZE UI conformance.

The authoritative GoreeCloud Platform Contract currently requires GLAZE UI V1.1 / `1.1.0` for applicable Stable consumer conformance. Manager's existing source still identifies an older application-specific Glaze baseline, so `goreecloud.platform.yaml` correctly remains `applicable-migration-required` for Glaze UI until the whole applicable interface is migrated and application-specific rendered acceptance evidence exists.

## Current implementation status

This candidate is source implementation for a read-only Manager consumer of the stacked Mesh Platform Registry API candidate. It must pass Manager's exact-head CI/readiness gates and its upstream Mesh API dependency must be reconciled before merge/release decisions.

The source-level adapter and authenticated Platform page do not establish accepted GoreeCloud Identity credential issuance/rotation, live Mesh publication, Manager-to-Mesh network acceptance, Wardveil Security runtime acceptance, Privacy Shield runtime acceptance, Everkeep target recovery acceptance, current Stable Glaze UI acceptance, production deployment, release approval, or Platform Stable eligibility.

It does not provision a production Mesh endpoint, GoreeCloud Identity credential, Caddy route, DNS record, NetBird policy, firewall rule, secret mount, monitoring rule, production backup, or deployment.
