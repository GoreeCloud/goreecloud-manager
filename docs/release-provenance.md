# GoreeCloud Manager Release Provenance

## Purpose

This document defines the source-side release-provenance and deployment-artifact identity contract for GoreeCloud Manager. The contract binds an exact Git source revision to the exact container image loaded and scanned by CI, the immutable OCI/Docker distribution descriptor digest emitted by that same Buildx build, and the machine-readable software-supply-chain evidence produced for the build.

This evidence improves release traceability and prepares a future immutable deployment selector. It does **not** publish Manager, create a registry release, authorize production, or satisfy target-environment production-readiness evidence.

## Governing identity chain

Accepted source-side evidence uses this chain:

`exact Git revision -> OCI revision/source labels -> loaded Docker image/config digest -> Buildx distribution descriptor digest -> SBOM/vulnerability evidence -> retained release provenance`

These identities have different meanings and must not be conflated.

### Git source revision

CI checks out and builds the exact forty-character pull-request head or push SHA.

### Docker image ID / config digest

The loaded image is inspected with Docker. Its `sha256:` image ID identifies the image configuration used by the local Docker engine. Manager requires the Buildx `containerimage.config.digest` to equal this loaded Docker image ID.

### Buildx distribution descriptor digest

CI builds with `docker buildx build --load --metadata-file ...`. Buildx emits `containerimage.config.digest`, `containerimage.digest`, and `containerimage.descriptor`.

The top-level descriptor can validly be either an image manifest or an image index/manifest list. Manager therefore validates the descriptor by media type rather than assuming one container packaging shape. Accepted media types are limited to OCI image manifests/indexes and Docker distribution v2 image manifests/manifest lists.

Manager requires the descriptor digest to equal `containerimage.digest`, validates a positive descriptor size, and checks the descriptor's `config.digest` annotation against the exact loaded image config when the annotation is present.

The minimized accepted result is written to:

`security-artifacts/goreecloud-manager-oci-build-identity.json`

### Registry distribution digest

A Buildx distribution descriptor digest is **not** proof that an image has been published to a registry. A future approved publication workflow must capture the immutable digest reported by the approved registry for the published artifact and document how that registry object relates to the accepted CI build output.

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

The security image build uses Buildx with `--load` so the exact loaded image continues through the existing Trivy SBOM and vulnerability-scan path.

Raw Buildx metadata is written only to the GitHub Actions runner temporary directory. `BUILDX_METADATA_PROVENANCE=disabled` is set because Manager currently needs only the digest and descriptor fields required to bind the exact build output; it does not retain an unnecessary raw Buildx provenance payload.

`scripts/oci_build_identity.py` validates the raw metadata and retains only:

- exact source revision and repository identity
- exact CI image reference
- exact loaded Docker image/config digest
- exact Buildx distribution descriptor digest
- descriptor digest, kind, media type, and size
- required OCI labels
- any repository digests already visible to the local image
- explicit negative publication/deployment/production claims

The raw Buildx metadata itself is not uploaded as a security artifact.

## Release-provenance evidence

CI also generates:

`security-artifacts/goreecloud-manager-release-provenance.json`

The existing release-provenance record hashes the OCI build-identity JSON alongside the other security evidence. That binds the distribution descriptor identity into the same retained evidence chain as:

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

The relevant CI evidence gate fails on any short/malformed source revision or SHA-256 digest; missing/incorrect OCI labels; source-revision mismatch; unexpected image reference; Buildx config digest differing from the loaded Docker image ID; descriptor digest differing from `containerimage.digest`; unsupported non-image descriptor media type; malformed descriptor size or annotations; changed identity evidence; missing/duplicate/changed source or security-evidence files; malformed provenance; or any positive claim of registry publication, deployment, target-environment readiness, or production approval.

The final `always()` enforcement step treats any evidence-stage failure as CI failure while still permitting unaffected diagnostic evidence to be retained.

## Rejected first candidate

The first PR #48 candidate assumed that the Buildx top-level descriptor must always be a single image manifest. CI rejected that candidate at the fail-closed identity boundary. The application test suite and existing security evidence remained green, but the new OCI identity and dependent release-provenance stages correctly failed.

The contract was corrected to model the Buildx top-level distribution descriptor accurately: an accepted result may be an image manifest or an image index/manifest list, but it must remain an explicitly recognized image-distribution media type with an exact digest and valid relationship to the loaded image config.

No waiver, bypass, or production change was used.

## Retention

The OCI build-identity JSON and release-provenance JSON are uploaded inside the existing `manager-supply-chain-security-<source-revision>` artifact retained for 30 days.

Manager does not add another permanent readiness workflow solely for artifact identity. The existing six permanent exact-revision readiness workflows remain the source-side acceptance boundary.

## Future deployment-artifact acceptance

A future approved publication and deployment flow should:

1. Build from the exact accepted source revision.
2. Preserve the OCI source/revision labels.
3. Record the exact loaded Docker image/config digest.
4. Record and verify the exact Buildx distribution descriptor digest from the same build.
5. Generate and verify the retained OCI build-identity and release-provenance records.
6. Publish only through an approved registry or artifact channel.
7. Capture the immutable registry-reported digest/reference.
8. Verify the published artifact is traceably derived from the accepted build.
9. Deploy by immutable digest rather than mutable tag alone.
10. Record the deployed digest in target-environment evidence.
11. Preserve the previous accepted digest for rollback evidence.

This follows the GoreeCloud Docker Image Pinning Standard preference for digest-controlled critical and internally built images.

## Repository-governance dependency

During this increment, GitHub `main` was independently observed as unprotected. GitHub issue #47 tracks the separate repository-setting requirement to require pull requests and the six permanent readiness checks and to block force pushes and branch deletion. This document does not claim repository protection is already enabled.

## Production boundary

This contract does not create/rotate credentials, publish an image, create a registry/release, modify production Docker state, change DNS/Caddy/NetBird/firewall/backup/monitoring/alerting, deploy or restart Manager, satisfy any of the 28 target-environment production-readiness categories, or change the `not-approved` production boundary.

Its role remains source-side: make the accepted source, exact CI image/config digest, Buildx distribution descriptor digest, and retained security evidence cryptographically traceable to one another before any future publication or deployment is authorized.
