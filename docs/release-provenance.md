# GoreeCloud Manager Release Provenance

## Purpose

This document defines the source-side release-provenance and deployment-artifact identity contract for GoreeCloud Manager. The contract binds an exact Git source revision to the exact single-platform container image loaded and scanned by CI, the OCI image-manifest digest emitted by that same Buildx build, and the machine-readable software-supply-chain evidence produced for the build.

This evidence improves release traceability and prepares a future immutable deployment selector. It does **not** publish Manager, create a registry release, authorize production, or satisfy target-environment production-readiness evidence.

## Governing identity chain

Accepted source-side evidence now uses this chain:

`exact Git revision -> OCI revision/source labels -> loaded Docker image/config digest -> OCI manifest digest -> SBOM/vulnerability evidence -> retained release provenance`

The identities have different meanings and must not be conflated.

### Git source revision

CI checks out and builds the exact forty-character pull-request head or push SHA.

### Docker image ID / config digest

The loaded image is inspected with Docker. Its `sha256:` image ID identifies the image configuration used by the local Docker engine.

### OCI manifest digest

CI builds with `docker buildx build --load --metadata-file ...`. Docker Buildx emits `containerimage.config.digest`, `containerimage.digest`, and `containerimage.descriptor`.

Manager requires the Buildx config digest to equal the loaded Docker image ID. It also requires the descriptor digest to equal the Buildx manifest digest and accepts only an OCI image manifest or Docker distribution image manifest media type.

The minimized accepted result is written to:

`security-artifacts/goreecloud-manager-oci-build-identity.json`

### Registry distribution digest

A Buildx OCI manifest digest is **not** proof that an image has been published to a registry. A future approved publication workflow must capture the immutable digest reported by the registry for the published artifact and record how that registry object relates to the accepted CI manifest.

No registry publication is performed by the current workflow.

## Source and image labels

Accepted CI builds pass the full Manager source revision into the Docker build as `MANAGER_SOURCE_REVISION`.

The image records:

- `org.opencontainers.image.title=GoreeCloud Manager`
- `org.opencontainers.image.source=https://github.com/GoreeCloud/goreecloud-manager`
- `org.opencontainers.image.revision=<exact 40-character Git SHA>`
- `org.opencontainers.image.licenses=MIT`
- `org.opencontainers.image.vendor=GoreeCloud`

The Dockerfile intentionally defaults `MANAGER_SOURCE_REVISION` to `local` so ordinary developer builds remain usable without pretending to be accepted release candidates.

## Buildx metadata minimization

The security image build uses Buildx with `--load` so the exact loaded image can continue through the existing Trivy SBOM and vulnerability scan path.

Raw Buildx metadata is written only to the GitHub Actions runner temporary directory. `BUILDX_METADATA_PROVENANCE=disabled` is set because Manager currently needs only the digest and descriptor fields required to bind the exact build output; it does not retain an unnecessary raw Buildx provenance payload.

`scripts/oci_build_identity.py` validates the raw metadata and retains only:

- exact source revision and repository identity
- exact CI image reference
- exact loaded Docker image/config digest
- exact OCI manifest digest
- descriptor digest, media type, and size
- required OCI labels
- any repository digests already visible to the local image
- explicit negative publication/deployment/production claims

The raw Buildx metadata itself is not uploaded as a security artifact.

## Release-provenance evidence

CI also generates:

`security-artifacts/goreecloud-manager-release-provenance.json`

The existing release-provenance record hashes the OCI build-identity JSON alongside the other security evidence. That binds the OCI manifest identity into the same retained evidence chain as:

- Python CycloneDX SBOM
- OSV Python vulnerability report
- container-image CycloneDX SBOM
- Trivy Debian operating-system vulnerability report
- container operating-system vulnerability policy summary

The current source materials recorded by release provenance remain:

- `Dockerfile`
- `requirements.txt`
- `requirements.lock`

## Fail-closed verification

OCI build-identity generation and verification are separate operations. Release-provenance generation and verification remain separate operations as well.

Any of the following fails the relevant CI evidence gate:

- a short or malformed source revision
- a malformed SHA-256 image/config/manifest digest
- missing or incorrect OCI labels
- a source revision label that differs from the exact checked-out revision
- an unexpected image reference
- a Buildx config digest that differs from the loaded Docker image ID
- a Buildx descriptor digest that differs from the emitted manifest digest
- an unsupported image-manifest media type
- malformed descriptor size or annotations
- a changed OCI build-identity record
- missing source or security-evidence files
- duplicate evidence paths
- changed file digest or size
- malformed provenance evidence
- any positive claim of registry publication, deployment, target-environment readiness, or production approval

The final `always()` enforcement step treats any of these evidence-stage failures as a CI failure while still allowing diagnostic artifacts from other stages to be retained.

## Retention

The OCI build-identity JSON and release-provenance JSON are uploaded inside the existing:

`manager-supply-chain-security-<source-revision>`

artifact retained for 30 days.

Manager does not add another permanent readiness workflow solely for artifact identity. The existing six permanent exact-revision readiness workflows remain the source-side acceptance boundary.

## Future deployment-artifact acceptance

A future approved publication and deployment flow should extend this chain:

1. Build from the exact accepted source revision.
2. Preserve the OCI source and revision labels.
3. Record the exact loaded Docker image/config digest.
4. Record and verify the exact OCI manifest digest from the same build.
5. Generate and verify the retained OCI build-identity and release-provenance records.
6. Publish only through an approved registry or artifact channel.
7. Capture the immutable registry-reported digest/reference.
8. Verify the published artifact is traceably derived from the accepted build.
9. Deploy by immutable digest rather than mutable tag alone.
10. Record the deployed digest in target-environment evidence.
11. Preserve the previous accepted digest for rollback evidence.

This follows the GoreeCloud Docker Image Pinning Standard preference for digest-controlled critical and internally built images.

## Repository-governance dependency

Source evidence is strongest when GitHub also prevents direct bypass of the accepted workflow. During this increment, `main` was independently observed as unprotected.

GitHub issue #47 tracks the separate repository-setting requirement to require pull requests and the six permanent readiness checks and to block force pushes and branch deletion.

This document does not claim that repository protection is already enabled.

## Production boundary

This contract does not:

- create or rotate credentials
- publish an image
- create a registry or release
- modify production Docker state
- modify DNS, Caddy, NetBird, firewall, backup, monitoring, or alerting configuration
- deploy or restart Manager in a target environment
- satisfy any of the 28 target-environment production-readiness evidence categories
- change the `not-approved` production boundary

Its role remains source-side: make the accepted source, exact CI image/config digest, OCI manifest digest, and retained security evidence cryptographically traceable to one another before any future publication or deployment is authorized.
