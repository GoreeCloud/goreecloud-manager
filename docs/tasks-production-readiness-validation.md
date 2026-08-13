# GoreeCloud Manager — Tasks Production-Readiness Validation Plan

## Purpose

I use this document to define GoreeCloud Manager's responsibilities in the production-readiness validation of the read-only GoreeCloud Tasks integration.

The shared and Tasks-authoritative validation plan is maintained in GoreeCloud Tasks at:

[`GoreeCloud Tasks — Manager Production-Readiness Validation Plan`](https://github.com/GoreeCloud/goreecloud-tasks/blob/main/docs/manager-production-readiness-validation.md)

This Manager document narrows that shared plan to Manager-owned configuration, network membership, secret consumption, fail-soft behavior, monitoring, recovery, rollback, and validation evidence.

This document does not create a production Tasks identity, bearer token, Vaultwarden item, secret file, Docker network, DNS/Caddy/NetBird configuration, monitoring check, or production deployment.

## Manager Role

Manager is the read-only consumer of the Tasks Manager API. It does not own:

- Tasks task content;
- Tasks project membership;
- the `goreecloud-manager-integration` identity lifecycle;
- project authorization decisions;
- the Tasks database;
- task write operations; or
- the source of truth for which Tasks projects Manager may observe.

Tasks remains authoritative for those controls.

Manager owns only its integration configuration, its protected credential mount as a consumer, its network membership, its adapter behavior, its user-interface presentation, its fail-soft operational state, and the data-minimized monitoring signal derived from that adapter state.

## Preferred Same-VM Network Design

When Tasks and Manager run on the same GoreeCloud Infrastructure Services VM, Manager should reach Tasks through a dedicated cross-stack Docker network named:

```text
manager-tasks
```

The Tasks web service should expose a stable alias on that network such as:

```text
goreecloud-tasks
```

The intended Manager base URL is therefore:

```text
TASKS_API_URL=http://goreecloud-tasks:8000
```

The HTTP transport is acceptable only because it remains inside the approved same-host Docker network. The bearer token and Tasks authorization remain required.

Manager must not join the Tasks PostgreSQL/backend network. It must not obtain direct database reachability merely because the applications share a VM.

## Manager Network Membership

The final Manager deployment may continue to use other approved networks for other read-only integrations, but `manager-tasks` must remain a purpose-specific dependency.

Manager must not receive unnecessary access to:

- the Tasks database network;
- Tasks persistent storage;
- Tasks Docker volumes;
- Tasks administrative shell interfaces;
- unrelated application networks; or
- Caddy's proxy network merely to call the Tasks API when the dedicated direct service path is available.

The production network inventory must document `manager-tasks` if and when it is actually created.

## No Backend Publication for Manager

Manager does not require a direct public host port to consume Tasks.

The production target is:

- Manager backend not directly publicly exposed;
- Tasks backend not directly publicly exposed;
- Caddy remains the controlled HTTPS gateway for approved user-facing private web access;
- Manager's Tasks request uses the dedicated inter-service network; and
- the internal API path remains independent from a public wildcard or public backend route.

Development-only loopback bindings do not constitute production publication approval.

## Protected Token Consumption

Manager's production configuration should use:

```text
TASKS_ENABLED=true
TASKS_API_URL=http://goreecloud-tasks:8000
TASKS_ACCESS_TOKEN_FILE=/run/secrets/goreecloud_tasks_manager_api_token
TASKS_TIMEOUT_SECONDS=5
```

The direct `TASKS_ACCESS_TOKEN` variable must remain empty in long-lived production when the file-backed mechanism is available.

The active token value must not be stored in the Manager repository, SQLite database, ordinary `.env` documentation, logs, screenshots, issues, pull requests, or change logs.

The Tasks-side identity and credential lifecycle remains authoritative for token generation, Vaultwarden recovery material, rotation, revocation, and retirement.

## Secret-Mount Acceptance

Before Manager is enabled against production Tasks, I must prove without printing the token that:

- the expected secret file exists inside the Manager container;
- the Manager runtime user can read it;
- the mount is read-only;
- the direct token variable is empty;
- the token is absent from `docker inspect` environment output;
- the token is absent from image layers and source control;
- unrelated Manager integrations do not gain the same mount unless separately required; and
- the file can be replaced through the approved rotation procedure without broadening host permissions.

The final host owner, group, mode, and any supplementary GID must be selected from the actual target runtime and recorded without the secret value.

## Adapter Acceptance

The real `integrations/tasks.py` adapter must be used for production-representative validation.

A healthy result must prove that Manager:

- reads the file-backed token successfully;
- reaches the expected Tasks base URL;
- receives the supported `goreecloud.tasks.manager.v1` schema version 1;
- normalizes only approved operational fields;
- reports the configured Tasks identity;
- returns only authorization-scoped operational work;
- does not persist copied Tasks records as a second source of truth; and
- continues to render `/tasks/` through the authenticated Manager interface.

## Fail-Soft Acceptance

Manager must continue to fail soft when the integration is unavailable.

Production-representative tests must cover:

- `TASKS_ENABLED=false`;
- unreadable or missing secret file;
- empty secret file;
- invalid bearer token;
- Tasks timeout;
- Tasks network failure;
- HTTP 401;
- HTTP 403;
- HTTP 404;
- unsupported schema/version;
- malformed response; and
- temporary Tasks restart or unavailability.

None of these conditions should break Manager's minimal health endpoint or unrelated integrations.

Manager must not render raw upstream response bodies, Authorization headers, or bearer-token values while reporting failures.

## Authorization Boundary Acceptance

Manager must display only what Tasks authorizes for the configured service identity.

The shared production test must prove that:

- an approved operational task appears;
- an unauthorized Shared project remains absent;
- a Private project remains absent;
- personal tasks remain absent;
- non-operational project tasks remain absent;
- completed/cancelled tasks remain absent under the current contract;
- descriptions remain absent;
- comments remain absent;
- labels remain absent;
- user account details remain absent;
- reminder/notification state remains absent; and
- Viewer membership revocation removes the affected project from the next Manager request without changing the token.

Manager must not provide a control that selects another Tasks principal or bypasses that membership state.

## Read-Only Acceptance

The production integration remains accepted only while the Manager-side contract is read-only.

Manager must not gain a Tasks API path that creates, edits, completes, reopens, deletes, comments on, reassigns, or changes membership for Tasks records without a separate design and authorization review.

No Manager administrative role may be interpreted as permission to browse Tasks private user content.

## Monitoring Responsibilities

Manager's minimal `/healthz/` endpoint intentionally does not fail when an optional integration is unavailable. Therefore `/healthz/` alone does not monitor the Tasks integration.

Manager now implements the separate integration-specific signal:

```text
GET /healthz/integrations/tasks/
```

The endpoint exercises the real `integrations.tasks.tasks_snapshot()` adapter and returns only a sanitized Manager service label, integration label, broad adapter state, and monitoring condition. It does not return task titles, counts, project names, Tasks usernames, token values, secret paths, upstream response bodies, or adapter detail text.

The monitoring condition distinguishes at least:

- `healthy`;
- `disabled`;
- `misconfigured`;
- `unreachable`;
- `authentication-rejected`;
- `authorization-denied`; and
- `schema-invalid`.

It additionally distinguishes `endpoint-unavailable` and `upstream-error` when the HTTP failure can be categorized more precisely.

A healthy condition returns HTTP 200. Every non-healthy integration-specific condition returns HTTP 503 so an approved HTTP monitor can alert on the integration without changing Manager's generic liveness semantics. Responses are GET-only and use `Cache-Control: no-store`.

Repository tests must prove that monitoring responses do not include bearer-token values, private task content, task counts, configured Tasks identities, or adapter detail text. The Tasks disposable final-topology gate should exercise the endpoint against the real cross-application adapter before production preflight.

The endpoint implementation does not itself create an Uptime Kuma monitor, Healthchecks check, ntfy subscription, notification route, or production publication. Those remain separately approval-controlled target-runtime work. Any alert forwarded through Healthchecks, ntfy, or another approved monitor must continue to exclude the bearer token and private task content.

## Logging Review

Before production acceptance I must inspect recent Manager logs and confirm:

- no bearer token appears;
- no Authorization header appears;
- no raw upstream sensitive response is rendered;
- no private task description/comment marker appears;
- no unexplained repeated authentication failure remains;
- no unexplained repeated network failure remains; and
- failure details remain useful but sanitized.

## Backup and Recovery

The Manager production backup/recovery plan must include the configuration needed to reconstruct the Tasks integration without placing the reusable token in ordinary documentation.

Recovery must be able to restore or reconstruct:

- Manager source/release revision;
- Manager persistent database/state;
- non-secret Tasks integration configuration;
- the documented `manager-tasks` network dependency;
- the secret file path and mount definition;
- the protected credential through the approved Tasks/Vaultwarden recovery path;
- monitoring configuration; and
- the Manager UI/integration behavior after restoration.

The recovered credential must not silently reactivate a previously retired integration. The authoritative Tasks lifecycle procedure decides whether the old token may be restored or a new token must be generated.

## Rollback

Manager's first rollback control is:

```text
TASKS_ENABLED=false
```

This stops Manager from making Tasks requests without changing Tasks data.

If a network problem is caused by the new cross-stack dependency, Manager should be disabled before its `manager-tasks` attachment is removed.

If a credential problem is suspected, Manager should stop presenting the credential immediately and the Tasks-side credential lifecycle should rotate or revoke the token.

If an authorization problem is observed, Manager must be disabled while Tasks project membership and identity state are reviewed.

Manager production rollback must not require deleting Tasks content or changing another user's private records.

## Upgrade Compatibility

The selected production Manager revision must remain compatible with the selected Tasks revision.

Before an upgrade I must verify:

- the expected Tasks schema/version;
- the Manager adapter regression tests;
- the disposable cross-application gate against the selected revisions;
- final Docker network compatibility;
- final secret-file compatibility;
- no expansion of displayed private fields;
- fail-soft behavior against unsupported schema;
- the integration-specific monitoring condition remains accurate and data-minimized; and
- a known-good Manager rollback revision.

## Evidence Manager Must Contribute

The production validation record should include Manager-specific evidence for:

```text
Manager deployed revision
Manager image reference/digest
Manager target host/VM
Manager public host port present: Yes/No
manager-tasks membership
Tasks API URL
secret container path
secret mount read-only: Yes/No
Manager runtime user/group evidence
Manager secret read test: Pass/Fail
TASKS_ACCESS_TOKEN direct variable empty: Yes/No
real adapter healthy test: Pass/Fail
invalid-token test: Pass/Fail
Tasks-unavailable fail-soft test: Pass/Fail
schema-rejection test: Pass/Fail
membership-revocation visibility test: Pass/Fail
Manager /tasks/ authenticated UI test: Pass/Fail
Manager logs reviewed: Yes/No
integration-specific monitoring endpoint test: Pass/Fail
external monitor registration and alert-delivery test: Pass/Fail
rollback test with TASKS_ENABLED=false: Pass/Fail
recovery test reference
responsible administrator
validation date/time
```

No active credential value belongs in the evidence record.

## Go/No-Go Rule

Manager-side production activation is **GO** only when its network, file-backed secret consumption, read-only adapter, authorization behavior, fail-soft behavior, monitoring, logging, recovery, and rollback evidence all pass together with the shared Tasks-side requirements.

It is **NO-GO** if Manager requires broader Tasks access, direct database access, a public backend port, a broadly readable secret, undocumented Docker network membership, or a production state that cannot be safely disabled and reconstructed.

## Relationship to Existing CI

The existing Tasks-maintained `manager-cross-app` CI job exercises the actual Manager adapter and authenticated Manager Tasks page against a disposable Tasks API. The newer `manager-final-topology` job reproduces the planned same-VM application network and file-backed secret pattern with synthetic data and credentials.

The integration-specific monitoring endpoint is implemented in Manager and must be exercised by the Tasks final-topology gate against the selected Manager revision. Together these tests remain compatibility evidence only; they do not prove the final target-host owner/group/GID, user-facing private publication, external production monitor registration/alert delivery, or production-representative recovery.

## Governing Principle

I will keep GoreeCloud Manager useful without making it a privileged shortcut around GoreeCloud Tasks. Production readiness means Manager can reliably read only the operational work explicitly authorized to its service identity, through a private and recoverable path, while remaining easy to disable when any authorization, secret, network, monitoring, or compatibility boundary is uncertain.
