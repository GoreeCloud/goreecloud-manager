# GoreeCloud — Project Specification — Manager

## Document Metadata

- Document Owner: LaDamian Goree
- Version: v0.1
- Status: Draft
- Created: August 11, 2026
- Classification: Internal
- Document Type: Software Project Specification and Implementation Blueprint
- Project Name: GoreeCloud Manager
- Project Status: Initiated — Initial Implementation
- Planned Repository: GoreeCloud/goreecloud-manager
- Development Model: Original GoreeCloud-owned software development
- Initial Deployment Model: Docker and Docker Compose
- Initial Production Placement: Not approved; development and validation first
- Long-Term Environment: GoreeCloud Infrastructure Services VM
- Planned Access Model: Private administrative web application
- Authoritative Record: Yes

## 1. Role

I will use GoreeCloud Manager as the central GoreeCloud management and operational console. It will provide a GoreeCloud-native control plane for understanding the platform as one environment while preserving the specialized responsibilities of Proxmox, Docker, NetBird, Caddy, AdGuard Home, Healthchecks, Uptime Kuma, Beszel, Kopia, ntfy, TrueNAS, and other approved systems.

## 2. Purpose

I am building GoreeCloud Manager to reduce operational fragmentation. I currently administer GoreeCloud through multiple independent applications, inventories, APIs, dashboards, command-line tools, and documents. Manager will collect only the information required for its approved functions, normalize selected status information, and present it through one secure GoreeCloud-specific interface.

The initial purpose is visibility rather than automation. I will establish a trustworthy read-only foundation before adding administrative actions.

## 3. Problem Being Solved

GoreeCloud is becoming a platform rather than a single server or application. As the environment grows, I need one place to answer questions such as: What is healthy? What requires attention? Which systems are reachable? Which backups are current? Which peers and services are active? Which component owns a capability? What supporting service does another component depend on?

Without a central application, understanding the platform requires switching among multiple interfaces and manually correlating information. Manager will reduce that fragmentation without creating a second competing management authority for the underlying systems.

## 4. Intended Users

The initial user is me as GoreeCloud owner and administrator. The v0.1 application is administrative and is not a family-facing service.

Future versions may support additional individually assigned administrative accounts or restricted read-only roles. Family-facing functionality will remain separate unless a future specification explicitly approves a limited view.

## 5. v0.1 Required Features

The first usable release will include:

- Secure application login using Django's built-in authentication and session framework.
- An authenticated Overview page.
- A platform identity panel identifying the application as GoreeCloud Manager.
- A normalized integration registry that reports whether each supported integration is configured, disabled, unavailable, or healthy.
- Read-only integration architecture with no write-capable service credentials required by default.
- Initial adapter framework for NetBird, Healthchecks, Docker visibility through an approved delegated source, Uptime Kuma, Beszel, Kopia, and ntfy.
- A health endpoint for container and monitoring validation.
- Environment-based configuration with a committed `.env.example` but no live secrets.
- Dockerfile and Docker Compose deployment artifacts.
- Automated Django system checks and test execution in CI.
- Basic responsive interface suitable for desktop and mobile administration.
- Documentation covering role, purpose, architecture, development, deployment boundaries, configuration, security, backup, recovery, and retirement.

The scaffold may expose placeholder integration states before live credentials are configured. A placeholder state must be visibly distinguished from verified live data.

## 6. Explicitly Excluded From v0.1

The following are out of scope for the first release:

- Starting, stopping, restarting, deleting, or modifying containers.
- Direct Proxmox administrative actions.
- Editing NetBird peers, groups, routes, policies, setup keys, or users.
- Editing DNS records, AdGuard Home configuration, Caddy routes, firewall rules, or open ports.
- Running backup restores or deleting backup snapshots.
- Executing arbitrary shell commands.
- Mounting the Docker socket directly into the Manager container.
- Storing SSH private keys or reusable infrastructure secrets in the Manager database.
- Family access, media access, surveillance access, or camera functionality.
- AI agents that autonomously modify production infrastructure.
- A plugin marketplace or third-party telemetry.
- Replacing the native administrative interfaces of integrated services.

## 7. Security Requirements

Manager will be treated as an administrative application. I will require authentication even when it is reachable only through GoreeCloud private networking. I will use individual accounts, least privilege, secure sessions, CSRF protection, secure cookies in production, and service-specific credentials.

