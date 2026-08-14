# GoreeCloud Manager Backup and Restore Readiness

## Purpose

This document defines the source-controlled, disposable backup and restoration validation used to prepare GoreeCloud Manager for future production without creating a production backup repository, schedule, monitor, or deployment.

Manager currently owns a small amount of persistent state in SQLite, including Django authentication, session, migration, and application-owned database state. A raw copy of a live SQLite file is not treated as sufficient recovery evidence. The validation uses SQLite's online backup API to create a consistent recovery point while the Manager application is running, validates that recovery point, destroys the disposable primary data volume, restores into a clean replacement volume while the application is offline, and proves that the recovered application can authenticate and operate.

## Source-controlled backup utility

`ops/sqlite-backup.py` provides three deliberately narrow operations:

- `backup SOURCE DESTINATION` — opens the source SQLite database read-only and creates a transactionally consistent destination through `sqlite3.Connection.backup()`;
- `restore SOURCE DESTINATION` — validates the backup and creates a new destination database through the same SQLite backup mechanism;
- `verify DATABASE` — requires `PRAGMA integrity_check` to return `ok`, requires `PRAGMA foreign_key_check` to return no errors, and reports non-secret checksum/size/page metadata.

The utility refuses to overwrite an existing destination. Completed recovery points are written through a temporary file in the destination directory, validated before publication, restricted to mode `0600`, flushed, and published without replacing an existing recovery point.

The helper does not select a production storage destination, create a backup schedule, manage Kopia, register Healthchecks, send notifications, or contain production credentials.

## Disposable topology

`scripts/backup_restore.compose.yml` uses three physically distinct Docker named volumes for the validation run:

1. **Primary Manager data** — the running pre-loss SQLite state.
2. **Restore-target Manager data** — a clean replacement data volume used only after loss.
3. **Backup data** — the independent disposable recovery-point volume that survives destruction of the primary data volume.

The Manager primary and restored runtimes use the same hardened candidate image and preserve the existing runtime-security controls:

- non-root `manager` user;
- read-only root filesystem;
- `no-new-privileges`;
- all Linux capabilities dropped;
- bounded `/tmp` tmpfs;
- no host-published application port;
- no Docker socket;
- file-backed synthetic Django secret;
- dedicated writable SQLite data volume.

Backup and restore helper services have `network_mode: none`. They require access only to the source, destination, or backup volumes appropriate to the operation.

## Validation sequence

`scripts/validate_backup_restore_readiness.sh` performs this sequence:

1. Generate runtime-random synthetic Django and administrative credentials in a private temporary directory.
2. Validate the SQLite helper's Python syntax.
3. Render the Compose model and fail on host-published ports, missing Manager runtime hardening, helper network access, direct Django secret values, or volume-identity drift.
4. Build the exact candidate Manager image and disposable helper services.
5. Start the primary Manager and apply its real Django migrations.
6. Create a synthetic administrator plus a related Django group and verify the relationship.
7. Create `manager-pre-loss.sqlite3` through SQLite's online backup API while Manager remains running.
8. Verify database integrity, foreign keys, SHA-256 metadata, and stable checksum immediately after creation.
9. Prove the existing recovery point cannot be silently overwritten.
10. Mutate the live primary database after the recovery point by changing the synthetic administrator and adding a post-backup-only user.
11. Stop and remove the primary Manager container and delete the entire primary Manager data volume.
12. Confirm the independent backup volume still exists.
13. Create a new replacement Manager data volume, apply migrations, and prove it contains none of the synthetic pre-loss data.
14. Remove only that clean placeholder database and restore the verified pre-loss recovery point while no Manager process is using the target database.
15. Prove a repeated restore refuses to overwrite the restored database.
16. Start the restored Manager, allowing the normal startup migration step to confirm schema compatibility.
17. Verify the restored administrator has the pre-backup values and relationship, and prove the post-backup-only mutation is absent.
18. Verify the restored password hash accepts the separately recovered synthetic password.
19. Use Django's authenticated client against the restored database to load the Manager Overview and the exact minimal `/healthz/` response.
20. Create and verify a second `manager-post-recovery.sqlite3` recovery point from the restored Manager to prove backup protection can resume after recovery.
21. Restore that second recovery point to a separate verification database and run integrity and foreign-key checks again.
22. Require both backup files to remain mode `0600` and reject plaintext appearances of the generated Django secret or administrative password in either SQLite artifact.
23. Inspect the restored Manager container to ensure recovery did not weaken the non-root, read-only-root, no-host-port, or no-Docker-socket boundaries.
24. Scan rendered Compose data, Docker inspection data, and runtime logs for the generated synthetic secret values.
25. Remove the disposable containers, networks, volumes, and temporary credentials.

## Point-in-time behavior

The test intentionally changes the primary database **after** creating the first recovery point. Successful recovery must therefore restore the administrator's pre-backup state and omit the post-backup-only user. This prevents a test from passing merely because some SQLite file was copied; the recovered database must correspond to the selected recovery point.

## Relationship to Kopia and production backup architecture

This gate validates Manager's database-native recovery-point and restoration semantics. It does not replace GoreeCloud's broader backup architecture.

For production, a validated Manager SQLite recovery point still needs to be protected by an approved independent backup system and repository according to GoreeCloud backup policy. Kopia or another approved protection layer may store the validated recovery-point file together with required configuration and recovery references. The application database itself must not depend on unsafe live-file copying when database-native backup semantics are available.

## What a green gate proves

A green Backup Restore Readiness workflow proves, for the exact source revision under test, that:

- the application can create a consistent online SQLite recovery point;
- the recovery point passes integrity and relationship checks;
- recovery storage is independent from the disposable primary data volume;
- complete loss of that primary volume does not destroy the recovery point;
- a clean replacement can be restored offline without overwriting an existing target;
- selected point-in-time Manager state and relationships recover correctly;
- the recovered administrator can authenticate;
- the restored application reaches its Overview and health path;
- backup protection can produce another valid recovery point after restoration;
- generated plaintext synthetic secrets are not embedded in the SQLite recovery artifacts;
- the restored runtime remains hardened.

## What the gate does not prove

This validation does **not**:

- choose or create a production Manager backup repository;
- create a production Kopia policy or snapshot;
- schedule production Manager backups;
- configure Healthchecks, ntfy, Uptime Kuma, or another production backup monitor;
- prove off-host or off-site backup independence;
- establish production retention, RPO, or RTO values;
- create or recover real production Manager credentials;
- validate the final production secret file owner, group, mode, or ACL;
- perform a real Infrastructure Services VM restore;
- validate production DNS, Caddy, NetBird, firewall, or monitoring recovery;
- prove full-host or full-VM disaster recovery;
- authorize production deployment or activation.

Those remain separate approval-controlled target-environment evidence.

## Rollback

The source changes are reversible through Git. The validation creates only disposable synthetic state and removes it after each run. No production Manager database or backup target is opened, modified, restored, or deleted by this workflow.
