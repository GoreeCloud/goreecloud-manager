# GoreeCloud Manager Runtime and Private-Publication Readiness

## Purpose

This document defines the source-controlled, disposable validation boundary used to prepare GoreeCloud Manager for a future private production deployment without creating that deployment.

The validation is deliberately narrower than production activation. It proves that the current Manager source can operate with a hardened container and the intended private Caddy/NetBird-style publication model. It does not claim that the final Infrastructure Services VM, production DNS, Caddy configuration, NetBird policy, firewall, monitoring, backup, or recovery environment has been inspected or approved.

## Security changes validated by this increment

Manager supports a file-backed Django secret through `DJANGO_SECRET_KEY_FILE`. `DJANGO_SECRET_KEY` remains available for isolated development, but the two sources are mutually exclusive. When `DJANGO_DEBUG=false`, Manager refuses to start with the repository's development placeholder secret.

The production-oriented Django settings also require secure session and CSRF cookies, trust the conventional `X-Forwarded-Proto: https` signal supplied by the controlled reverse proxy, keep session cookies HttpOnly with SameSite=Lax, use SameSite=Lax for CSRF cookies, deny framing, enable MIME-type sniffing protection, and use a same-origin referrer policy.

Static files are collected while the application image is built. A running Manager container therefore does not need to write into the application root merely to prepare WhiteNoise assets.

The source Compose definition now applies:

- a read-only root filesystem;
- a bounded `/tmp` tmpfs;
- `no-new-privileges`;
- `cap_drop: [ALL]`;
- a PID limit;
- a dedicated writable Manager data volume for SQLite;
- read-only delegated Kopia and Beszel artifact mounts;
- no Docker socket mount.

The existing loopback port in the normal Compose file remains a development/live-validation path. It is not the planned production publication mechanism.

## Disposable topology

`scripts/runtime_publication.compose.yml` creates four disposable services:

- `manager` — candidate GoreeCloud Manager image with all optional integrations disabled, file-backed synthetic Django secret, read-only root filesystem, SQLite named volume, and no host-published port;
- `caddy` — pinned Caddy image using an internal CA and the exact synthetic hostname `manager.goreecloud.com`;
- `approved-client` — synthetic private client with address `100.100.0.10`, inside the NetBird CGNAT range;
- `unapproved-client` — separate source at `172.30.245.10` outside the approved private range.

The Caddy fixture accepts only a source in `100.64.0.0/10` and returns HTTP 403 to other sources. Supplying a spoofed `X-Forwarded-For` header does not bypass that source-address decision.

The disposable client trusts the Caddy test CA rather than disabling certificate verification. The TLS test therefore verifies both certificate trust and the `manager.goreecloud.com` hostname.

## End-to-end assertions

`scripts/validate_runtime_publication_readiness.sh` performs the following sequence:

1. Generate runtime-random synthetic Django and administrative credentials in a private temporary directory.
2. Render the Compose model and reject host-published ports, network-membership drift, missing runtime hardening, or a direct Django secret value.
3. Build the exact candidate Manager image.
4. Prove `DJANGO_DEBUG=false` fails closed when neither approved secret source is configured.
5. Start Manager and apply the real Django migrations to the disposable SQLite volume.
6. Create a synthetic administrative user only inside that disposable database.
7. Start Caddy and the two isolated clients.
8. Verify CA-trusted TLS and the exact private hostname.
9. Verify `/healthz/` returns only the minimal Manager liveness payload.
10. Verify an unauthenticated Overview request redirects to `/login/`.
11. Verify the login page supplies CSRF protection and a Secure/SameSite CSRF cookie.
12. Perform a real Django login with the synthetic administrator and verify the session cookie is Secure, HttpOnly, and SameSite=Lax.
13. Verify the authenticated Overview renders successfully.
14. Verify the unapproved source receives HTTP 403 even when it spoofs an approved `X-Forwarded-For` value.
15. Verify the private client cannot resolve the internal Manager backend name directly.
16. Inspect the live Manager container and require the non-root `manager` user, read-only root filesystem, all capabilities dropped, `no-new-privileges`, no host port bindings, no Docker socket, read-only secret mounts, and a bounded writable persistent data path.
17. Remove and recreate the Manager container while preserving its SQLite volume, then perform the real login again to prove Manager-owned authentication state survives container replacement.
18. Search the rendered Compose model, container inspection data, runtime logs, and repository tree for the generated synthetic secret values.
19. Tear down containers, networks, volumes, and temporary credentials.

## What this evidence means

A green Runtime Publication Readiness workflow is strong source/disposable evidence that the current Manager release can operate using the intended runtime-security and private-publication pattern.

It also makes these properties regression-tested: future changes that reintroduce the development secret in production mode, require a writable application root, publish a Manager host port in the disposable topology, widen the private source boundary, weaken TLS/login/cookie behavior, add the Docker socket, or leak the synthetic credentials will fail the gate.

## What this evidence does not mean

This validation does **not**:

- create or approve a production Manager deployment;
- create `manager.goreecloud.com` in AdGuard Home or public DNS;
- modify the production Caddyfile;
- create or change NetBird groups, peers, or access policies;
- modify host nftables rules or port ownership;
- choose or install final production secret files, owners, groups, modes, or ACLs;
- prove the actual Infrastructure Services VM runtime user, Docker Engine version, Compose version, capacity, or mount state;
- register a real Uptime Kuma monitor or notification route;
- create a production Manager backup repository or schedule;
- prove production SQLite backup/restoration or full-environment disaster recovery;
- activate the production GoreeCloud Tasks integration or any other integration identity;
- authorize production use.

Those target-environment checks remain separate approval-controlled evidence.

## Rollback

The source changes are reversible through Git. The runtime hardening itself does not transform Manager application data. The disposable validation stack is removed after every run, including its named SQLite volume and generated secrets.
