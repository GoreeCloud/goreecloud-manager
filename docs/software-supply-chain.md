# Software Supply-Chain Immutability

## Purpose

GoreeCloud Manager treats build and CI inputs as reviewed source-controlled inputs rather than accepting mutable upstream references at execution time. This document defines that source-level reproducibility and Python dependency vulnerability-evidence boundary. It does not claim that pinned software is vulnerability-free and it does not approve production deployment.

## Python dependency contract

`requirements.txt` remains the small human-maintained declaration of Manager's direct runtime dependencies.

`requirements.lock` is the executable production lock. It contains every direct and transitive dependency resolved for the validated CPython 3.14.6 / Ubuntu 24.04 environment, with:

- an exact `==` version for every package;
- a SHA-256 hash for the selected PyPI wheel;
- only platform-independent Python wheels in the current graph.

The Docker image and normal CI install dependencies with:

```text
python -m pip install --require-hashes --only-binary=:all: -r requirements.lock
```

`--require-hashes` makes package integrity an all-or-nothing contract: a missing dependency, unpinned version, or unapproved archive hash fails installation. `--only-binary=:all:` prevents an unexpected source distribution from becoming a build-time code-execution fallback.

The current lock contains twelve packages:

- Django 5.2.17
- asgiref 3.12.1
- sqlparse 0.6.0
- gunicorn 26.0.0
- packaging 26.3
- httpx 0.28.1
- anyio 4.14.2
- certifi 2026.7.22
- httpcore 1.0.9
- h11 0.16.0
- idna 3.18
- whitenoise 6.12.0

Regression coverage requires every direct dependency in `requirements.txt` to exist at the same version in the lock and requires every locked package to carry a 64-character SHA-256 hash.

## Base-image contract

The application image uses a readable Python patch tag and an immutable Docker content digest together:

```text
python:3.14.6-slim@sha256:cea0e6040540fb2b965b6e7fb5ffa00871e632eef63719f0ea54bca189ce14a6
```

The tag documents the intended runtime version. The digest fixes the selected multi-platform image index so a later upstream tag update cannot silently change what Manager builds from.

The previous Dockerfile syntax directive was removed because Manager does not currently require a non-default Dockerfile frontend feature. This avoids introducing another mutable external image reference solely to parse a simple Dockerfile.

Regression coverage requires a complete Python `x.y.z` tag and a 64-character SHA-256 image digest, while the existing runtime test continues to require the CI Python patch version to match the image tag.

## GitHub Actions contract

All external GitHub Actions used by Manager workflows are referenced by full 40-character commit SHA rather than a mutable major-version tag.

The current reviewed references correspond to the previously used releases:

- `actions/checkout` v4: `11d5960a326750d5838078e36cf38b85af677262`
- `actions/setup-python` v5: `a26af69be951a213d495a4c3e4e4022e16d87065`
- `actions/setup-node` v4: `49933ea5288caeca8642d1e84afbd3f7d6820020`
- `actions/upload-artifact` v4: `ea165f8d65b6e75b540449e92b4886f43607fa02`

A trailing major-version comment remains beside each SHA for readability. Regression coverage scans every workflow and fails if an external `owner/repository@reference` does not use a full commit SHA.

All six workflows use the explicit `ubuntu-24.04` hosted-runner family and a finite job timeout. The hosted runner image still receives GitHub-maintained updates within that OS family; this source contract prevents accidental migration to a different floating OS family but does not pretend that a GitHub-hosted runner label is a byte-for-byte immutable machine image.

## Python dependency SBOM

Normal CI generates a deterministic CycloneDX 1.7 JSON SBOM from `requirements.lock` with `scripts/python_supply_chain_security.py`. The artifact identifies the exact source revision, the SHA-256 digest of the lock file, every locked package version, its PyPI package URL, and the approved wheel SHA-256 hash.

The SBOM explicitly declares its scope as `python-runtime-dependencies`. It is not represented as a complete operating-system, container-base-image, browser, GitHub-hosted-runner, or target-environment inventory. Those layers require separate evidence.

