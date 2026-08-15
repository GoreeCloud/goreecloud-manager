# GoreeCloud — Project Specification — Manager — Repository Implementation Companion

## Document Metadata

- Document Owner: LaDamian Goree
- Version: v0.1
- Status: Draft
- Created: August 11, 2026
- Last Updated: August 15, 2026
- Classification: Internal
- Document Type: Source-Controlled Software Project Specification Companion
- Project Name: GoreeCloud Manager
- Project Status: In Development — Source and Disposable Readiness Validation Established; Target-Environment Production Readiness Evidence Outstanding
- Repository: GoreeCloud/goreecloud-manager
- Development Model: Original GoreeCloud-owned software development
- Initial Deployment Model: Docker and Docker Compose
- Initial Production Placement: Not approved; development and validation first
- Long-Term Environment: GoreeCloud Infrastructure Services VM
- Planned Access Model: Private administrative web application
- Governing Project Record: `GoreeCloud — Project Specification — Manager` in Google Drive
- Record Role: Repository implementation companion for code-adjacent architecture, structure, tests, and release boundaries
- Authoritative Record: No — the Google Drive project specification is authoritative

## 1. Role

I will use GoreeCloud Manager as the central GoreeCloud management and operational console. It will provide a GoreeCloud-native control plane for understanding the platform as one environment while preserving the specialized responsibilities of Proxmox, Docker, NetBird, Caddy, AdGuard Home, Healthchecks, Uptime Kuma, Beszel, Kopia, ntfy, TrueNAS, GoreeCloud Tasks, and other approved systems.

Manager is an aggregation and context layer. It must not become an unnecessarily privileged replacement for the native interfaces, APIs, data stores, or recovery mechanisms owned by the systems it observes.

This repository document records the implementation state and code-adjacent contract. It must remain consistent with the governing Google Drive specification but must not become a second competing governance authority.

## 2. Purpose

I am building GoreeCloud Manager to reduce operational fragmentation. I administer GoreeCloud through multiple independent applications, inventories, APIs, dashboards, command-line tools, and documents. Manager will collect only the information required for its approved functions, normalize selected status information, and present it through one secure GoreeCloud-specific interface.

The v0.1 direction remains visibility before automation. I will continue to establish trustworthy read-only integrations, explicit authority boundaries, sanitized failure handling, recoverable deployment practices, and evidence-backed release controls before introducing write-capable administration.

## 3. Problem Being Solved

As GoreeCloud grows into a platform, I need one place to answer questions such as:

- What is healthy?
- What requires attention?
- Which systems are reachable?
- Which scheduled jobs are current?
- Which services are available?
- Which backups and protection signals are current?
- What system owns a particular capability?
- Which operational tasks are active?
- What supporting component does another service depend on?

Without a central application, answering these questions requires switching among multiple interfaces and manually correlating information. Manager reduces that fragmentation while keeping each integrated system authoritative for its own data and operations.

## 4. Intended Users

The initial user is me as GoreeCloud owner and administrator. Manager v0.1 is an administrative application and is not a family-facing service.

Future versions may support additional individually assigned administrative accounts or explicitly restricted read-only roles. Family-facing functionality will remain separate unless a future specification approves a limited view.

## 5. Current Implemented Foundation

The current v0.1 development line includes:

