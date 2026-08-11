# NetBird Read-Only Integration

## Role

I use the NetBird adapter to give GoreeCloud Manager read-only visibility into current NetBird peer state. NetBird remains the authoritative system for private-network configuration and peer management.

## API Contract

Manager uses only:

```text
GET /api/peers
```

The runtime base URL is supplied through `NETBIRD_API_URL`. For the current GoreeCloud self-hosted deployment, the intended value is:

```text
https://netbird.goreecloud.com/api
```

No write-capable NetBird endpoint is implemented in Milestone 2.

## Authentication and Permission Boundary

The adapter uses a dedicated NetBird service-user personal access token supplied through `NETBIRD_API_TOKEN`.

The approved identity model is read-only/Auditor authority. I will not replace it with an administrator token merely to simplify integration.

The token must remain outside source control and ordinary documentation. Manager uses it only in the outbound `Authorization: Token ...` header and never returns that value to the registry, templates, health endpoint, or user interface.

## Configuration

```dotenv
NETBIRD_ENABLED=true
NETBIRD_API_URL=https://netbird.goreecloud.com/api
NETBIRD_API_TOKEN=<protected read-only token>
NETBIRD_TIMEOUT_SECONDS=5
```

`NETBIRD_TIMEOUT_SECONDS` defaults to five seconds and is capped at thirty seconds so a failed upstream service cannot hold the Manager Overview open indefinitely.

## Normalized Data

Manager retains only the peer fields needed for the current administrative view:

- Peer ID.
- Peer name.
- NetBird DNS label.
- NetBird IPv4 address.
- NetBird IPv6 address when available.
- Connected/disconnected state.
- Last-seen timestamp.
- Operating-system description.
- NetBird client version.

Manager does not make its local database authoritative for this peer information.

## Failure Behavior

The adapter is fail-soft and returns one of four application-facing states:

- `disabled` — live querying is intentionally off.
- `misconfigured` — the integration is enabled but a required non-secret configuration reference or token is missing.
- `healthy` — the peers endpoint returned a valid response that Manager normalized successfully.
- `unavailable` — the API timed out, could not be reached, rejected authentication, returned an HTTP error, or returned an unsafe/unexpected response shape.

Raw response bodies and authentication headers are not surfaced in failure messages.

## Explicitly Excluded Actions

This adapter cannot:

- Create, rename, approve, expire, or delete peers.
- Create, edit, or delete groups.
- Create, edit, or delete access policies.
- Create, edit, or delete routes or networks.
- Create or revoke setup keys.
- Create, edit, or delete users or service users.
- Change DNS settings.
- Change NetBird server configuration.

Any future write capability requires a separate approved specification, authorization model, recovery plan, test scope, and change-control decision.

## Validation Status

Mocked success and failure-path validation is part of the repository test suite. Live validation requires the protected GoreeCloud NetBird Auditor token at runtime and is intentionally not performed through public CI or committed fixtures.
