# GoreeCloud Manager Release Provenance

## Purpose

This document defines the source-side release-provenance and deployment-artifact identity contract for GoreeCloud Manager. The accepted design binds an exact Git source revision to two outputs emitted by one exact Buildx build: the Docker image loaded locally for security/runtime validation and an OCI image-layout artifact whose manifest, config, and layers are independently hash-validated.

This improves release traceability and prepares a future immutable deployment selector. It does **not** publish Manager, create a registry release, authorize production, or satisfy target-environment production-readiness evidence.

## Governing identity chain

Accepted source-side evidence uses this chain:

`exact Git revision -> OCI revision/source labels -> one Buildx build -> loaded Docker image ID + OCI image layout -> verified OCI manifest digest -> SBOM/vulnerability evidence -> retained release provenance`

These identities have different meanings and must not be conflated.

### Git source revision

CI checks out and builds the exact forty-character pull-request head or push SHA. The source revision is passed into the image build and must match the image's `org.opencontainers.image.revision` label.

### Digest-pinned BuildKit builder

The OCI exporter is not available through Docker's default `docker` Buildx driver. CI therefore creates a temporary `docker-container` builder specifically for the supply-chain build.

The builder image is pinned by readable tag and immutable digest:

`moby/buildkit:buildx-stable-1@sha256:2f5adac4ecd194d9f8c10b7b5d7bceb5186853db1b26e5abd3a657af0b7e26ec`

The temporary builder is bootstrapped before use and removed at the end of the build step. A future refresh must verify the current stable BuildKit image from the official Docker image source, update the tag/digest together, and rerun all exact-head evidence gates. A mutable BuildKit tag without a digest is not accepted.

### One build, two outputs

The exact candidate build uses the digest-pinned `docker-container` builder and emits two outputs from the same BuildKit execution:

1. `--load` stores the image in the local Docker engine under the exact CI reference so Trivy, Docker inspection, and the established container-security evidence operate on the same candidate.
2. `--output type=oci,dest=<runner-temp>,oci-mediatypes=true` writes an OCI image-layout tarball to runner-temporary storage.

`--provenance=false` is deliberate for this artifact path so the OCI index contains only the intended image manifest rather than adding an attestation descriptor. GoreeCloud's separate release-provenance evidence remains authoritative for this source-side contract.

No `push=true` output is used. No registry is contacted for publication.

### Loaded Docker image identity

After the build completes, CI independently inspects the local image and records its `sha256:` Docker image ID. The image ID is the digest of the image configuration object.

### Real OCI image-manifest identity

`scripts/oci_build_identity.py` opens the OCI layout tarball without extracting paths to the filesystem and validates the actual OCI structures and blobs.

The validator requires:

- `oci-layout` with image-layout version `1.0.0`.
- `index.json` with schema version 2.
- Exactly one image-manifest descriptor in the index.
- OCI image-manifest media type.
- A valid manifest SHA-256 digest and positive manifest size.
- The referenced manifest blob to exist, match the descriptor byte size, and hash exactly to the descriptor digest.
- Manifest schema version 2.
- A valid config descriptor whose digest equals the independently inspected loaded Docker image ID.
- The referenced config blob to exist and match its declared size and SHA-256.
- A non-empty OCI layer list.
- Every layer descriptor to have an OCI layer media type, valid SHA-256 digest, and positive size.
- Every referenced layer blob to exist and match its declared size and SHA-256.

The manifest digest is therefore calculated from and verified against the real distributable OCI manifest bytes, not inferred from Buildx console metadata.

### Retained OCI evidence

CI retains two minimized OCI evidence files:

- `security-artifacts/goreecloud-manager-oci-build-identity.json`
- `security-artifacts/goreecloud-manager-oci-manifest.json`

The identity JSON records the exact source revision, digest-pinned builder image, two-output build model, loaded Docker image ID, OCI manifest digest, OCI config digest, manifest/config sizes, layer count and aggregate layer bytes, required OCI labels, and explicit negative publication/deployment/production claims.

The retained manifest file contains the exact raw OCI manifest bytes. Its SHA-256 must equal the `manifest_digest` in the identity JSON. This gives future publication/deployment tooling a concrete immutable source-side manifest identity rather than only a descriptive metadata record.

The OCI layout tarball itself remains runner-temporary and is deleted after generation and verification. This keeps the retained artifact focused on the minimum evidence required for identity and audit while the full candidate image remains reproducible from the accepted source, pinned base image, locked dependencies, and pinned builder.

### Registry distribution digest

The verified source-side OCI manifest digest is **not** proof that an image has been published to a registry. A future approved publication workflow must capture the immutable digest reported by the approved registry and verify how the published object relates to the accepted source-side manifest.

No registry publication is performed by this workflow.

## Source and image labels

Accepted CI builds pass the full Manager source revision into the Docker build as `MANAGER_SOURCE_REVISION`.

The image records:

- `org.opencontainers.image.title=GoreeCloud Manager`
- `org.opencontainers.image.source=https://github.com/GoreeCloud/goreecloud-manager`
- `org.opencontainers.image.revision=<exact 40-character Git SHA>`
- `org.opencontainers.image.licenses=MIT`
- `org.opencontainers.image.vendor=GoreeCloud`

The Dockerfile intentionally defaults `MANAGER_SOURCE_REVISION` to `local` so ordinary developer builds remain usable without pretending to be accepted release candidates.

## Privacy and evidence minimization

The OCI archive is never uploaded. The temporary BuildKit builder is removed after the build. The retained identity contains no credentials, Docker daemon state, raw runner environment, or unnecessary provider metadata.

