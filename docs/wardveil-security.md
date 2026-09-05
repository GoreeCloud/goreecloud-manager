# Manager ↔ Wardveil Security status visibility

## Status

This document describes a **Development/source integration**. It does not establish production Wardveil Security acceptance, production GoreeCloud Mesh evidence delivery, production GoreeCloud Identity credential issuance, or a production security claim.

## Purpose

GoreeCloud Manager surfaces bounded Wardveil Security state for administrative visibility without becoming a security authority.

The integration uses GoreeCloud Mesh's authenticated evidence plane instead of adding a private Manager-to-Wardveil status API:

```text
Wardveil Security
  producer-authoritative security-status evidence
        |
        v
GoreeCloud Mesh evidence plane
  transport + producer/freshness preservation
        |
        |  mesh.evidence.read
        v
GoreeCloud Manager
  read-only presentation
```

Wardveil remains authoritative for security policy, trust, findings, protection decisions, security evidence, and authorized security execution. Mesh remains coordination/evidence transport. Manager only presents accepted minimized evidence.

## Accepted evidence

Manager requests only evidence matching all of these filters:

- producer: `wardveil-security`;
- authority domain: `security`;
- assertion: `security-status`.

Every returned envelope is then validated again locally. Manager requires:

- `goreecloud.evidence-envelope.v1`;
- producer repository `GoreeCloud/goreecloud-wardveil-security`;
- an exact 40-character producer Git revision;
- producer contract `contracts/wardveil.status.schema.json`;
- authority domain `security`;
- assertion `security-status`;
- one of the Wardveil status outcomes `protected`, `attention`, `degraded`, `unknown`, or `not_applicable`;
- no user content and no secret material;
- approved `public`, `operational`, or `derived` data classification;
- valid timezone-aware observation and validity timestamps;
- Mesh freshness that agrees with the producer-declared validity window;
- bounded identifiers, summaries, envelope counts, response bytes, and credential sizes.

Unexpected envelope fields, producer spoofing, authority mismatch, an unsupported contract, invalid timestamps, inconsistent freshness, secret/user-content flags, malformed digests, and oversized responses fail closed.

## Security-claim boundary

A successful Mesh read is not a security verdict.

Manager preserves Wardveil's `outcome` as a producer-reported value. Manager does **not** infer a new `Protected by Wardveil` claim from transport success, a green UI state, a current envelope, or an earlier protected observation. In particular, a stale `protected` outcome is displayed only as historical producer evidence and must not remain a current protection claim.

The minimized Mesh envelope does not transfer Wardveil authority to either Mesh or Manager.

## Freshness and history

Manager does not invent a second security-evidence freshness threshold. The evidence envelope already carries producer-declared `valid_until`, and Mesh exposes whether that evidence is current at read time.

Manager verifies those values agree. For presentation, Manager keeps only the latest observation for each `(subject kind, subject id, scope)` tuple in memory for the current request. It does not create a second Wardveil evidence history store; history remains with the producer/approved evidence plane.

An empty evidence result is presented as unknown. Stale-only evidence remains visible as historical state but cannot create a current security claim.

## Authentication and least privilege

This consumer requires a **separate GoreeCloud Identity service credential** with:

- audience: `goreecloud-mesh`;
- scope: `mesh.evidence.read` only for this path.

It must not reuse or broaden Manager's separate Platform Registry credential (`mesh.platform-registry.read`) or live lifecycle-event credential (`mesh.events.read`).

Manager supports direct and file-backed credential configuration. Long-lived environments should use an approved externally refreshed file-backed secret source. Credentials are never rendered in the Manager UI or stored in Manager's database.

Configuration variables:

```text
WARDVEIL_STATUS_ENABLED=false
MESH_API_URL=https://<approved-mesh-host>
MESH_WARDVEIL_EVIDENCE_TOKEN=
MESH_WARDVEIL_EVIDENCE_TOKEN_FILE=
WARDVEIL_STATUS_TIMEOUT_SECONDS=5
```

Set exactly one token source. `MESH_API_URL` requires HTTPS except for loopback development.

## Runtime and production boundary

Source implementation does not prove production availability. Acceptance still requires, at minimum:

- durable GoreeCloud Identity signing-key custody and live workload-bound service-token issuance;
- deployed JWKS verification and credential rotation/revocation evidence;
- live Wardveil production of approved minimized `security-status` evidence;
- live Mesh persistence/routing/read authorization in the target environment;
- accepted Manager-to-Mesh TLS/network routing;
- Privacy Shield review of the operational data exposed to Manager;
- applicable Wardveil, Mesh, Identity, Everkeep, Glaze UI, deployment, monitoring, recovery, and release gates.

Until those are validated, the Platform Contract remains `applicable-blocked` for Wardveil Security even though the read-only consumer exists at source level.