- Django authentication with database-backed, bounded server-side sessions.
- An authenticated Overview page and authenticated GoreeCloud Tasks page.
- Minimal public `/healthz/` liveness and database-aware `/readyz/` readiness endpoints that do not expose private platform state.
- A normalized read-only integration registry with bounded execution and fail-soft isolation.
- Loopback-only development/disposable publication through Docker Compose.
- SQLite-backed Manager-owned application state with bounded lock handling and documented PostgreSQL migration triggers.
- Gunicorn and WhiteNoise for containerized serving.
- Automated Django checks, tests, supply-chain checks, and permanent production-readiness evidence gates in GitHub Actions.
- Exact-revision workflow execution for pull-request and main-branch acceptance evidence.
- Hash-locked Python dependencies, deterministic Python SBOM evidence, and fail-closed OSV policy evaluation.
- Exact-built-image CycloneDX SBOM evidence and Debian-authoritative operating-system vulnerability policy evaluation.
- Glaze UI product identity, responsive shared navigation, local System/Light/Dark appearance selection, accessible focus and skip behavior, practical touch targets, reduced-motion/reduced-transparency support, increased-contrast and forced-colors fallbacks, and local-only browser presentation assets.
- Live read-only NetBird peer visibility.
- Live read-only Healthchecks scheduled-job visibility.
- Live read-only Uptime Kuma service-availability visibility through the protected metrics interface.
- Delegated read-only Kopia protection visibility through a sanitized host-produced status artifact.
- Delegated read-only Beszel host and container resource visibility through a sanitized host-produced status artifact.
- A read-only GoreeCloud Tasks adapter using the versioned `goreecloud.tasks.manager.v1` application API.

Docker inventory visibility and ntfy remain planned integration entries rather than active Manager adapters.

## 6. Explicitly Excluded From v0.1

The following remain outside the first release unless the governing project specification later changes the boundary:

- Starting, stopping, restarting, deleting, or modifying containers.
- Direct Proxmox administrative actions.
- Editing NetBird peers, groups, routes, policies, setup keys, or users.
- Editing DNS records, AdGuard Home configuration, Caddy routes, firewall rules, or open ports.
- Running backup restores or deleting backup snapshots.
- Executing arbitrary shell commands.
- Mounting `/var/run/docker.sock` into Manager.
- Storing SSH private keys or reusable infrastructure secrets in the Manager database.
- Family access, media access, surveillance access, or camera functionality.
- AI agents that autonomously modify production infrastructure.
- A plugin marketplace or third-party telemetry.
- Replacing the native administrative interfaces of integrated services.

## 7. Security Requirements

Manager is an administrative application. Authentication is required even when it is reached only through GoreeCloud private networking.

I require:

- individual accounts;
- least privilege;
- Django CSRF protection;
- secure cookies for production HTTPS deployment;
- bounded database-backed sessions;
- service-specific integration credentials;
- no reusable secrets committed to Git;
- file-backed long-lived secret support where implemented;
- no raw Docker socket;
- no unnecessary host filesystem access;
- no direct public backend exposure;
- sanitized integration and authentication event logging;
- explicit separation between Manager-owned state and authoritative infrastructure state.

Read-only identities are preferred. A service integration must not receive write permission merely because the upstream platform makes write APIs available.

### 7.1 Delegated Artifact Boundary

Kopia and Beszel use delegated collectors because their safest approved Manager path is not a broad direct credential inside the Manager container.

The collector credential and collection authority stay outside Manager. Manager mounts only the sanitized artifact path read-only. The artifact must contain only approved display fields and must not include passwords, tokens, authentication headers, agent keys, raw database content, container environment secrets, or other reusable credentials.

### 7.2 Tasks Boundary

Manager consumes the dedicated GoreeCloud Tasks Manager API and never reads the Tasks database directly.

Tasks remains authoritative for:

- task content;
- project membership;
- visibility and authorization;
- ownership;
- operational-work classification.

The intended production pattern uses a dedicated non-interactive Tasks identity, Viewer-only memberships on explicitly approved shared projects, and a protected file-backed bearer credential. Manager cannot select another Tasks identity or broaden its project scope.

### 7.3 Source and Build Evidence Boundary

Successful source/disposable gates prove only the conditions those gates actually exercise. They do not authorize production publication.

Accepted pull-request evidence must execute the exact immutable PR head. Build and supply-chain evidence must identify the tested source revision and, where applicable, the exact built image. Exceptions to vulnerability policy must remain explicit, source-controlled, narrowly scoped, reasoned, and expiring.

## 8. Privacy Requirements

Manager will collect and display only information needed for approved administrative visibility.

