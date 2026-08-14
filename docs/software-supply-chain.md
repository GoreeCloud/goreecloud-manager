# Software Supply-Chain Immutability

## Purpose

GoreeCloud Manager treats build and CI inputs as reviewed source-controlled inputs rather than accepting mutable upstream references at execution time. This document defines that source-level reproducibility boundary. It does not claim that pinned software is vulnerability-free and it does not approve production deployment.

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

A trailing major-version comment remains beside each SHA for readability. Regression coverage scans every workflow and fails if an external `owner/repository@reference` does not use a full commit SHA.

All six workflows also use the explicit `ubuntu-24.04` hosted-runner family and a finite job timeout. The hosted runner image still receives GitHub-maintained updates within that OS family; this source contract prevents accidental migration to a different floating OS family but does not pretend that a GitHub-hosted runner label is a byte-for-byte immutable machine image.

## Deliberate update procedure

Supply-chain pins are maintenance controls, not permanent values. Security and compatibility updates require deliberate refreshes.

For a Python dependency update:

1. update the intended direct dependency version in `requirements.txt` when applicable;
2. resolve the complete dependency graph in the validated Python/runtime environment;
3. obtain wheel SHA-256 hashes from authoritative PyPI release metadata;
4. update every affected direct and transitive entry in `requirements.lock`;
5. run the normal CI and all five production-readiness workflows on the exact final head;
6. review dependency security information separately from hash correctness.

For a base-image update:

1. select the intended official Python patch/tag;
2. resolve the current official multi-platform digest;
3. update the Dockerfile tag and digest together;
4. update the CI Python patch version if the Python patch changes;
5. run all six exact-head gates, including disposable runtime, backup/restore, and rollback validation;
6. review current image vulnerability information rather than assuming a new digest is safe solely because it is immutable.

For a GitHub Action update:

1. select the intended official action release/tag;
2. resolve that release to the full commit SHA from the action's official repository;
3. update the SHA and readable version comment together;
4. run the complete exact-head workflow set before merge.

## Security boundary

These controls reduce mutable-input and dependency-substitution risk and make repeated builds materially more reproducible. They do not prove that an upstream package, action commit, or base image is free of vulnerabilities or malicious code. Hashes prove identity, not trustworthiness.

The repository still requires routine dependency, action, Python, operating-system/base-image, and vulnerability review. A future vulnerability-scanning policy may add additional source-level evidence, but any target-environment scanner, registry, deployment identity, or production image record remains separate production-readiness evidence.

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
