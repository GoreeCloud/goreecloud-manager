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
HEALTHCHECKS_API_URL=https://healthchecks.goreecloud.com/api/v3
HEALTHCHECKS_API_KEY=<protected read-only project API key>
HEALTHCHECKS_TIMEOUT_SECONDS=5
HEALTHCHECKS_API_HOST=healthchecks.goreecloud.com
HEALTHCHECKS_API_IP=100.71.27.119
```

The populated API key must remain in approved protected runtime configuration and must not be committed, pasted into issues, recorded in screenshots, or stored in ordinary documentation.

## Private Hostname Resolution

The current GoreeCloud Healthchecks service is privately published through the approved Caddy/NetBird path. The Manager Compose configuration supports an application-specific hostname mapping from `HEALTHCHECKS_API_HOST` to `HEALTHCHECKS_API_IP`.

This preserves:

- the `healthchecks.goreecloud.com` HTTPS hostname;
- normal TLS certificate validation and SNI;
- the private NetBird/Caddy destination;
- the existing VPS-wide DNS configuration.

The mapping is a runtime/deployment detail rather than a new public-service publication path.

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
- `unavailable` — timeout, reachability, authentication, HTTP, or malformed-response failure.

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
