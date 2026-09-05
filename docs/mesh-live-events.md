# Manager Mesh Live-Event Refresh

## Status

**Development / source implementation.** This document describes the Manager-side consumer implemented on this branch. It does not establish production GoreeCloud Mesh availability, production GoreeCloud Identity credential issuance, target-network acceptance, durable event delivery, or Manager Stable eligibility.

The source dependency is GoreeCloud Mesh's bounded authenticated event-consumer work (`GET /v1/events/stream`) and the registered `goreecloud.mesh.event.v1` contract. Manager must not treat the existence of this adapter as evidence that the dependency is deployed or accepted.

## Purpose

The Manager Platform Overview already reads normalized, authority-preserving records from Mesh `GET /v1/platform-registry`. Live-event refresh adds a narrow coordination hint so an authenticated Manager browser can refresh the Platform Overview after Mesh observes a service or relationship lifecycle change.

The event is **not** platform truth. An accepted event only causes Manager to re-read the Platform Registry. Producer records and the canonical GoreeCloud evaluator remain authoritative for the state shown after refresh.

## Accepted event contract

Manager requests exactly these registered Mesh event types:

- `mesh.service.upserted.v1`
- `mesh.relationship.upserted.v1`

The server-side adapter requires:

- envelope schema exactly `goreecloud.mesh.event.v1`;
- the closed expected envelope field set;
- `authority_transfer: false`;
- process-local `evt-<sequence>` event IDs;
- bounded, control-character-free source/subject/value fields;
- the exact type-specific closed data shape;
- a non-future timezone-aware `created_at` value; and
- an SSE event name matching the event payload type.

Unknown event types, extra payload fields, malformed values, replay fields such as SSE `id:`, invalid content type, oversized streams, and authority-transfer attempts fail closed for the current stream window.

## Identity and least privilege

The live-event adapter uses a **separate** GoreeCloud Identity service credential from the Platform Registry adapter.

Required event permission:

- audience: `goreecloud-mesh`
- scope: `mesh.events.read`

Platform Registry permission remains separate:

- scope: `mesh.platform-registry.read`

Manager must not assume one scope grants the other and must not use a write scope for either read path.

Configuration:

- `MESH_EVENTS_ENABLED=false` by default;
- exactly one of `MESH_EVENTS_ACCESS_TOKEN` or `MESH_EVENTS_ACCESS_TOKEN_FILE` when enabled;
- `MESH_EVENTS_BUFFER_SIZE`, from 1 through 64, default 8;
- `MESH_EVENTS_WINDOW_SECONDS`, from 1 through 10, default 5;
- the existing `MESH_API_URL` supplies the Mesh base URL.

A direct token is intended only for isolated development. Long-lived environments should use an approved protected, externally refreshed file-backed credential source. Manager rereads the file for each new stream and never stores the credential in its database or sends it to the browser.

## Browser boundary

The authenticated Manager endpoint is `/platform/events/`.

The endpoint never proxies the raw Mesh event. After full server-side validation, it emits only a same-origin SSE signal containing the registered event type:

```text
event: platform-update
data: {"type":"mesh.service.upserted.v1"}
```

The browser immediately closes the stream and reloads `/platform/`. That reload performs a fresh Platform Registry read using the separate registry credential and validation contract.

No Mesh credential, source/subject identifier, health value, relationship target/type, process-local event ID, or upstream error body is rendered into the browser signal.

## Delivery and replay boundary

This integration deliberately preserves Mesh's current live-only semantics:

- no replay cursor;
- no `Last-Event-ID` use;
- no event retention in Manager;
- no acknowledgement or delivery receipt;
- no exactly-once or at-least-once guarantee;
- no durable subscriber checkpoint;
- no irreversible Manager action may depend on delivery; and
- reconnecting may miss events between bounded Mesh stream windows.

Missing an event therefore cannot make Manager's Platform Registry data incorrect; it can only delay an automatic refresh until the operator reloads the page or a later event arrives.

## Failure behavior

Disabled or locally misconfigured event refresh returns HTTP 204 from Manager, which stops browser EventSource retry for that page load. Upstream connection, authorization, HTTP, content-type, or event-contract failures terminate the current best-effort stream without reflecting credential or remote error text.

The ordinary Manager Platform Overview remains usable. Event-stream failure does not manufacture platform state and does not change the Platform Registry adapter's own failure/freshness rules.

## Platform-system boundaries

- **Manager:** presents accepted normalized platform state and performs the page refresh only.
- **Identity:** owns the workload credential and `mesh.events.read` authorization.
- **Mesh:** owns the lifecycle-event transport contract and coordination event facts.
- **Privacy Shield:** remains authoritative for privacy/purpose/minimization requirements; this consumer retains no event journal.
- **Wardveil Security:** remains authoritative for security/trust requirements; Manager does not infer security state from event delivery.
- **Everkeep:** remains authoritative for backup/recovery; no durable event state exists here to claim recoverability for.
- **Glaze UI:** remains presentation authority; this live-refresh source work does not alter or satisfy Manager's separate current Stable Glaze migration/acceptance gate.

## Acceptance boundary

Before production activation, Manager still needs accepted Identity credential issuance/rotation, an accepted/deployed compatible Mesh event endpoint, target network and TLS acceptance, browser/runtime validation, monitoring and failure-behavior evidence, applicable Privacy Shield and Wardveil acceptance, and the independent current Stable Glaze application-conformance path.