It will not include advertising, analytics, behavioral tracking, external telemetry, or unnecessary third-party browser scripts. Logs must avoid passwords, API tokens, private keys, complete authentication headers, session identifiers, and unnecessary personal information.

The Glaze UI appearance preference is browser-local state only. It is not sent to Manager or an integration and is not used for tracking. Browser presentation assets remain local to Manager; remote fonts, scripts, stylesheets, analytics packages, and externally hosted branding are not part of the v0.1 UI contract.

## 9. Data Requirements

Manager-owned data may include:

- application users;
- Django session and authentication state;
- Manager configuration appropriate for database storage;
- normalized local metadata genuinely owned by Manager.

Live infrastructure facts must remain authoritative in their originating systems. Manager may query or temporarily normalize selected status, but it must not silently become the authoritative database for NetBird peers, Uptime Kuma monitors, Healthchecks jobs, Beszel resource history, Kopia snapshots, Docker containers, DNS records, or Tasks content.

SQLite remains approved for development and the initial MVP because Manager is a low-write single-instance administrative application. The current implementation uses bounded busy-wait handling, short-lived connections, and no request-wide database transactions. I will plan migration to PostgreSQL when recurring normal-use contention, ordinary concurrent writers, write-heavy/background database work, authentication/session pressure, or other operational evidence shows that SQLite is no longer appropriate.

## 10. Integration Requirements

Each adapter must define:

- role and purpose;
- configuration requirements;
- credential/permission boundary;
- timeout behavior;
- malformed-response behavior;
- authentication-failure behavior;
- unavailable-service behavior;
- normalized fields returned to the UI;
- logging and secret-minimization requirements.

Current integration state:

### NetBird

Implemented read-only peer/private-network visibility through the approved read-only API boundary.

### Healthchecks

Implemented read-only scheduled-job monitoring. Healthchecks signals do not replace the authoritative state of the underlying job or backup system.

### Uptime Kuma

Implemented read-only availability visibility through the protected metrics endpoint. Manager does not receive the Uptime Kuma administrator password or write-capable management authority.

### Beszel

Implemented through the delegated host-side collector and sanitized artifact boundary. Manager receives only the approved read-only artifact rather than Beszel credentials or Docker-socket authority.

### Kopia

Implemented through a delegated host-side collector and sanitized read-only artifact. Manager does not receive repository credentials, SFTP keys, restore/delete authority, or the Docker socket.

### GoreeCloud Tasks

Implemented as a read-only application-to-application integration. Repository-local tests and disposable cross-application/final-topology gates validate schema handling, authorization, data minimization, invalid credentials, membership revocation/restoration, database isolation, file-backed synthetic credential behavior, and fail-soft conditions. Actual production identity, credential, network, publication, monitoring, and activation remain separate approval-controlled work.

### Docker

Planned. Direct Docker socket access is prohibited. Live Docker inventory visibility requires a separately approved least-privilege delegated source.

### ntfy

Planned. Any future notification integration must define whether Manager is only observing notification state or is permitted to publish a narrowly scoped administrative notification.

Proxmox, TrueNAS, AdGuard Home, Caddy, DNS inventories, GoreeCloud documentation, dependency mapping, security findings, and AI capabilities remain future integrations or modules unless separately implemented and validated.

## 11. User Interface and Glaze UI Requirements

Manager uses GoreeCloud Glaze UI as its complete visual and interaction language while remaining an operational console first.

The interface must provide:

- clear information hierarchy;
- consistent GoreeCloud identity, typography, spacing, and geometry;
- rounded layered surfaces and restrained translucency;
- semantic status colors with textual state labels so color is not the sole signal;
- high-quality System, Light, and Dark appearance behavior;
- responsive desktop, tablet, and mobile layouts;
- keyboard-accessible navigation;
- a skip link and programmatically focusable main target;
- visible focus indicators;
- practical minimum 44-pixel interactive targets;
- reduced-motion and reduced-transparency behavior where supported;
- increased-contrast behavior where requested;
- forced-colors/High Contrast operability;
- solid-surface fallbacks where backdrop filtering is unavailable;
- clear authentication error, empty, degraded, and unavailable states;
- local-only browser presentation dependencies.