Identity validation uses static diagnostic codes instead of dynamic exception strings. Representative codes include `builder-image-not-digest-pinned`, `oci-index-manifest-count-invalid`, `oci-manifest-hash-mismatch`, `oci-config-loaded-image-mismatch`, `oci-config-hash-mismatch`, `oci-layer-hash-mismatch`, `retained-oci-manifest-hash-mismatch`, and `loaded-image-contract-invalid`.

These codes identify a failed invariant without copying raw artifact contents or provider error details into the log.

## Release-provenance evidence

CI also generates:

`security-artifacts/goreecloud-manager-release-provenance.json`

The existing release-provenance record hashes both OCI evidence files alongside the other security evidence. The retained evidence set therefore binds the exact source revision and loaded image to:

- OCI build-identity JSON.
- Exact raw OCI manifest JSON.
- Python CycloneDX SBOM.
- OSV Python vulnerability report.
- Container-image CycloneDX SBOM.
- Trivy Debian operating-system vulnerability report.
- Container operating-system vulnerability policy summary.

The current source materials recorded by release provenance remain `Dockerfile`, `requirements.txt`, and `requirements.lock`.

## Fail-closed verification

OCI build-identity generation and verification are separate operations. Release-provenance generation and verification remain separate operations as well.

The OCI identity gate fails on malformed source or builder identity, unexpected loaded-image labels/reference, malformed OCI layout/index/manifest/config/layer structure, any missing blob, any size mismatch, any SHA-256 mismatch, manifest-config versus loaded-image mismatch, altered retained manifest bytes, or a changed identity record.

Release provenance separately fails on missing, duplicate, changed, or malformed source/security evidence or any positive deployment/production claim.

The final `always()` enforcement step treats any evidence-stage failure as CI failure while still allowing unaffected diagnostic evidence to be retained.

## Rejected candidates during implementation

PR #48 deliberately kept failed or semantically insufficient candidates unaccepted.

The first frozen candidate, `259f68e115a712419920c2a449ebed48dac60682`, encoded Buildx metadata too narrowly. CI #103 rejected the new identity boundary and dependent release provenance. Existing application tests and security scanning remained green. No waiver or bypass was used.

The second candidate, `61e63efd1be5fc603f38e96d41bc7cbfa4d72ee9`, corrected that model but still failed CI #106. The full Django suite passed 171 tests and the other five permanent readiness workflows passed, but the OCI identity and dependent provenance stages remained unestablished. The diagnostic boundary was strengthened with static non-secret reason codes.

The third candidate, `a6238e0b11e497c0783d61f3e0f2e0dcff660f0b`, passed CI #110 mechanically. Direct inspection of retained artifact `9243506309`, however, showed the default Docker-exporter path merely repeated the local image/config digest as `containerimage.digest` and emitted no distribution descriptor. The artifact did not support the stronger immutable-manifest claim, so the candidate was rejected despite green CI. This directly applies the GoreeCloud File Validation rule that successful execution is not sufficient evidence of artifact identity or fitness.

The fourth candidate, `a5715c366b8f4315acf641314b2a407eef5f502f`, changed the default Docker-driver exporter to `type=image,push=false,oci-mediatypes=true`. CI #114 still rejected the identity boundary with the safe reason code `buildx-distribution-descriptor-missing`. The application suite passed 174 tests and the existing Python/container security layers remained healthy, but the default Docker driver still did not expose the required distribution descriptor in this runner configuration. No waiver was added.

The accepted design therefore no longer relies on default-driver Buildx metadata for the distribution identity. It uses the OCI exporter through a digest-pinned `docker-container` builder and validates the actual OCI artifact bytes.

No rejected candidate is accepted Manager state.

## Retention

The accepted OCI build-identity JSON, raw OCI manifest JSON, release-provenance JSON, SBOMs, and vulnerability evidence are uploaded inside the existing:

`manager-supply-chain-security-<source-revision>`

artifact retained for 30 days.

Manager does not add another permanent readiness workflow solely for artifact identity. The existing six permanent exact-revision readiness workflows remain the source-side acceptance boundary.

## Future deployment-artifact acceptance

A future separately approved publication and deployment flow should:

1. Build from the exact accepted source revision.
2. Preserve the OCI source/revision labels.
3. Use the accepted digest-pinned builder or an explicitly reviewed successor.
4. Reproduce and validate the OCI image-layout contract.
5. Require the OCI manifest config digest to equal the loaded image ID.
6. Require the retained manifest file hash to equal the accepted OCI manifest digest.
7. Verify release provenance hashes the same OCI identity and manifest evidence.
8. Publish only through an approved registry or artifact channel.
9. Capture the immutable registry-reported digest/reference.
10. Verify the published artifact is traceably derived from the accepted source-side manifest.
11. Deploy by immutable digest rather than mutable tag alone.
12. Record the deployed digest in target-environment evidence.
13. Preserve the previous accepted digest for rollback evidence.

This follows the GoreeCloud Docker Image Pinning Standard preference for digest-controlled critical and internally built images.

## Repository-governance dependency

During this increment, GitHub `main` was independently observed as unprotected. GitHub issue #47 tracks the separate repository-setting requirement to require pull requests and the six permanent readiness checks and to block force pushes and branch deletion. This document does not claim repository protection is already enabled.

## Production boundary

This contract does not create or rotate credentials, publish an image, create a registry/release, modify production Docker state, change DNS/Caddy/NetBird/firewall/backup/monitoring/alerting, deploy or restart Manager, satisfy any of the 28 target-environment production-readiness categories, or change the `not-approved` production boundary.

Its role remains source-side: make the accepted source, exact loaded image identity, real OCI manifest identity, and retained security evidence cryptographically traceable to one another before any future publication or deployment is authorized.
