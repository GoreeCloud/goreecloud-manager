# Uptime Kuma Integration

## Role

Uptime Kuma provides GoreeCloud Manager with read-only visibility into current service and endpoint availability. Uptime Kuma remains authoritative for monitor configuration, heartbeat processing, maintenance state, notification routing, history, and alerting.

## Purpose

The Manager adapter answers a narrow set of operational questions:

- How many monitor status samples are currently exposed by Uptime Kuma?
- Which monitored services are up, down, pending, or in maintenance?
- What monitor display name and monitor type are associated with each visible sample?
- What current response time does Uptime Kuma report when that metric is available?
- When did Manager successfully observe the current metrics payload?

The adapter does not turn Manager into an Uptime Kuma configuration or control interface.

## Metrics Contract

Manager uses Uptime Kuma's protected Prometheus metrics endpoint:

```text
GET /metrics
```

In Uptime Kuma 2.5.0 the endpoint is protected by `apiAuth`. When API keys are enabled, Uptime Kuma accepts the generated API key as the **password** portion of HTTP Basic authentication with an empty username.

Conceptually:

```text
Authorization: Basic base64(":" + API_KEY)
```

Manager uses the dedicated `goreecloud-manager-metrics` API key and does not receive the Uptime Kuma administrator password.

The API key is a reusable secret and must remain only in approved protected runtime configuration. It must not be committed, pasted into issues, recorded in screenshots, or stored in ordinary documentation.

## Configuration

```dotenv
UPTIME_KUMA_ENABLED=true
UPTIME_KUMA_METRICS_URL=http://uptime-kuma:3001/metrics
UPTIME_KUMA_API_KEY=<protected metrics API key>
UPTIME_KUMA_TIMEOUT_SECONDS=5
```

## Service-to-Service Network

On the GoreeCloud VPS, Manager reaches Uptime Kuma directly over the dedicated external Docker network `manager-uptime`.

The approved path is:

```text
GoreeCloud Manager
        |
        | manager-uptime
        v
Uptime Kuma :3001/metrics
```

The network is intentionally separate from the existing `proxy` network used by Caddy.

The design preserves the following boundaries:

- Manager does not join Uptime Kuma's persistent-data path or receive access to its application database.
- Manager does not receive the Docker socket.
- Manager does not receive Uptime Kuma administrator credentials.
- Manager does not receive Socket.IO monitor-management authority.
- Uptime Kuma does not publish a new host port.
- Caddy, NetBird, DNS, and firewall publication controls remain unchanged.
- Docker service discovery uses the stable `uptime-kuma` service/container name rather than a temporary container IP.
- The cross-stack dependency is explicit and recoverable through Compose declarations.

The external `manager-uptime` network must be created deliberately on the Docker host before the stacks are recreated with the dependency. It should be an internal bridge network because it exists only for same-host service communication.

## Normalized Fields

The raw Prometheus payload may contain target-oriented labels such as URLs, hostnames, or ports. Manager deliberately discards those labels and retains only the approved display subset:

- monitor name;
- monitor type;
- normalized current state;
- response time in milliseconds, when reported.

Manager also records the local observation time for the successful metrics request.

Manager normalizes Uptime Kuma monitor status values as:

- `0` -> `down`
- `1` -> `up`
- `2` -> `pending`
- `3` -> `maintenance`
- any otherwise valid but unsupported numeric status -> `unknown`

A `down`, `pending`, or `unknown` monitor causes the Uptime Kuma integration summary to become `degraded`. Maintenance is reported separately and does not by itself mean the metrics integration has failed.

## Interface Limitations

The protected metrics endpoint is intentionally narrower than Uptime Kuma's authenticated management interface.

For Milestone 3C, Manager does not claim visibility into fields that the metrics endpoint does not safely and consistently expose, including:

- paused-monitor inventory;
- per-monitor heartbeat timestamps;
- monitor authentication headers;
- request bodies;
- target URLs;
- target hostnames or ports;
- notification configuration;
- monitor-management metadata.

The Overview explicitly states these limitations instead of inventing values or reading the Uptime Kuma database directly.

## Failure Behavior

The adapter fails soft. It returns a sanitized state instead of raising integration failures through the Manager Overview.

Expected states are:

- `disabled` — adapter intentionally disabled;
- `misconfigured` — required metrics URL or API key is absent;
- `healthy` — live metrics were retrieved and no monitor is down, pending, or unknown;
- `degraded` — live metrics were retrieved but at least one monitor requires attention, or no monitor-status samples were present;
- `unavailable` — timeout, reachability, rejected API key, denied endpoint, HTTP error, or malformed metrics failure.

HTTP `401` is classified as a rejected metrics API key. HTTP `403` is classified separately as denied access to the metrics endpoint.

Raw metrics payloads, API keys, Basic Auth headers, target URLs, target hostnames, target ports, and other reusable secrets are not rendered.

## Explicitly Excluded Operations

The adapter does not implement:

- monitor creation;
- monitor edits;
- monitor deletion;
- pause or resume actions;
- maintenance creation or modification;
- notification management;
- API-key management;
- Socket.IO login or management operations;
- direct SQLite/database access.

Any future write-capable Uptime Kuma feature requires separate specification, permission review, tests, and approval.
