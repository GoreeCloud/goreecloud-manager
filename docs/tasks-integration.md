# GoreeCloud Manager — GoreeCloud Tasks Integration

## Role

GoreeCloud Manager consumes the dedicated read-only GoreeCloud Tasks Manager API to display authorized operational work. GoreeCloud Tasks remains authoritative for task content, project membership, user permissions, task lifecycle, and data portability.

Manager does not connect to the Tasks database and does not use a normal user's password or session.

## Tasks-side authorization boundary

The Tasks endpoint maps one reusable bearer token to one existing active Tasks account configured by the Tasks deployment. That account is the authorization principal. Tasks begins the integration query with its normal `Task.objects.visible_to(identity)` authorization helper and then limits output to active project-scoped tasks marked as GoreeCloud operational work.

The intended identity is a dedicated account such as `goreecloud-manager-integration` with Viewer membership only in shared projects explicitly approved for Manager visibility. Manager cannot send a username or project identifier to broaden the identity's scope. Revoking a project membership removes that project's tasks from subsequent API responses.

The endpoint is GET-only and intentionally excludes personal Inbox tasks, ordinary non-operational tasks, descriptions, comments, labels, account details, notification state, and write operations.

## Manager configuration

```text
TASKS_ENABLED=true
TASKS_API_URL=https://tasks.goreecloud.com
TASKS_ACCESS_TOKEN_FILE=/run/secrets/goreecloud_tasks_manager_api_token
TASKS_TIMEOUT_SECONDS=5
```

For an isolated development environment only, `TASKS_ACCESS_TOKEN` may be supplied through the uncommitted `.env`. Set only one of `TASKS_ACCESS_TOKEN` or `TASKS_ACCESS_TOKEN_FILE`.

`TASKS_API_URL` is the application base URL. Manager appends:

```text
/api/v1/manager/operational-tasks/
```

The production container/deployment must mount the protected token file at the configured path. The repository does not create, commit, or provision a production token.

## Manager behavior

The adapter:

- sends a Bearer token only to the configured Tasks base URL;
- uses a bounded request timeout;
- validates the `goreecloud.tasks.manager.v1` schema and version 1 response;
- rejects malformed task objects, invalid timestamps, impossible summary counts, and unsupported schemas;
- normalizes only the approved operational fields;
- never returns the access token in the snapshot or user interface;
- fails soft to `disabled`, `misconfigured`, or `unavailable` states instead of breaking the Manager Overview page; and
- preserves Tasks as the authoritative source instead of caching or rewriting task records in Manager's database.

The authenticated Manager `/tasks/` page shows the current summary and returned operational task records. The existing integration registry also reports the Tasks adapter state on the Overview page.

## Displayed fields

Manager may display:

- task ID and title;
- project ID and name;
- GoreeCloud priority and task status;
- due timestamp;
- assigned system and service;
- environment and workload category;
- blocker and resume condition;
- backup, recovery, validation, and documentation requirement flags;
- related change-record and documentation references; and
- task update timestamp.

Manager does not receive task descriptions, comments, labels, email addresses, passwords, sessions, reminder state, or the Tasks integration token through the API response.

## Failure handling

- Tasks integration disabled in Manager: no network request is made.
- Missing or ambiguous Manager token configuration: `misconfigured`.
- Tasks timeout or connection failure: `unavailable`.
- HTTP 401: sanitized credential rejection state.
- HTTP 403: sanitized authorization denial state.
- HTTP 404: endpoint unavailable, including a Tasks deployment where the Manager API remains disabled.
- Unsupported or malformed response: `unavailable` with no raw upstream body rendered to the user.

## Identity and credential lifecycle

The authoritative lifecycle for the integration identity and bearer token is maintained in GoreeCloud Tasks at:

[`GoreeCloud Tasks — Manager Integration Identity and Credential Lifecycle`](https://github.com/GoreeCloud/goreecloud-tasks/blob/main/docs/manager-integration-credential-lifecycle.md)

Manager is the credential consumer. It does not create the Tasks service identity, grant project memberships, generate a Tasks user password, or decide which projects are authorized. Those decisions remain on the Tasks side.

For long-lived deployment I will use the file-backed token source and keep the direct `TASKS_ACCESS_TOKEN` variable empty. If Tasks and Manager are deployed together on the planned Infrastructure Services VM, the preferred design uses one protected host-side runtime source under the approved GoreeCloud Docker secrets structure and mounts that same credential only into the two containers that require it. I will not duplicate the bearer token across unrelated `.env` files merely for convenience.

Manager must be disabled or stopped during a planned single-token rotation until the replacement protected source is installed and both applications have been restarted or recreated as required by the final production secret-mount design. A brief fail-soft integration interruption is preferable to retaining multiple long-lived overlapping tokens without a separately approved requirement.

If the token may be exposed, Manager should stop presenting it immediately, Tasks may disable the Manager API, and the credential must be replaced rather than merely deleting a local copy. If the integration is retired, Manager must be disabled before the Tasks identity, memberships, secret source, and integration-specific network path are retired through the authoritative Tasks lifecycle procedure.

No active bearer value belongs in Manager logs, screenshots, support output, change logs, pull requests, or ordinary documentation.

## Production boundary

This repository increment establishes the application-to-application contract and read-only Manager presentation. It does not provision the real Tasks integration account, project memberships, production bearer token, private inter-service network, DNS route, Caddy route, Vaultwarden record, monitoring check, or production deployment.

Before production use, the integration requires separately approved credential generation/storage, private service reachability, transport validation, token rotation/revocation procedure, backup/recovery treatment for any Manager-owned configuration, and production acceptance testing.

A successful API response does not authorize Manager to modify Tasks data or to execute infrastructure changes.
