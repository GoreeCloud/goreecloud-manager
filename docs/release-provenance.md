# GoreeCloud Manager Release Provenance

## Purpose

This document defines the source-side release-provenance contract for GoreeCloud Manager. The contract binds an exact Git source revision to the exact container image identity built by CI and to the machine-readable software-supply-chain evidence produced for that same image.

This evidence improves release traceability. It does **not** deploy Manager, publish an image, authorize production, or satisfy target-environment production-readiness evidence.

## Source and image identity

Accepted CI builds pass the full 40-character Manager source revision into the Docker build as `MANAGER_SOURCE_REVISION`.

The image records the following Open Container Initiative labels:

- `org.opencontainers.image.title=GoreeCloud Manager`
- `org.opencontainers.image.source=https://github.com/GoreeCloud/goreecloud-manager`
- `org.opencontainers.image.revision=<exact 40-character Git SHA>`
- `org.opencontainers.image.licenses=MIT`
- `org.opencontainers.image.vendor=GoreeCloud`

The Dockerfile intentionally defaults `MANAGER_SOURCE_REVISION` to `local` so normal developer builds remain usable without pretending to be release artifacts. CI must explicitly replace that value with the exact revision being tested.

## Provenance evidence

CI runs `scripts/release_provenance.py` after the Python and container security evidence has been generated. The script inspects the exact CI-built Manager image, validates its OCI identity labels, validates its `sha256:` image ID, hashes the relevant source materials and security evidence, and writes:

`security-artifacts/goreecloud-manager-release-provenance.json`

The provenance record includes:

- GoreeCloud Manager project identity.
- Canonical source repository.
- Exact full Git source revision.
- Exact CI image reference.
- Exact Docker image ID.
- Any registry repository digests visible to the inspected image.
- Required OCI labels.
- SHA-256 and byte size for source materials.
- SHA-256 and byte size for the security-evidence files.
- GitHub Actions run metadata when available.
- Explicit negative claims stating that no deployment or production approval occurred.

The current source materials recorded by CI are:

- `Dockerfile`
- `requirements.txt`
- `requirements.lock`

The current security evidence bound into the provenance record is:

- Python CycloneDX SBOM.
- OSV Python vulnerability report.
- Container-image CycloneDX SBOM.
- Trivy Debian operating-system vulnerability report.
- Container operating-system vulnerability policy summary.

## Fail-closed verification

Generation and verification are separate operations in CI. After producing the JSON record, CI immediately re-inspects the image and recomputes every recorded file hash. Any of the following causes the provenance step to fail:

- A short or malformed source revision.
- A malformed Docker image ID.
- Missing or incorrect OCI labels.
- A source revision label that differs from the exact checked-out revision.
- An unexpected image reference.
- Missing source or security-evidence files.
- Duplicate evidence paths.
- A changed file digest or size.
- A malformed provenance schema.
- A provenance record that claims deployment, target-environment readiness, or production approval.

The final CI enforcement step treats provenance failure as a CI failure even though evidence-generation steps use `continue-on-error` so partial diagnostic artifacts can still be retained.

## Retention

The provenance JSON is uploaded inside the existing `manager-supply-chain-security-<source-revision>` GitHub Actions artifact together with the other supply-chain evidence. The current workflow retains that artifact for 30 days.

This reuse is deliberate. Manager does not add another permanent readiness workflow merely to store provenance; the six permanent exact-head readiness workflows remain the source-side acceptance boundary.

## Image ID versus registry digest

A Docker image ID identifies the exact image configuration and referenced layer set present in the CI engine. It is useful and immutable for the CI-built local image, but it is **not** a substitute for the canonical distribution digest of an image published to a registry.

A future approved publication workflow must additionally record the immutable registry digest after the image is pushed. A future target-environment deployment must then record and verify that same registry digest before deployment evidence can establish which distributable artifact was actually deployed.

Until that exists, the provenance record intentionally reports whether any registry digest was observed and does not claim that a distributable production artifact has been published.

## Production boundary

This source-side contract does not change GoreeCloud Manager's production status.

It does not:

- Create or rotate credentials.
- Publish an image to a registry.
- Create a release.
- Modify DNS, Caddy, NetBird, firewall, backup, monitoring, or alerting configuration.
- Deploy or restart Manager in a target environment.
- Satisfy any of the 28 target-environment production-readiness evidence categories.
- Change the `not-approved` production boundary.

Its role is narrower: make the accepted source and the exact CI-built candidate image cryptographically traceable to one another and to their retained security evidence.

## Future release progression

When a GoreeCloud Manager deployment is explicitly authorized, the release path should extend this contract rather than replace it:

1. Build from the exact accepted source revision.
2. Preserve the OCI revision/source labels.
3. Generate and verify this provenance record.
4. Publish through an approved registry or artifact channel.
5. Capture the canonical immutable distribution digest.
6. Verify that digest before target-environment deployment.
7. Record the deployed digest in target-environment evidence.
8. Preserve rollback evidence for the previous known-good digest.

That future work requires separate target-environment authorization and is not implied by source-side readiness.