The generated file is retained as `security-artifacts/goreecloud-manager-python.cdx.json` in the CI supply-chain security artifact for thirty days.

## OSV vulnerability evidence

Normal CI queries the official OSV.dev batch API for every package/version pair in `requirements.lock`. The client uses only the Python standard library, has a ten-second request timeout, performs at most two bounded attempts, caps response size locally, and treats malformed, incomplete, paginated, unavailable, or otherwise unusable responses as an inability to establish evidence.

`security/osv-policy.json` defines the acceptance policy. The current policy is deliberately conservative: every known vulnerability returned for a locked Python package is blocking unless an explicit source-controlled exception exists.

An exception must match the exact OSV identifier and normalized package name and must contain:

- the OSV identifier;
- the package name;
- an ISO `YYYY-MM-DD` expiration date;
- a non-empty reason.

Expired exceptions fail policy validation. Wildcard exceptions are not supported. The report records the reason and expiration date for every exception actually applied.

The scanner writes `security-artifacts/osv-python-vulnerabilities.json`. Raw scanner exceptions are not copied into the report; failures expose only a safe error type and the statement that vulnerability evidence could not be established.

The OSV step uses `continue-on-error` only so normal application validation can finish and the machine-readable SBOM/report can still be uploaded. A final `always()` enforcement step examines the original OSV step outcome and fails CI unless it passed. This is therefore evidence-preserving fail-closed behavior, not a bypass.

The supply-chain artifact is uploaded even when later CI validation fails and is retained for thirty days. A successful CI run therefore proves both the normal application test contract and the Python dependency vulnerability policy for that exact source revision at that execution time.

## Deliberate update procedure

Supply-chain pins and vulnerability evidence are maintenance controls, not permanent values. Security and compatibility updates require deliberate refreshes.

For a Python dependency update:

1. update the intended direct dependency version in `requirements.txt` when applicable;
2. resolve the complete dependency graph in the validated Python/runtime environment;
3. obtain wheel SHA-256 hashes from authoritative PyPI release metadata;
4. update every affected direct and transitive entry in `requirements.lock`;
5. run the generated CycloneDX inventory and OSV policy against the exact final graph;
6. run normal CI and all five production-readiness workflows on the exact final head;
7. review any OSV finding rather than weakening the default policy merely to make CI pass.

For a base-image update:

1. select the intended official Python patch/tag;
2. resolve the current official multi-platform digest;
3. update the Dockerfile tag and digest together;
4. update the CI Python patch version if the Python patch changes;
5. run all six exact-head gates, including disposable runtime, backup/restore, and rollback validation;
6. perform separate base-image/operating-system vulnerability review because the Python OSV gate does not cover those packages.

For a GitHub Action update:

1. select the intended official action release/tag;
2. resolve that release to the full commit SHA from the action's official repository;
3. update the SHA and readable version comment together;
4. run the complete exact-head workflow set before merge.

## Security boundary

These controls reduce mutable-input and dependency-substitution risk, create a standard Python dependency inventory, and make known-vulnerability evidence part of the ordinary CI acceptance path. They do not prove that an upstream package, action commit, base image, hosted runner, or environment is free of vulnerabilities or malicious code. Hashes prove identity, and OSV results prove only what the queried vulnerability data reported for the locked Python versions at the time of the scan.

The repository still requires routine dependency, action, Python, operating-system/base-image, and vulnerability review. Container operating-system scanning and target-environment vulnerability evidence remain separate production-readiness work.

## Production boundary

This increment does not:

- deploy or publish Manager;
- alter production Docker containers or images;
- create or change DNS, Caddy, NetBird, firewall, or port state;
- create, rotate, or expose credentials or secret mounts;
- create production backup, monitor, notification, or alerting resources;
- change integration permissions;
- mark any target-environment evidence category satisfied;
- approve production activation.

The production-readiness evidence manifest remains authoritative for the target environment and approval state.
