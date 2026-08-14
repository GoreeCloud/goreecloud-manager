# SQLite Concurrency and Contention Boundary

## Purpose

GoreeCloud Manager currently uses SQLite for its small private administrative workload. This document defines the runtime controls that keep that choice bounded and the conditions that require migration to a server database instead of continued SQLite tuning.

## Current Stability Contract

Manager configures Django's SQLite backend with the following runtime behavior:

- `DJANGO_SQLITE_TIMEOUT_SECONDS=10` by default.
- The timeout must be a finite positive value and cannot exceed 20 seconds.
- `transaction_mode` is `IMMEDIATE` so explicit transactions establish write intent before doing transactional work and wait up to the configured timeout when another writer holds the database.
- `ATOMIC_REQUESTS` remains disabled so Manager does not wrap complete web requests in unnecessarily long database transactions.
- `CONN_MAX_AGE` remains zero so request database connections are short-lived rather than persistent across unrelated requests.
- A recognized transient SQLite lock failure at the outer Manager request boundary returns HTTP `503 Service Unavailable` with `Retry-After: 1`, `Cache-Control: no-store`, and the server-generated `X-Request-ID`.
- The raw SQLite exception text, database path, request query string, and caller-supplied request identifiers are not returned or written to the contention log event.
- Database operational errors that are not recognized SQLite lock/contention errors are not converted to the retryable response; they continue through Django's normal error path so unrelated defects are not hidden.

## Why the Timeout Is Bounded

A longer SQLite timeout can reduce failures caused by brief write overlap, but it does not increase SQLite's underlying write concurrency. Manager therefore keeps the database wait below both the Gunicorn hard request timeout and the integration response budget boundary.

The timeout is a contention cushion, not a capacity mechanism.

## Transaction Scope

Database transactions must remain short. Manager should avoid introducing request-wide transactions, slow network calls inside transactions, or long-running work between the start of a write transaction and commit.

Integration HTTP and artifact reads remain outside database transactions.

## PostgreSQL Migration Trigger

SQLite remains acceptable only while Manager is a low-write, small-user administrative application and lock contention is exceptional.

A PostgreSQL migration should be planned instead of raising the SQLite timeout when any of the following becomes true:

1. SQLite lock/contention events become recurring under normal use rather than exceptional.
2. Concurrent authenticated users or automated writers become a normal operating condition.
3. Manager begins storing materially larger operational datasets or write-heavy historical data.
4. Background jobs begin writing to the same application database concurrently with web requests.
5. Authentication or session writes regularly consume a meaningful portion of the configured SQLite timeout.
6. Stability requires repeated increases to SQLite timeout values or additional application-level retry loops.

The migration must be handled as a separate controlled change with backup, restore, migration, rollback, and target-environment validation evidence.

## Validation Requirements

Changes to this boundary must preserve tests that verify:

- the configured timeout and transaction mode;
- the live SQLite connection's busy timeout;
- rejection of invalid, non-finite, non-positive, and over-limit timeout values;
- sanitized retryable handling for recognized lock failures;
- propagation of unrelated database operational errors;
- normal authentication, session, readiness, backup/restore, runtime-publication, monitoring, upgrade/rollback, and production-readiness-manifest workflows.

## Security Patch Baseline

The stabilization pass that introduced this boundary also updates Django from 5.2.16 to 5.2.17. Django 5.2.17 is a security patch release and remains within the existing Django 5.2 LTS line; this change does not alter Manager's application architecture or database schema.
