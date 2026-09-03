# GoreeCloud Manager Platform Overview

## Purpose

Manager's authenticated `/platform/` surface provides one read-only view of GoreeCloud component lifecycle, Platform System conformance, declared dependencies, runtime state, and continuity evidence. The source is the authority-preserving GoreeCloud Mesh Platform Registry v1 read API.

This feature reduces platform-status fragmentation. It does not make Manager the authoritative database for producer lifecycle, security, privacy, recovery, health, Glaze UI, Identity, Mesh, or release facts.

## Integration contract

Manager uses only:

- `GET /v1/platform-registry`
- a GoreeCloud Identity service credential carrying `mesh.platform-registry.read`
- the normalized `goreecloud.mesh.platform-record.v1` records returned by Mesh

Manager does **not** require or request `mesh.platform-registry.write`. It does not call a producer database or filesystem and does not mutate a Mesh registry record.

Configuration is opt-in through:

- `MESH_ENABLED`
- `MESH_API_URL`
- exactly one of `MESH_ACCESS_TOKEN` or `MESH_ACCESS_TOKEN_FILE`
- `MESH_TIMEOUT_SECONDS`

A direct token is intended only for isolated development. The file-backed source is reread on every request so an approved external GoreeCloud Identity credential lifecycle can replace the credential without storing it in Manager's database. Production identity issuance, refresh/rotation, secret mounting, network publication, and acceptance remain separately governed.

## Normalized fields

Manager accepts and displays only the platform fields needed by this feature:

- component ID, product name, kind, repository, source revision, version, lifecycle, and supported platforms;
- declared capabilities, dependencies, and explicit relationships;
- the seven Integral Platform System states;
- runtime, health, and readiness state;
- backup status and restore status as separate facts;
- last verified restore time only when restore state is `verified`;
- export/portability state;
- producer-computed conformance result and Stable eligibility; and
- missing mandatory evidence identifiers.

Mesh evidence payloads, bearer credentials, private keys, arbitrary producer payloads, and raw upstream error bodies are not presented by this integration.

## Authority and fail-closed rules

The adapter rejects a record when the source requests authority transfer, the source repository differs from the component repository, the Platform Contract schema is unsupported, required Platform System state is absent, recovery semantics are contradictory, or non-conformant state claims Stable eligibility.

A healthy HTTP transport is not enough to make invalid data displayable. Unsupported or malformed responses become a sanitized `schema-invalid` integration condition.

Authentication establishes access to Mesh, not truth for every field. The originating component and applicable GoreeCloud platform authorities remain responsible for the underlying evidence and acceptance.

## Continuity Health

Manager deliberately presents backup and restore evidence separately.

A `backup_status: verified` value does not cause Manager to say that a component is restorable. The Platform page treats continuity as verified only when `restore_status` is `verified` **and** a concrete `last_verified_restore` timestamp is present. This preserves Everkeep authority and prevents backup-job success from being presented as restoration proof.

## Failure behavior

The Mesh adapter participates in Manager's existing bounded integration executor and request budget. Disabled, misconfigured, unreachable, authentication-rejected, authorization-denied, endpoint-unavailable, oversized, and schema-invalid conditions fail soft: the authenticated Manager shell remains available and presents a sanitized source-unavailable state instead of inventing platform facts.

Unexpected adapter exceptions are contained by the same integration fault-isolation boundary as Manager's other adapters. Logs contain the integration key, request correlation identifier, and exception class only; protected exception text and credentials are not intentionally logged or rendered.

## Glaze UI 2.2 presentation

The Platform page inherits the accepted source-level Manager Glaze UI 2.2 shell. Durable reading and decision surfaces are solid. No new nested backdrop blur or competing dominant Glaze panel is introduced. The page uses responsive grids that collapse to one column under small widths and explicit 200% text mode.

This repository source implementation does not by itself establish application-specific browser Human Visual Excellence, target-device acceptance, production deployment, release acceptance, or Platform Stable eligibility.

## Current implementation status

This candidate is source implementation for a read-only Manager consumer of the stacked Mesh Platform Registry API candidate. It must pass Manager's exact-head CI/readiness gates and its upstream Mesh API dependency must be reconciled before merge/release decisions.

It does not provision a production Mesh endpoint, GoreeCloud Identity credential, Caddy route, DNS record, NetBird policy, firewall rule, secret mount, monitoring rule, production backup, or deployment.
