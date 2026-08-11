# Beszel read-only resource visibility

## Purpose

GoreeCloud Manager surfaces selected current Beszel host and container resource data without receiving Beszel credentials, PocketBase auth tokens, Beszel application data, Beszel agent credentials, or Docker access.

Beszel remains authoritative for resource monitoring, historical charts, alerts, and system configuration. Manager presents a sanitized current-state view only.

## Validated Beszel 0.18.7 boundary

The live GoreeCloud deployment uses Beszel Hub and Agent 0.18.7. The Hub exposes its PocketBase API on container port 8090 and is not directly host-published. The existing Beszel Agent retains its read-only Docker socket mount; Manager does not receive that mount.

Anonymous PocketBase list requests for `systems`, `system_stats`, `system_details`, `containers`, `container_stats`, and `systemd_services` returned no records.

A dedicated Beszel user is configured with role `readonly` and only the approved `goreecloud-vps-01` system record is shared with that identity. Live validation confirmed that the identity sees exactly one system.

Beszel's readonly role blocks system/system-scoped writes, but it is not globally write-free because authenticated users can manage certain user-owned records such as alerts/settings. For that reason the credential is not placed inside the Manager container.

## Architecture

```text
Beszel Hub
    |
    | auth POST + approved GET reads
    v
host-side delegated collector
    |
    | sanitized JSON artifact
    v
/srv/docker/appdata/goreecloud-manager/integrations/beszel/status.json
    |
    | read-only bind mount
    v
GoreeCloud Manager
```

The authentication POST is the only non-GET HTTP operation performed by the collector and is required by PocketBase to obtain a temporary auth token. After authentication, the collector performs only approved GET data reads.

The collector credential is stored outside Manager in protected host-side secret storage. The default collector path is:

```text
/srv/docker/secrets/goreecloud-manager-beszel/credentials.json
```

The populated credential file must not be committed. The intended permissions are a root-owned `0700` secret directory and `0600` credential file.

## Collector scope

The collector verifies all of the following before accepting data:

- authentication succeeds;
- the authenticated record role is exactly `readonly`;
- the identity sees exactly one system;
- approved Beszel/PocketBase responses are structurally valid.

Approved reads are limited to:

- `/api/beszel/info` for the Beszel version;
- `systems` for current system name/status/update and compact `info` values;
- latest `system_stats` for current host resource metrics;
- the `system_details` record whose record ID equals the approved system ID;
- `containers` for current container state/health;
- latest `container_stats` for current CPU, memory, and network counters.

The collector does not query alerts, user settings, quiet hours, fingerprints, universal tokens, container logs, container details, notification configuration, or raw Beszel application data.

## Sanitized artifact schema version 1

The artifact contains only:

- `schema_version`;
- `generated_at`;
- collector state and check time;
- source system name, current Beszel system state, source update timestamp, Agent version, and Hub version;
- latest resource observation time;
- CPU percentage and load average;
- memory total/used/percentage;
- swap total/used;
- root-disk total/used/percentage;
- latest aggregate sent/received byte counters when present;
- temperature values when present;
- approved system details: hostname, kernel, cores, threads, CPU model, OS name, architecture, memory bytes, and Podman boolean;
- container name, current state, normalized health state, CPU percentage, memory usage, and latest sent/received byte counters when present.

The artifact intentionally excludes:

- Beszel email/password;
- PocketBase auth tokens;
- PocketBase user IDs and system record IDs;
- system host/port target configuration;
- Beszel Agent key/token;
- Docker socket or Docker API data not explicitly normalized above;
- container image names and port mappings;
- Beszel application database/files;
- alert/notification configuration;
- raw API responses.

## Failure behavior

The collector writes a sanitized collector state of `ok`, `auth_error`, `unavailable`, or `error`. When a refresh fails and a previous valid artifact exists, only the previously sanitized resource fields are preserved; credentials and raw responses are never written.

Manager fails soft:

- missing artifact -> `unavailable`;
- malformed/unsupported artifact -> `unavailable`;
- fresh collector failure with previous data -> `degraded`;
- collector failure without previous data -> `unavailable`;
- stale artifact -> `degraded`;
- stale resource observation -> `degraded`;
- Beszel system state other than `up` -> `degraded`.

Manager `/healthz/` remains independent of Beszel state.

Default freshness windows are:

- artifact: 15 minutes;
- underlying resource observation: 30 minutes.

## Manager configuration

```text
BESZEL_ENABLED=true
BESZEL_STATUS_HOST_DIR=/srv/docker/appdata/goreecloud-manager/integrations/beszel
BESZEL_STATUS_PATH=/app/integrations/beszel/status.json
BESZEL_STATUS_MAX_AGE_SECONDS=900
BESZEL_DATA_MAX_AGE_SECONDS=1800
```

Compose mounts only the sanitized host directory read-only at `/app/integrations/beszel`.

## UI meaning

The Beszel section is resource-monitoring visibility. It must remain distinct from:

- Uptime Kuma service-availability monitoring;
- Healthchecks scheduled-job monitoring;
- Kopia protection/snapshot state.

Beszel resource data does not prove service availability, backup success, restore readiness, or production readiness. Historical analysis and alerting authority remain in Beszel.

All displayed timestamps are rendered by Manager in `America/Chicago` using 12-hour AM/PM formatting.