Read-only service identities will be preferred. A service integration will not receive write permission merely because an upstream API offers it. Reusable secrets will be supplied through environment-specific secret handling and will never be committed to the repository.

Manager v0.1 will not mount `/var/run/docker.sock`. Direct Docker socket access would give the application excessive host authority. Docker visibility must instead use an approved delegated interface or a purpose-built least-privilege collection method before it becomes a live production integration.

Production publication must follow the GoreeCloud private web service model: stable HTTPS through Caddy, private DNS through the approved DNS path, and reachability limited to authorized private-network clients. No Manager backend port will be intentionally exposed directly to the public Internet.

## 8. Privacy Requirements

Manager will collect only information needed to administer GoreeCloud. It will not include advertising, analytics, behavioral tracking, external telemetry, or unnecessary third-party scripts.

Logs will avoid passwords, API tokens, private keys, full authentication headers, session identifiers, and unnecessary personal information. Integration responses will be normalized so that the user interface receives only fields required for the feature being displayed.

## 9. Data Requirements

The v0.1 database will store application users, Django session/authentication data, Manager configuration state that is appropriate for database storage, and normalized local metadata required by Manager itself.

Live infrastructure facts should remain source-of-truth data in their authoritative systems. Manager will initially query or cache selected read-only status rather than becoming the authoritative database for NetBird peers, Docker containers, backup snapshots, DNS records, or monitoring checks.

SQLite is approved for development and the initial MVP because the application begins as a single-instance administrative service with low write volume. I may migrate to PostgreSQL when concurrency, durability, reporting, background jobs, clustering, or operational evidence demonstrates that SQLite is no longer appropriate.

## 10. Integration Requirements

The integration layer will use explicit adapters with a common health/status contract. Each adapter must declare its role, configuration requirements, permissions, timeout behavior, failure behavior, and data fields returned to Manager.

Initial integration targets are:

- NetBird — peer and private-network visibility using read-only API credentials.
- Healthchecks — check and scheduled-job status.
- Docker — container visibility only through a separately approved least-privilege source.
- Uptime Kuma — monitor status where a supported integration method is available.
- Beszel — host and system health where a supported integration method is available.
- Kopia — backup and snapshot status without restore or deletion capability.
- ntfy — notification status and later controlled Manager-generated administrative notifications.

Proxmox, TrueNAS, AdGuard Home, Caddy, DNS inventories, GoreeCloud documentation, tasks, dependency mapping, security findings, and AI capabilities are future integrations or modules and are not required to make the first scaffold usable.

## 11. Technology Stack

The initial implementation stack is deliberately conservative:

- Python 3.14.
- Django 5.2 LTS.
- Django server-rendered templates for the user interface.
- Plain CSS and minimal vanilla JavaScript; no frontend framework in v0.1.
- SQLite for development and initial MVP state.
- Gunicorn for containerized WSGI serving.
- WhiteNoise for self-contained static-file serving in the application container.
- Docker and Docker Compose for reproducible deployment.
- GitHub Actions for automated checks.
- Django's built-in test framework for initial automated tests.

I am choosing Django 5.2 rather than a pre-release or non-LTS framework line because it provides built-in authentication, sessions, CSRF protection, ORM, migrations, templates, and a long-term support window while reducing the number of separate components I must maintain.

## 12. Deployment Environment

Development may occur on my administrative workstation and in isolated Docker environments. Development data, secrets, and credentials must remain separate from production.

The first production deployment is not approved by this specification alone. Before production, I must validate authentication, secret handling, private service publication, backup coverage, restore procedures, container security, monitoring, and the selected live integrations.

The long-term placement is the GoreeCloud Infrastructure Services VM because Manager is an administrative and infrastructure application rather than a family service.

## 13. Backup Requirements

Before production use, I will protect:

- Source code and release history.
- Application configuration that is not reproducible from source.
- SQLite database or future database state.
- Required persistent Manager data.
- Deployment files.
- Documentation.
- Secret recovery references without storing reusable secrets in ordinary backups that are not approved for them.

GitHub is a source-control location, not the complete backup strategy.

## 14. Recovery Requirements

A documented recovery procedure must be validated before Manager becomes a critical production dependency. Recovery must be possible by rebuilding the container image, restoring required configuration and persistent data, recreating secrets through the approved secret-recovery process, running database migrations, and validating login, health checks, and read-only integrations.

