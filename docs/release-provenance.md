# GoreeCloud Manager Release Provenance

## Purpose

This document defines the source-side release-provenance and deployment-artifact identity contract for GoreeCloud Manager. The contract binds an exact Git source revision to the exact image identity emitted by Buildx, the exact image loaded and scanned by Docker, a real OCI/Docker image-distribution descriptor emitted by that same non-publishing build, and the retained software-supply-chain evidence.

This improves release traceability and prepares a future immutable deployment selector. It does **not** publish Manager, create a registry release, authorize production, or satisfy target-environment production-readiness evidence.

## Governing identity chain

Accepted source-side evidence uses this chain:

`exact Git revision -> OCI revision/source labels -> Buildx image ID -> loaded Docker image ID -> Buildx image-distribution descriptor digest -> SBOM/vulnerability evidence -> retained release provenance`

These identities have different meanings and must not be conflated.

### Git source revision

CI checks out and builds the exact forty-character pull-request head or push SHA.

### Buildx image ID and loaded Docker image ID

CI uses Buildx's dedicated `--iidfile` output to capture the image ID emitted by the exact build operation. After the image exporter stores the result in Docker's local image store, Docker independently reports the image ID through `docker image inspect`.

Manager requires these two `sha256:` identities to match exactly. Buildx metadata may also expose `containerimage.config.digest`; when present, that optional cross-check must equal the same image identity.

### Buildx image-distribution descriptor digest

The security image uses the default Docker-driver **image exporter** with:

`type=image,name=<exact CI reference>,push=false,oci-mediatypes=true`

Docker documents that the image exporter writes the build result as a container image or manifest list, that the image appears in `docker images` when using the Docker driver, and that `push=false` is the default/non-publishing behavior. OCI media types are requested explicitly so the distribution evidence is aligned with the OCI model.

The same build writes Buildx metadata. Manager requires:

- a valid `containerimage.digest` SHA-256 value
- a `containerimage.descriptor` JSON object
- descriptor digest equal to `containerimage.digest`
- a recognized OCI/Docker image manifest or image index/manifest-list media type
- a positive descriptor size

This is deliberately stricter than merely accepting a digest-shaped value. The retained evidence must prove that Buildx actually emitted an image-distribution descriptor, not just repeat the local image/config digest.

The minimized accepted result is written to:

`security-artifacts/goreecloud-manager-oci-build-identity.json`

### Registry distribution digest

A Buildx image-distribution descriptor digest is **not** proof that an image has been published to a registry. A future approved publication workflow must capture the immutable digest reported by the approved registry for the published artifact and document how that registry object relates to the accepted CI distribution descriptor.

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

The security image build keeps both raw Buildx outputs only in the GitHub Actions runner temporary directory:

- metadata JSON written by `--metadata-file`
- exact image ID written by `--iidfile`

`BUILDX_METADATA_PROVENANCE=disabled` is set because Manager currently needs only the build-output identity fields required for this source-side contract; it does not retain an unnecessary raw Buildx provenance payload.

`scripts/oci_build_identity.py` validates the temporary inputs and retains only:

- exact source revision and repository identity
- exact CI image reference
- exact Buildx image ID
- exact loaded Docker image ID
- optional matching Buildx config digest
- exact Buildx image-distribution descriptor digest
- descriptor kind, media type, and size
- required OCI labels
- any repository digests already visible to the loaded image
- explicit negative publication/deployment/production claims

Neither raw Buildx temporary file is uploaded as a security artifact.

## Safe fail-closed diagnostics

Identity validation uses static diagnostic codes instead of raw exception messages. This makes a failed CI contract actionable without printing dynamic metadata, provider responses, or unnecessary paths.

Representative codes include `buildx-image-id-invalid`, `buildx-loaded-image-id-mismatch`, `buildx-config-image-id-mismatch`, `buildx-distribution-digest-invalid`, `buildx-distribution-descriptor-missing`, `buildx-descriptor-digest-mismatch`, `buildx-descriptor-media-type-unsupported`, `loaded-image-contract-invalid`, and `identity-record-mismatch`.

## Release-provenance evidence

CI also generates:

`security-artifacts/goreecloud-manager-release-provenance.json`

The existing release-provenance record hashes the accepted OCI build-identity JSON alongside the other security evidence. That binds the distribution descriptor into the same retained evidence chain as:

