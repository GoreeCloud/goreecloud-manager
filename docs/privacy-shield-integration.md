# GoreeCloud Manager Privacy Shield Integration

## Purpose

GoreeCloud Manager consumes a minimized GoreeCloud Privacy Shield status document so an authenticated administrator can see declared privacy capability and acceptance state without centralizing private activity.

Manager is a read-only status consumer. It is not a Privacy Shield enforcement runtime and does not become authoritative for browser filtering, DNS privacy enforcement, network privacy behavior, application telemetry policy, retention, deletion, or other runtime privacy controls.

## Shared contract

The producer contract is owned by `GoreeCloud/goreecloud-privacy-shield` through `contracts/privacy-shield.status.schema.json`.

Manager currently accepts schema version 1 only. Unsupported versions fail soft to an unavailable Privacy Shield state rather than being partially interpreted.

The status document contains only:

- producer adapter identity, product name, runtime repository authority, and adapter contract version;
- generation timestamp;
- broad Privacy Shield state;
- declared capability identifiers and their normalized states;
- explicit privacy guarantees that the document contains no raw private activity, credentials, or identifying content;
- runtime-acceptance and production-approval state.

## Data explicitly excluded

The Manager status path must not receive browsing history, visited URLs, search queries, DNS queries, network flows, source/destination addresses, cookies, authentication headers, passwords, tokens, private keys, setup keys, device identifiers, user identifiers, tracker-learning evidence, per-site exception contents, raw application telemetry, or other private activity merely to render centralized Privacy Shield status.

If a status document reports, omits, or ambiguously declares any of the three required privacy guarantees, Manager rejects the document and reports the integration unavailable.

## Runtime authority

Each Privacy Shield adapter remains authoritative for its own implementation and evidence. For example:

- GoreeCloud Browser owns Firefox/Gecko-specific Privacy Shield enforcement and compiled runtime acceptance.
- GoreeCloud DNS will own DNS privacy enforcement when its adapter is implemented and accepted.
- GoreeCloud Network will own networking-specific privacy behavior when its adapter is implemented and accepted.
- Other GoreeCloud applications retain their own storage, telemetry, retention, deletion, and export implementations.

Manager does not infer a privacy capability from product identity. A producer must declare capabilities through the approved Privacy Shield contracts.

## Acceptance boundary

`runtime_acceptance_required` must remain true. `production_approved` is supplied by the authoritative producer and is never promoted by Manager.

A successful Manager parser test or rendered page does not approve the producer runtime. A successful shared Privacy Shield contract validation does not approve Manager production adoption. Each side retains an independent validation and acceptance boundary.

## Manager configuration

Manager reads one local file path from:

```text
PRIVACY_SHIELD_STATUS_FILE
```

The intended long-lived deployment model is a read-only mount containing an approved sanitized status artifact. No active producer, host path, bind mount, production environment value, or target-runtime deployment is established by the initial source implementation.

Missing configuration, missing files, malformed JSON, unsupported schemas, unsafe privacy declarations, malformed producer metadata, invalid acceptance metadata, and malformed capability entries fail soft to an unavailable Privacy Shield state.

## User interface

Authenticated users may open `/privacy-shield/` from the Manager primary navigation. The Glaze UI surface shows only the normalized status, runtime authority, generation timestamp, production-approval state, and declared capability states.

The page explicitly identifies Manager as a read-only status consumer and states that raw private activity is not accepted by the contract.

## Security relationship

Privacy Shield remains the platform-wide privacy and privacy-control identity. Wardveil Security by GoreeCloud remains the separate platform-wide security and protection authority. Manager may present both identities without merging their responsibilities.

## Current implementation state

The Manager consumer, source tests, authenticated status surface, and shared status schema are development candidates. An actual runtime producer has not yet been accepted for this Manager path, and no end-to-end target-environment Privacy Shield status flow is claimed yet.
