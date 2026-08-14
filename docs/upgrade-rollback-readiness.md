# GoreeCloud Manager Upgrade and Rollback Readiness

## Purpose

This document defines the source-controlled, disposable upgrade and rollback validation used to prepare GoreeCloud Manager for future controlled releases without updating or rolling back the live Manager deployment.

A candidate release is not considered safe merely because its migrations apply to an empty database or because its new image starts successfully. Before production use, GoreeCloud Manager must have evidence that a candidate can consume the persisted state created by the previous accepted revision and that the previous revision can be restored from a verified pre-upgrade recovery point if the candidate must be rolled back.

The permanent `Upgrade Rollback Readiness` workflow provides that source/disposable evidence.

## Baseline and candidate selection

`scripts/validate_upgrade_rollback_readiness.sh` uses Git history to build two distinct Manager images:

- **baseline** — the previous accepted revision against which compatibility and rollback are evaluated;
- **candidate** — the exact revision under validation.

For branch and pull-request validation, the baseline resolves to the accepted `main` merge base when available. For a merged `main` validation run, the baseline resolves to the candidate merge commit's previous first-parent revision. The workflow checks out full history so neither revision is inferred from an incomplete shallow checkout.

The validator fails if the baseline or candidate commit is unavailable or if both resolve to the same revision.

## Pre-upgrade recovery point

The baseline image creates the actual synthetic Manager state used by the test. That state includes:

- a synthetic administrative user;
- a password hash derived from a runtime-random password stored separately from SQLite;
- staff and superuser flags;
- deterministic profile fields;
- membership in the `Synthetic Upgrade Reviewers` group.

The baseline image runs real Django migrations, system checks, migration-current checks, and live health validation before the recovery point is created.

The accepted baseline's `ops/sqlite-backup.py` then creates `pre-upgrade.sqlite3` using SQLite's online backup API. The recovery point is independently verified immediately after creation and its SHA-256 digest is retained for later immutability validation. The artifact remains mode `0600`.

## Candidate upgrade validation

The candidate image is run against the **same persisted SQLite volume created by the baseline revision**. The validator then:

1. applies candidate migrations;
2. runs Django system checks;
3. verifies that no migration remains unapplied;
4. compares selected persisted state with the exact pre-upgrade baseline state;
5. performs real authentication using the separately recovered synthetic password;
6. loads the authenticated Manager Overview;
7. verifies the minimal `/healthz/` response;
8. starts the candidate image as a live hardened Manager runtime and verifies health.

The candidate is then deliberately allowed to create candidate-era state:

- the synthetic administrator's first name is changed to `Candidate Era`;
- a `candidate-only` user is added.

This mutation gives the rollback test an explicit condition that must disappear after restoration.

## Backup-backed rollback

Rollback does not attempt to reverse the candidate in place.

The validator first confirms that the pre-upgrade recovery point's SHA-256 digest is unchanged. It then removes the **entire upgraded Manager data volume**, creates a new empty volume, and restores the verified pre-upgrade SQLite recovery point using the **previous accepted Manager image**.

After restoration, the baseline image must:

- pass Django system checks;
- report no unapplied migration;
- reproduce the exact selected baseline state captured before the upgrade;
- restore the administrator's `Accepted Baseline` first name;
- restore the group relationship;
- omit the `candidate-only` user;
- validate the separately recovered password against the restored password hash;
- authenticate successfully;
- render the Manager Overview;
- return the healthy `/healthz/` response;
- start successfully as a live Manager runtime.

The final live baseline container is inspected to require the accepted runtime boundary after rollback:

- non-root `manager` user;
- read-only root filesystem;
- all Linux capabilities dropped;
- `no-new-privileges`;
- no host-published Manager port;
- no Docker socket.

The recovery point is also scanned for the generated plaintext Django secret and administrative password, and it must remain mode `0600`. Candidate and rolled-back runtime logs plus Docker inspection output are scanned for those synthetic values.

## Initial validation issue and resolution

The first workflow run failed before database creation because the runtime-random bind-mounted secret files were mode `0400` and owned by the GitHub runner. The hardened Manager image runs as the non-root `manager` user, so that container user correctly could not read the bind-mounted files.

The disposable harness was corrected to use the same local-Compose pattern already accepted by the other GoreeCloud readiness gates:

- the temporary secret directory remains mode `0700`;
- only the runtime-random files that Docker bind-mounts into the disposable non-root containers are mode `0444`;
- the whole temporary directory is deleted during cleanup;
- no reusable or production secret is involved.

This change affects only ephemeral CI fixture files. It does not set or weaken production secret ownership, mode, ACL, or storage policy.

## Accepted branch evidence before documentation

On corrected branch head `15082b0c0c3a8d2958be3a6327c2519bfc83abb5`, Upgrade Rollback Readiness run `31772655355` passed using accepted main `7e24c8d512148373b6019ed4091e6e2a2a45a0fb` as the baseline.

The inspected run log showed this sequence:

- baseline and candidate images built separately;
- baseline migrations, state creation, and live health succeeded;
- verified pre-upgrade recovery point created;
- candidate migrations/checks succeeded against baseline state;
- candidate authentication, Overview, and health succeeded;
- candidate-only state was created;
- the upgraded data volume was destroyed;
- the verified pre-upgrade point was restored into a new volume;
- the previous accepted image passed checks, authentication, Overview, and health against the restored state;
- the exact selected baseline state returned and candidate-only state disappeared;
- rolled-back runtime hardening passed;
- rollback artifact secret and file-mode checks passed.

The verified rollback-point SHA-256 for that disposable run was:

`ceeb1c4b21acbbe044529c744cf2d262e60babd6ab5731c979c25a3d6636ae26`

This hash is evidence for that synthetic run only and is not a production backup identifier.

## What a green gate proves

A green Upgrade Rollback Readiness workflow proves for the exact source revision under test that:

- the previous accepted revision can create and operate its real persisted Manager state;
- a verified immutable pre-upgrade SQLite recovery point exists before candidate migration;
- the candidate can apply migrations to the previous accepted state;
- selected application and authorization state remains intact through the upgrade;
- the candidate can authenticate and serve Manager after migration;
- candidate-era state can be distinguished from baseline state;
- the upgraded data volume can be discarded completely;
- the previous accepted image can restore and operate the selected pre-upgrade state;
- candidate-era state disappears after rollback;
- authentication and health work after rollback;
- runtime hardening remains intact after rollback;
- generated synthetic plaintext secrets are not embedded in the rollback artifact or emitted in inspected logs/configuration.

## What the gate does not prove

This validation does **not**:

- perform a production Manager update;
- perform a production rollback;
- choose a production release version or maintenance window;
- create a production pre-upgrade backup;
- choose or create a production Kopia repository, retention policy, or independent copy;
- validate the final Infrastructure Services VM image-retention or rollback-storage capacity;
- prove a production RTO or maintenance-window duration;
- validate production Caddy, DNS, NetBird, firewall, monitoring, or notification behavior during an upgrade or rollback;
- exercise real production integration credentials or data;
- prove full-VM, Proxmox, or full-environment rollback;
- authorize production deployment or activation.

Those remain separate approval-controlled target-environment evidence.

## Rollback of this source increment

The readiness implementation itself is reversible through Git. Each CI run removes its temporary worktree, candidate/baseline images, containers, Docker volumes, recovery point, and generated synthetic credentials. It does not open, migrate, back up, restore, or delete the live GoreeCloud Manager database.
