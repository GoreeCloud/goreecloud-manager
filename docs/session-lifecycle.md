# GoreeCloud Manager Session Lifecycle Maintenance

## Purpose

GoreeCloud Manager uses Django database-backed sessions for its private administrative authentication state. Session expiration prevents an expired session from remaining usable, but expired database rows still require routine cleanup so stale authentication records do not accumulate indefinitely in the Manager SQLite database.

This document defines the source-controlled maintenance contract for that cleanup. It does not create a production scheduler, authorize a deployment, or change the existing production-readiness boundary.

## Command

Manager provides:

```bash
python manage.py prune_expired_sessions
```

The command:

- freezes one cutoff timestamp at command start;
- selects only sessions whose `expire_date` is earlier than that cutoff;
- deletes expired rows in bounded batches;
- preserves active sessions;
- prints only aggregate counts and dry-run state;
- never prints session keys, encoded session payloads, user identifiers, cookies, or authentication material.

The default batch size is 100 rows. Operators may select a value from 1 through 1000:

```bash
python manage.py prune_expired_sessions --batch-size 250
```

The bounded loop is intended to keep one maintenance pass understandable and limit the amount of expired state removed in each delete operation rather than issuing one unbounded delete against the SQLite session table.

## Dry run

Before a scheduled or manual cleanup, the operator may inspect the number of currently expired rows without changing the database:

```bash
python manage.py prune_expired_sessions --dry-run
```

Example output shape:

```text
expired_sessions=12 deleted_sessions=0 dry_run=true
```

A normal successful cleanup uses the same sanitized summary shape:

```text
expired_sessions=12 deleted_sessions=12 dry_run=false
```

Counts are operational metadata only. No session identifier or session content is emitted.

## Scheduling boundary

This repository intentionally does not choose or activate the production schedule. Final cadence and execution ownership depend on the approved Infrastructure Services VM runtime, backup timing, maintenance windows, monitoring, and target-environment operating procedures.

A future production schedule must:

1. run only after the production Manager deployment has been separately authorized;
2. use the same application image and database configuration as the deployed Manager instance;
3. avoid overlapping backup, migration, upgrade, or restore operations unless the overlap has been explicitly validated;
4. record success/failure through an approved monitoring path without logging session identifiers or payloads;
5. remain independently disableable during incident response, recovery, or rollback.

Until that target-environment work is authorized, the command is a source-side operational capability and CI-tested maintenance contract only.

## Validation contract

Automated tests prove that:

- dry-run mode makes no database change;
- active sessions survive cleanup;
- expired sessions are deleted;
- cleanup continues across multiple bounded batches;
- invalid batch sizes fail closed;
- command output excludes representative session-key and session-payload markers.

The existing authentication/session resilience tests continue to prove login session-key rotation, read-only request behavior, POST-only logout and server-side session deletion, password-change invalidation, safe redirect handling, no-store login responses, and sanitized authentication logging.

## Recovery and rollback

The command changes only already-expired session rows. Removing expired sessions does not invalidate active sessions.

If the source implementation must be rolled back, revert the related Git commit. No schema migration is introduced by this feature.

Production backup and restore evidence remains governed by the separate Manager production-readiness requirements. This source-side maintenance capability does not satisfy any of the twenty-eight target-environment evidence categories by itself.
