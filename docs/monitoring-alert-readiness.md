# GoreeCloud Manager Monitoring and Alert-Delivery Readiness

## Purpose

This document defines the source-controlled, disposable monitoring and alert-delivery validation used to prepare GoreeCloud Manager for future production monitoring without registering a real Uptime Kuma monitor, changing production Caddy, installing production notification credentials, or altering an existing ntfy route.

Manager already exposes a minimal unauthenticated `/healthz/` endpoint and has a read-only Uptime Kuma integration for administrative visibility. Those features do not by themselves prove that an independent monitoring service can reach Manager through the intended private HTTPS path, detect a service outage, publish a least-privilege alert, and report recovery. This readiness gate validates that external monitoring chain in a disposable environment.

## Proposed Uptime Kuma contract

`scripts/manager_uptime_kuma_monitor.json` is explicitly marked `proposed-not-provisioned` and defines the intended production-pattern monitor:

- monitor name: `GoreeCloud Manager`;
- monitor type: HTTP;
- URL: `https://manager.goreecloud.com/healthz/`;
- method: GET;
- interval: 60 seconds;
- accepted status: HTTP 200 only;
- TLS verification: required;
- private Caddy path: required;
- monitoring source container: `uptime-kuma`;
- Docker network: `proxy`;
- source IPv4: `172.19.0.50`;
- Caddy source allowlist: required.

The source identity follows the established GoreeCloud Uptime Kuma private-monitoring pattern already validated for GoreeCloud Tasks. Final live source-address observation is still required on the target host before production activation.

## Proposed alert-delivery contract

The monitoring publisher uses the existing GoreeCloud Uptime alert domain:

- service identity: `uptime-kuma`;
- ntfy permission: write-only;
- internal ntfy endpoint: `http://ntfy:80`;
- topic: `goreecloud-uptime`;
- DOWN title: `GoreeCloud Manager DOWN`;
- RECOVERED title: `GoreeCloud Manager RECOVERED`.

The disposable validation uses a separate read-only subscriber identity. The write-only publisher must not be able to subscribe, the read-only subscriber must not be able to publish, and an anonymous client must not be able to read the protected topic.

Sanitized messages are limited to:

- DOWN: `GoreeCloud Manager health endpoint is unavailable. Review Uptime Kuma and protected service logs.`
- RECOVERED: `GoreeCloud Manager health endpoint recovered.`

The payload validation rejects authentication/session/secret markers and does not include application content, user data, integration data, credentials, or raw upstream responses.

## Disposable topology

`scripts/monitoring_alert.compose.yml` creates:

- `manager` — the exact candidate Manager image using the accepted hardened runtime and file-backed synthetic Django secret;
- `caddy` — pinned Caddy using an internal CA and the exact `manager.goreecloud.com` hostname;
- `ntfy` — pinned disposable ntfy with deny-all default ACLs;
- `monitor` — a synthetic Uptime Kuma-like client fixed at `172.19.0.50`;
- `subscriber` — a separate read-only alert consumer.

All services share only the isolated internal `proxy` network needed for this validation. No service publishes a host port. Manager retains:

- non-root `manager` execution;
- read-only root filesystem;
- all Linux capabilities dropped;
- `no-new-privileges`;
- bounded `/tmp` tmpfs;
- dedicated writable SQLite volume;
- no Docker socket;
- no optional production integration credentials.

The Caddy fixture accepts both the synthetic NetBird range `100.64.0.0/10` and the documented Uptime Kuma source `172.19.0.50`, then reverse-proxies only to `goreecloud-manager:8000`. Other sources receive HTTP 403.

## Validation sequence

`scripts/validate_monitoring_alert_readiness.sh` performs these checks:

1. Generate runtime-random synthetic Django and ntfy credentials in a private temporary directory.
2. Build a disposable ntfy configuration with deny-all default access, a write-only Uptime publisher, and a read-only subscriber.
3. Validate the proposed-not-provisioned monitor contract and explicit production limitations.
4. Validate the Caddy hostname, TLS mode, approved-source matcher, Manager backend alias, and default HTTP 403 denial.
5. Render the Compose topology and reject host-published ports, network drift, monitor-IP drift, missing Manager runtime hardening, or direct Django secret values.
6. Build the exact candidate Manager image.
7. Start Manager and Caddy and validate the Caddy configuration.
8. Start disposable ntfy, the synthetic monitor, and the subscriber.
9. Require the internal ntfy health endpoint to become ready.
10. From source `172.19.0.50`, verify the exact private Manager HTTPS health URL using the disposable Caddy CA; certificate verification is not disabled.
11. Require HTTP 200 and the exact minimal Manager health payload.
12. Confirm that no alert is emitted while Manager is initially healthy.
13. Prove the write-only monitor cannot subscribe, the read-only subscriber cannot publish, and an anonymous client cannot subscribe.
14. Stop Manager while leaving Caddy, ntfy, the monitor, and subscriber running.
15. Require the private health probe to observe a server-side failure and publish the sanitized DOWN transition.
16. Require the subscriber to observe exactly the DOWN notification.
17. Restart Manager and wait for its real container health check.
18. Require verified private HTTPS health to recover and publish the sanitized RECOVERED transition.
19. Require the subscriber to observe the exact `DOWN → RECOVERED` title order and only approved minimized message bodies.
20. Inspect the live topology and require the monitor runtime address to remain `172.19.0.50`, every service to remain on only the expected internal network, and every service to have zero host port bindings.
21. Reinspect Manager for the non-root/read-only/cap-drop/no-Docker-socket runtime boundary.
22. Scan rendered Compose data, live Docker inspection data, and runtime logs for all generated synthetic secret values.
23. Remove containers, network, volumes, and temporary credentials during cleanup.

## What a green gate proves

A green Monitoring Alert Readiness workflow proves for the exact source revision under test that:

- the proposed Uptime Kuma monitor contract remains source-controlled and explicitly unprovisioned;
- the intended monitoring source identity and Caddy allowlist pattern are preserved;
- Manager's `/healthz/` endpoint is reachable through verified private HTTPS from that source;
- a healthy Manager does not create a false-positive alert;
- a controlled Manager outage is visible through Caddy as a server-side failure;
- the least-privilege write-only ntfy publisher can deliver a sanitized DOWN alert;
- the protected read-only subscriber can receive the alert while being unable to publish;
- restored Manager health produces a sanitized RECOVERED alert;
- the observed alert order is exactly DOWN then RECOVERED;
- runtime networking, source IP, Manager hardening, zero-host-port exposure, and synthetic-secret minimization remain intact.

## What the gate does not prove

This validation does **not**:

- register a real Uptime Kuma monitor;
- change the production Caddyfile or its source allowlist;
- prove the source address observed by the live production Caddy instance;
- install or rotate a production Uptime Kuma notification credential;
- assign a real ntfy notification integration to a production monitor;
- select final retry, retry-interval, or request-timeout values;
- prove receipt on an approved administrator's real client;
- prove an independent/out-of-band path if Uptime Kuma or ntfy itself is unavailable;
- modify production DNS, NetBird, firewall, monitoring, notification, backup, data, or deployment state;
- authorize production activation.

Those remain separate approval-controlled target-environment evidence.

## Rollback

The source implementation is reversible through Git. The workflow creates only disposable monitoring state and removes its containers, network, volumes, configuration, and generated credentials after every run. No live GoreeCloud Manager, Uptime Kuma, ntfy, Caddy, DNS, or network resource is modified.
