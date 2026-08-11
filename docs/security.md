# Security Model

- Application authentication is required independently of NetBird reachability.
- Production uses HTTPS termination through Caddy and the approved private-service publication model.
- Session and CSRF cookies are secure when `DJANGO_DEBUG=false`.
- Reusable secrets are environment-specific and are excluded from source control.
- Read-only API credentials are preferred.
- The NetBird adapter is intentionally limited to `GET /api/peers` and contains no write-capable API method.
- The intended NetBird credential is a dedicated service-user token with read-only/Auditor authority.
- NetBird tokens are read only from process environment configuration and are never returned by the adapter, registry, templates, or health endpoint.
- API authentication failures and malformed responses are sanitized before they reach the user interface.
- `/var/run/docker.sock` is explicitly excluded from the Manager container.
- The health endpoint contains no private infrastructure details.
- Integrated-service failures must not leak credentials, raw authentication headers, or upstream response bodies into the UI.
- Outbound API connectivity does not authorize direct public inbound access to Manager; the development backend remains loopback-bound.
