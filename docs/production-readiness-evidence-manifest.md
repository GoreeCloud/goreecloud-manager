# GoreeCloud Manager Production Readiness Evidence Manifest

## Purpose

GoreeCloud Manager now has multiple permanent source/disposable readiness gates covering application behavior, hardened runtime/private publication, database backup/restoration, upgrade/rollback, and monitoring/alert delivery. Those gates are valuable only if their inventory and the still-outstanding real-environment evidence remain explicit and synchronized.

`scripts/manager_production_readiness_manifest.json` is the aggregate machine-readable readiness inventory. It does not approve production. It records:

- the current production state;
- every permanent source/disposable workflow and exact required job;
- the declared effective check count;
- every target-environment evidence category that must be tracked separately from disposable CI;
- evidence references, verification timestamps, and verifiers only after a target category is genuinely satisfied.

The initial accepted state is intentionally conservative:

- production status: `not-approved`;
- source/disposable workflow layers: 6;
- effective source/disposable checks: 6;
- target-environment evidence categories: 28;
- target evidence satisfied: 0;
- target evidence outstanding: 28.

## Source evidence inventory

The manifest declares these permanent workflow/job pairs:

1. `CI` → `django`
2. `Runtime Publication Readiness` → `runtime-publication-readiness`
3. `Backup Restore Readiness` → `backup-restore-readiness`
4. `Upgrade Rollback Readiness` → `upgrade-rollback-readiness`
5. `Monitoring Alert Readiness` → `monitoring-alert-readiness`
6. `Production Readiness Evidence Manifest` → `production-readiness-evidence-manifest`

The aggregate workflow is intentionally included in the manifest before activation. It therefore validates its own presence rather than excluding itself from the inventory.

## Target-environment evidence categories

The manifest currently tracks 28 target categories. They remain separate because source/disposable evidence does not prove the real Infrastructure Services VM, production private-network path, production credentials, live monitor registration, production backup storage, or operational approval.

The categories cover:

- direct Infrastructure Services VM runtime inspection;
- real Docker Engine, Compose, and container state;
- production secret-file ownership, permissions, ACLs, and recoverability;
- AdGuard Home private DNS;
- NetBird Manager peer/group/policy state;
- Caddy route, TLS, source boundary, and listeners;
- host firewall/port ownership and denial behavior;
- approved/denied private publication plus authentication;
- real Uptime Kuma registration, live source observation, and retry/timeout settings;
- approved administrator alert receipt;
- monitor removal/rollback evidence;
- an independent out-of-band alert path if required;
- production backup repository and Kopia protection;
- backup scheduling and retention;
- backup monitoring and notification receipt;
- independent off-host/off-site recovery copy;
- independently available recovery credentials;
- production SQLite restoration;
- full-environment recovery;
- backup resumption after recovery;
- production update and rollback execution;
- release-image retention and capacity;
- maintenance-window and RTO evidence;
- production integration identities, credentials, and networks;
- read-only integration acceptance against production services;
- production administrator account and final acceptance;
- production documentation/recovery records;
- deployment and activation.

A category marked `outstanding` must not contain an evidence reference, verification timestamp, or verifier. A category marked `satisfied` must contain all three.

## Validator behavior

`scripts/validate_manager_production_readiness_manifest.py` fails closed on readiness drift.

It validates:

- exact top-level schema fields;
- service identity `GoreeCloud Manager`;
- production state values;
- source workflow path uniqueness;
- workflow file existence;
- exact workflow-name match;
- exact workflow-job inventory match;
- complete reconciliation between manifested workflow paths and every `.yml` file under `.github/workflows`;
- declared effective check count versus actual manifested jobs;
- target-evidence field structure;
- target-evidence status values;
- duplicate target identifiers;
- required evidence reference, verification timestamp, and verifier for satisfied evidence;
- timestamp timezone information;
- prohibition on stale approval metadata while production is not approved;
- prohibition on production approval while target evidence remains outstanding;
- basic detection of active-looking private keys, bearer credentials, credential-bearing query strings, and credential-bearing URLs inside the manifest.

## Semantic self-test

The permanent workflow runs the validator with `--self-test`. The self-test proves the fail-closed semantics by creating synthetic in-memory invalid variants and requiring rejection of:

- declared effective-check count drift;
- duplicate target evidence identifiers;
- satisfied evidence without verification metadata;
- production approval while target evidence remains outstanding;
- stale approval metadata on a not-approved state;
- active-looking sensitive values.

It also confirms that one synthetically complete satisfied target item is accepted when it includes a non-secret evidence reference, timezone-aware verification timestamp, and verifier.

These synthetic fixtures are never written back to the authoritative manifest.

## Updating target evidence

A future target category may change from `outstanding` to `satisfied` only after separately authorized real-environment validation has produced appropriate non-secret evidence.

The update must include:

- `status: satisfied`;
- a non-secret `evidence_reference` identifying the authoritative result or record;
- a timezone-aware `verified_at` timestamp;
- a `verified_by` value identifying the responsible verifier.

The manifest is not a substitute for the underlying evidence record. It is an index and consistency control.

## Production approval rule

The validator prevents the manifest from declaring production `approved` while any target category remains outstanding.

When every target category is eventually satisfied, the current `not-approved` state also fails closed and requires an explicit production-state review rather than automatically promoting the service. A future approved state must include both a non-empty approval reference and an approval timestamp.

This means passing source CI can never automatically approve production, and completing all target evidence can never automatically approve production either.

## Sensitive-information boundary

The manifest stores evidence references and verification metadata, not reusable secret values.

It must not contain:

- passwords;
- private keys;
- bearer tokens;
- API-key values;
- recovery codes;
- database credentials;
- credential-bearing URLs;
- other active reusable authentication material.

Where target evidence depends on a credential, the manifest should reference the protected credential record or validation record without reproducing the value.

## What this manifest proves

A green Production Readiness Evidence Manifest workflow proves that, for the exact repository revision under test:

- the permanent workflow/job inventory matches the aggregate manifest;
- the declared check count matches the actual manifested job count;
- the target-evidence inventory is structurally consistent;
- outstanding evidence is not falsely presented as verified;
- satisfied evidence cannot omit its verification metadata;
- production cannot be approved with outstanding target evidence;
- the manifest does not contain the active-looking sensitive-value patterns checked by the validator.

## What it does not prove

A green manifest gate does **not** prove any outstanding target-environment category.

It does not inspect the Infrastructure Services VM, configure production DNS/Caddy/NetBird/firewall, register monitors, deliver a real administrator alert, create a production backup repository, perform a real restore, execute a production rollback, create production credentials, or deploy Manager.

It is an evidence-governance control, not operational evidence by itself.

## Rollback

The manifest, validator, workflow, and documentation are source-controlled and reversible through Git. This increment does not alter Manager application data or any production infrastructure resource.
