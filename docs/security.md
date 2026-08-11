# Security Model

- Application authentication is required independently of NetBird reachability.
- Production uses HTTPS termination through Caddy and the approved private-service publication model.
- Session and CSRF cookies are secure when `DJANGO_DEBUG=false`.
- Reusable secrets are environment-specific and are excluded from source control.
- Read-only API credentials are preferred.
- `/var/run/docker.sock` is explicitly excluded from the Manager container.
- The health endpoint contains no private infrastructure details.
- Integrated-service failures must not leak credentials or raw authentication responses into the UI.