- Python CycloneDX SBOM
- OSV Python vulnerability report
- container-image CycloneDX SBOM
- Trivy Debian operating-system vulnerability report
- container operating-system vulnerability policy summary

The current source materials recorded by release provenance remain `Dockerfile`, `requirements.txt`, and `requirements.lock`.

## Fail-closed verification

OCI build-identity generation and verification are separate operations. Release-provenance generation and verification remain separate operations as well.

The identity gate fails on malformed source or digest identity, Buildx/loaded image mismatch, optional config-digest mismatch, missing/malformed distribution digest, missing or inconsistent distribution descriptor, unsupported non-image descriptor media type, OCI-label/source mismatch, unexpected image reference, or changed identity evidence. Release provenance separately fails on missing, duplicate, changed, or malformed source/security evidence or any positive deployment/production claim.

The final `always()` enforcement step treats any evidence-stage failure as CI failure while still permitting unaffected diagnostic evidence to be retained.

## Rejected candidates during implementation

PR #48 deliberately kept failed or semantically insufficient candidates unaccepted.

The first frozen candidate, `259f68e115a712419920c2a449ebed48dac60682`, encoded the Buildx descriptor too narrowly. CI #103 rejected the candidate at the new identity boundary and dependent release provenance also failed. Existing application tests and security scanning remained green. No waiver or bypass was used.

The second candidate, `61e63efd1be5fc603f38e96d41bc7cbfa4d72ee9`, corrected the descriptor model but still failed CI #106. The full Django suite passed (171 tests), all five other permanent readiness workflows passed, and existing security layers passed, but the OCI identity and dependent provenance stages failed. The contract was improved to use Buildx's dedicated `--iidfile` output and static non-secret reason codes.

The third candidate, `a6238e0b11e497c0783d61f3e0f2e0dcff660f0b`, passed CI #110's mechanical identity/provenance checks, but direct inspection of retained artifact `9243506309` showed that the default Docker-exporter path emitted `containerimage.digest` equal to the image/config ID and emitted no distribution descriptor. The artifact therefore did **not** support the stronger claim this increment is intended to establish. The candidate was rejected despite green CI, demonstrating the GoreeCloud File Validation requirement that successful execution alone is not sufficient evidence of artifact identity or fitness.

The build contract was then changed to the Docker-driver image exporter with `push=false,oci-mediatypes=true`, and the validator was tightened to require a real distribution descriptor before acceptance.

No rejected candidate is accepted Manager state.

## Retention

The accepted OCI build-identity JSON and release-provenance JSON are uploaded inside the existing `manager-supply-chain-security-<source-revision>` artifact retained for 30 days.

Manager does not add another permanent readiness workflow solely for artifact identity. The existing six permanent exact-revision readiness workflows remain the source-side acceptance boundary.

## Future deployment-artifact acceptance

A future approved publication and deployment flow should:

1. Build from the exact accepted source revision.
2. Preserve the OCI source/revision labels.
3. Require the Buildx `--iidfile` identity to equal the loaded Docker image ID.
4. Record and verify the exact Buildx image-distribution descriptor digest from the same build.
5. Generate and verify retained OCI build-identity and release-provenance records.
6. Publish only through an approved registry or artifact channel.
7. Capture the immutable registry-reported digest/reference.
8. Verify the published artifact is traceably derived from the accepted distribution descriptor.
9. Deploy by immutable digest rather than mutable tag alone.
10. Record the deployed digest in target-environment evidence.
11. Preserve the previous accepted digest for rollback evidence.

This follows the GoreeCloud Docker Image Pinning Standard preference for digest-controlled critical and internally built images.

## Repository-governance dependency

During this increment, GitHub `main` was independently observed as unprotected. GitHub issue #47 tracks the separate repository-setting requirement to require pull requests and the six permanent readiness checks and to block force pushes and branch deletion. This document does not claim repository protection is already enabled.

## Production boundary

This contract does not create or rotate credentials, publish an image, create a registry/release, modify production Docker state, change DNS/Caddy/NetBird/firewall/backup/monitoring/alerting, deploy or restart Manager, satisfy any of the 28 target-environment production-readiness categories, or change the `not-approved` production boundary.

Its role remains source-side: make the accepted source, exact Buildx image identity, exact loaded image identity, real Buildx distribution descriptor digest, and retained security evidence cryptographically traceable to one another before any future publication or deployment is authorized.