The shared shell owns product identity and browser metadata. Primary surfaces inherit that shell instead of recreating navigation, theming, or identity independently.

Visual design must not obscure operational information or weaken accessibility. Manager should complement terminal administration and specialized service interfaces rather than reproduce every possible command or control as a button.

Source-level conformance is automated, but final production visual approval still requires representative authenticated browser review across supported widths, appearance modes, keyboard interaction, and relevant accessibility modes.

## 12. Technology Stack

The v0.1 implementation intentionally remains conservative:

- Python 3.14.
- Django 5.2 LTS.
- Django server-rendered templates.
- Plain CSS and minimal vanilla JavaScript; no frontend framework in v0.1.
- SQLite for development and initial MVP state.
- Gunicorn.
- WhiteNoise.
- Docker and Docker Compose.
- GitHub Actions.
- Django's built-in test framework.

This keeps authentication, sessions, CSRF protection, templates, database migrations, configuration, and application logic inside one understandable codebase while requirements are still evolving.

## 13. Deployment Environment

Development may occur on an administrative workstation and in isolated Docker environments. Development data, secrets, and credentials must remain separate from production.

Disposable publication/readiness validation does not approve a production deployment. Production placement remains explicitly unapproved until the governing target-environment evidence requirements are satisfied.

Before production publication I must validate the target environment, including:

- final private DNS and Caddy publication;
- authorized private-network reachability;
- secure cookie behavior over HTTPS;
- production secret management;
- target backup coverage and tested restoration;
- deployed container identity/security;
- target monitoring and alert delivery;
- target rollback and upgrade procedures;
- selected production integration identities and network paths;
- final authenticated Glaze UI visual/accessibility review.

The long-term placement remains the GoreeCloud Infrastructure Services VM because Manager is an administrative/infrastructure application rather than a family service.

## 14. Backup and Recovery Requirements

Before Manager becomes a critical production dependency I will protect:

- source code and release history;
- non-reproducible application configuration;
- SQLite or future database state;
- required Manager persistent data;
- deployment files;
- documentation;
- secret recovery references without placing reusable secrets into inappropriate ordinary backups.

GitHub is source control, not the complete backup strategy.

Recovery must be demonstrably possible by rebuilding the application, restoring required configuration and persistent data, recreating secrets through the approved process, applying migrations, and validating authentication, `/healthz/`, `/readyz/`, and approved read-only integrations.

Manager must never become the only location containing information required to recover GoreeCloud.

## 15. Repository Structure

The repository uses the following primary structure:

```text
goreecloud-manager/
├── goreecloud_manager/        # Django project configuration
├── core/                      # Shared application shell, views, middleware, and UI assets
│   ├── static/core/css/       # Manager components and Glaze UI conformance layers
│   ├── static/core/img/       # GoreeCloud-controlled local presentation assets
│   ├── static/core/js/        # Minimal browser-local interaction logic
│   └── templates/core/        # Shared shell and primary application surfaces
├── integrations/              # Read-only service adapter framework
├── ops/                       # Delegated collector and operational helpers
├── scripts/                   # Disposable readiness and evidence tooling
├── security/                  # Source-controlled vulnerability policy
├── tests/                     # Application, integration, security, and UI contract tests
├── docs/                      # Architecture and operational documentation
├── .github/workflows/         # Permanent exact-revision validation gates
├── .env.example               # Non-secret configuration template
├── compose.yml
├── Dockerfile
├── LICENSE
├── manage.py
├── requirements.lock
├── requirements.txt
└── README.md
```

The repository must remain understandable without depending on my memory. Cross-cutting rules belong in clearly named modules/files instead of being duplicated across templates or components.

## 16. Testing Requirements

The test and CI baseline verifies, as applicable:

