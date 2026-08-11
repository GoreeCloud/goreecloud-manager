# Healthchecks Integration

## Role

Healthchecks provides GoreeCloud Manager with read-only visibility into scheduled-job and heartbeat monitoring. Healthchecks remains authoritative for check configuration, status computation, schedules, grace periods, ping history, integrations, and alerting.

## Purpose

The Manager adapter answers a narrow set of operational questions:

- How many checks are currently represented in the configured Healthchecks project?
- Which checks are up, in grace, down, paused, or new?
- When did a check last report?
- When is the next report expected where Healthchecks provides that value?
- What schedule or expected period and grace window apply?
- Is the GoreeCloud Kopia backup-monitoring check currently healthy?

The adapter does not turn Manager into a Healthchecks configuration interface.

## API Contract

Manager uses the documented Healthchecks Management API v3 checks-list endpoint:

```text
GET /api/v3/checks/
```

Authentication uses a project-specific **read-only API key** supplied in the `X-Api-Key` request header.

Healthchecks documentation states that a read-only API key is restricted to read endpoints and that read-only check responses omit the check UUID, ping URL, update URL, pause URL, resume URL, and channel identifiers. Manager does not reconstruct or expose those omitted fields.

## Configuration

```dotenv
HEALTHCHECKS_ENABLED=true
HEALTHCHECKS_API_URL=http://healthchecks:8000/api/v3
HEALTHCHECKS_API_KEY=<protected read-only project API key>
HEALTHCHECKS_TIMEOUT_SECONDS=5
```

The populated API key must remain in approved protected runtime configuration and must not be committed, pasted into issues, recorded in screenshots, or stored in ordinary documentation.

## Service-to-Service Network

On the GoreeCloud VPS, Manager reaches the Healthchecks application container directly over the dedicated external Docker network `manager-healthchecks`.

The approved path is:

```text
GoreeCloud Manager
        |
        | manager-healthchecks
        v
Healthchecks application :8000
```

This network is intentionally separate from both the public/private Caddy publication path and Healthchecks' `healthchecks-internal` application/database network.

The design preserves the following boundaries:

- Manager does not join `healthchecks-internal` and therefore does not receive a network path to the Healthchecks PostgreSQL container.
- Healthchecks does not publish a new host port.
- Caddy's NetBird-only access policy remains unchanged.
- Manager does not hairpin through the VPS NetBird address to query a service already running on the same Docker host.
- Docker service discovery uses the stable `healthchecks` container/service name rather than a temporary container IP.
- The cross-stack dependency is explicit and recoverable through the external network declaration in each Compose stack.

The external `manager-healthchecks` network must be created deliberately on the Docker host before either stack is recreated with the dependency. It should be an internal bridge network because it exists only for same-host service communication.

## Normalized Fields

Manager accepts and normalizes only fields required by the authenticated Overview:

- stable read-only identifier (`unique_key` when supplied);
- name;
- slug;
- tags;
- status;
- started flag;
- last-ping timestamp;
- next-ping timestamp;
- expected period/timeout;
- grace period;
- schedule expression;
- schedule timezone.

Manager supports Healthchecks' documented check states:

- `new`
- `up`
- `grace`
- `down`
- `paused`

A `down` or `grace` check causes the Healthchecks integration summary to become `degraded`. Other integrations remain independently available.

## Kopia Protection Signal

The existing Healthchecks check named `GoreeCloud Kopia Backup` (slug `goreecloud-kopia-backup`) is shown as a protection-monitoring signal.

This means Manager can report whether Healthchecks considers the Kopia backup job current or late/down. It does **not** mean Manager has directly verified:

- a Kopia snapshot ID;
- repository connectivity;
- repository integrity;
- retention state;
- snapshot contents;
- storage capacity;
- restore capability.

Those facts remain Kopia/recovery-system responsibilities and require a separate read-only protection adapter or delegated status source.

## Failure Behavior

The adapter fails soft. It returns a sanitized state rather than raising integration errors through the Manager Overview.

Expected states are:

- `disabled` — adapter intentionally disabled;
- `misconfigured` — required API URL or API key is absent;
- `healthy` — read-only data was retrieved and no check is in `down` or `grace`;
- `degraded` — live data was retrieved but at least one check is in `down` or `grace`, or the configured project returned no checks;
- `unavailable` — timeout, reachability, authentication, authorization/path denial, HTTP, or malformed-response failure.

HTTP `401` is classified as a rejected credential. HTTP `403` is deliberately classified separately as a denied API request path so an infrastructure access-control response is not misreported as a bad read-only key.

Raw response bodies, API keys, authentication headers, ping URLs, and other reusable credentials are not rendered.

## Explicitly Excluded Operations

The adapter does not implement:

- check creation;
- check updates;
- pause or resume actions;
- deletion;
- ping submission;
- ping-body retrieval;
- notification-channel management;
- API-key management.

Any future write-capable Healthchecks feature requires separate specification, permission review, tests, and approval.