Manager must never become the only location containing information required to recover GoreeCloud.

## 15. Repository Structure

The initial repository structure is:

```text
goreecloud-manager/
├── goreecloud_manager/        # Django project configuration
├── core/                      # Core UI, health, and application views
├── integrations/              # Service adapter framework
├── tests/                     # Cross-application tests
├── docs/                      # Architecture and operational documentation
├── .github/workflows/         # CI workflows
├── .env.example               # Non-secret configuration template
├── .gitignore
├── compose.yml
├── Dockerfile
├── LICENSE
├── manage.py
├── requirements.txt
└── README.md
```

The repository must remain understandable without depending on my memory.

## 16. Testing Requirements

The initial test suite will verify:

- Django configuration passes system checks.
- The health endpoint responds without authentication.
- The Overview page requires authentication.
- An authenticated administrator can load the Overview page.
- Integration registry states are rendered without exposing secrets.
- Environment parsing behaves predictably.

Future integration adapters must add adapter-specific success, timeout, malformed-response, authentication-failure, and unavailable-service tests before production activation.

## 17. Release Model

The initial development line is `0.1.x`.

- `0.1.0` will represent the first complete MVP release after live validation.
- Patch releases will contain compatible fixes and small improvements.
- Minor releases may add integrations or significant functionality while the application remains pre-1.0.
- `1.0.0` will not be used until the core architecture, security model, upgrade process, backup process, recovery process, and operational role are stable enough to support long-term production administration.

The default branch will represent accepted project state. Material changes should normally be developed on separate branches and reviewed through pull requests.

## 18. Maintenance Responsibilities

I am responsible for approving Manager's architecture, dependencies, integrations, permissions, releases, and production deployment. Ongoing maintenance includes dependency review, security updates, container-image review, authentication and authorization review, test maintenance, backup validation, documentation updates, integration compatibility review, and removal of obsolete functionality.

AI-assisted code remains subject to the same review and validation requirements as manually written code.

## 19. Retirement and Data Export

Manager must remain replaceable. If I retire or rewrite it, I must be able to export or reconstruct the information that Manager itself owns using documented, non-proprietary formats where practical.

Retiring Manager must not impair the independent operation of Proxmox, Docker, NetBird, Caddy, AdGuard Home, Healthchecks, Uptime Kuma, Beszel, Kopia, ntfy, TrueNAS, or other integrated systems. Integrated systems remain authoritative for their own data and operations.

## 20. MVP Acceptance Criteria

I will consider the v0.1 foundation ready for MVP integration work when:

1. The repository contains the documented scaffold and open-source license.
2. The application builds and starts in an isolated environment.
3. The health endpoint passes.
4. Authentication protects the administrative interface.
5. The Overview page renders the integration registry.
6. No reusable credentials are committed.
7. No direct public service exposure is required.
8. No Docker socket is mounted into the Manager container.
9. Automated tests pass.
10. The project documentation clearly distinguishes implemented features from planned integrations.

## 21. Initial Implementation Decision

I approve GoreeCloud Manager to begin as a small Django monolith rather than a distributed frontend/backend architecture. This keeps authentication, templates, database migrations, configuration, and application logic inside one maintainable codebase while the product requirements are still developing.

I may split the application into separate services later if measured requirements justify that complexity. The architecture is not permanent; the GoreeCloud data, security, ownership, recoverability, and administrative outcomes are more important than preserving a framework choice.

## 22. Initial Development Milestones

### Milestone 1 — Foundation

Create the repository, Django project, core application, login flow, Overview page, health endpoint, Docker artifacts, tests, CI, and project documentation.

### Milestone 2 — First Live Integration

Implement the first read-only live adapter using a service-specific least-privilege credential. NetBird is the preferred first candidate because GoreeCloud already maintains an Auditor service identity for monitoring and API-derived inventory.

### Milestone 3 — Monitoring and Protection Visibility

Add approved read-only monitoring and backup adapters, normalize their states, and establish warning/error presentation.

### Milestone 4 — Production Readiness

Validate private publication, secure cookies, secret management, monitoring, backup, restoration, rollback, update procedures, and production container hardening before declaring Manager production-ready.

## 23. Governing Principle

I will build GoreeCloud Manager as the interface that helps me understand GoreeCloud as one platform without turning Manager into an unnecessary single point of failure or an over-privileged replacement for the specialized systems it integrates.