- dependency consistency with `pip check`;
- browser JavaScript syntax;
- static-file collection;
- Django system and deployment checks;
- public minimal liveness/readiness endpoint behavior;
- authentication and session requirements;
- authenticated Overview and Tasks rendering;
- integration-registry states;
- adapter-specific success and fail-soft paths;
- authentication failures;
- malformed/unsupported upstream data;
- stale artifact handling;
- no reusable secret leakage in normalized output;
- Glaze UI shared-shell identity and navigation;
- local-only browser presentation dependencies;
- pre-stylesheet local appearance initialization;
- skip-link/main-target semantics;
- reduced-motion, reduced-transparency, increased-contrast, forced-colors, and no-backdrop-filter source fallbacks;
- Python dependency/SBOM/vulnerability evidence;
- exact-built-image SBOM and operating-system vulnerability evidence;
- exact-revision execution of permanent readiness workflows.

Cross-application Tasks validation additionally exercises the real Manager adapter/UI against disposable Tasks environments without provisioning production credentials or production infrastructure.

Passing source/disposable checks is evidence for the tested contracts, not evidence that the target production environment exists or has been approved.

## 17. Release Model

The initial development line is `0.1.x`.

- `0.1.0` will represent the first complete MVP after required source, disposable, target-environment, and visual release-readiness gates are satisfied.
- Patch releases will contain compatible fixes and small improvements.
- Minor releases may add integrations or significant functionality while the application remains pre-1.0.
- `1.0.0` will not be used until the architecture, security model, upgrade process, backup process, recovery process, operational role, and user-interface contract are stable enough for long-term production administration.

The default branch represents accepted repository state. Material changes should normally be developed on separate branches and reviewed through pull requests with exact-head validation before merge.

## 18. Maintenance Responsibilities

I am responsible for approving Manager's architecture, dependencies, integrations, permissions, releases, and production deployment.

Ongoing maintenance includes:

- dependency and security update review;
- container-image review;
- authentication and authorization review;
- integration compatibility review;
- test maintenance;
- backup and restore validation;
- documentation synchronization;
- Glaze UI identity, accessibility, responsive, and browser-behavior review;
- removal of obsolete functionality.

AI-assisted code is subject to the same review and validation requirements as manually written code.

## 19. Retirement and Data Export

Manager must remain replaceable.

If I retire or rewrite Manager, I must be able to export or reconstruct the information Manager itself owns using documented, non-proprietary formats where practical.

Retiring Manager must not impair the independent operation of Proxmox, Docker, NetBird, Caddy, AdGuard Home, Healthchecks, Uptime Kuma, Beszel, Kopia, ntfy, TrueNAS, GoreeCloud Tasks, or other integrated systems.

## 20. Readiness Model

### Foundation and Read-Only Visibility — Established

The application foundation, authentication, shared Glaze UI shell, liveness/readiness endpoints, read-only integration architecture, and core operational visibility are implemented in source.

### Source and Disposable Validation — Established and Continuing

Permanent GitHub gates validate application tests, runtime/publication patterns, backup/restore patterns, upgrade/rollback patterns, monitoring/alert patterns, production-readiness manifest integrity, exact source revision, and supply-chain evidence without provisioning production infrastructure.

Material changes must preserve these controls on their exact PR head before merge.

### Target-Environment Production Readiness — Not Complete

The governing project record maintains the authoritative target-environment evidence categories. Source/disposable success must not be converted into a production-readiness claim.

Production deployment, publication, identities, credentials, monitoring registration, backup repository, alert routing, network controls, and activation remain separate approval-controlled work.

## 21. Governing Principle

I will build GoreeCloud Manager as the interface that helps me understand GoreeCloud as one platform without turning Manager into an unnecessary single point of failure or an over-privileged replacement for the specialized systems it integrates.

I will treat Glaze UI, privacy, accessibility, documentation, source integrity, recovery, and production-readiness evidence as parts of application quality rather than optional finishing work.
