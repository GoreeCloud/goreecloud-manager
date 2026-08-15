# GoreeCloud Manager Release Provenance

## Purpose

This document defines the source-side release-provenance and deployment-artifact identity contract for GoreeCloud Manager. The contract binds an exact Git source revision to the exact image identity emitted by Buildx, the exact image loaded and scanned by Docker, the immutable OCI/Docker distribution digest emitted by that same build, and the retained software-supply-chain evidence.

This improves release traceability and prepares a future immutable deployment selector. It does **not** publish Manager, create a registry release, authorize production, or satisfy target-environment production-readiness evidence.

## Governing identity chain

Accepted source-side evidence uses this chain:

`exact Git revision -> OCI revision/source labels -> Buildx image ID -> loaded Docker image ID -> Buildx distribution digest -> SBOM/vulnerability evidence -> retained release provenance`

These identities have different meanings and must not be conflated.

### Git source revision

CI checks out and builds the exact forty-character pull-request head or push SHA.

### Buildx image ID and loaded Docker image ID

CI builds with `docker buildx build --load` and uses Buildx's dedicated `--iidfile` output to capture the image ID emitted by the exact build operation. After loading the image, Docker independently reports the image ID through `docker image inspect`.

Manager requires these two `sha256:` identities to match exactly. This provides an explicit same-build binding before the image continues through SBOM and vulnerability analysis.

Buildx metadata may also expose `containerimage.config.digest`. When that optional field is present, Manager requires it to match the same Buildx/loaded image identity. Absence of that optional metadata field does not invalidate the dedicated `--iidfile` identity path.

### Buildx distribution digest

The same build writes a Buildx metadata file. Manager requires a valid `containerimage.digest` SHA-256 value from that same operation.

If `containerimage.descriptor` is present, Manager additionally validates that its digest equals `containerimage.digest`, its size is positive, and its media type is one of the recognized OCI/Docker image-distribution manifest or index/list types. The descriptor is treated as supplementary validated structure rather than an assumed mandatory metadata shape.

The minimized accepted result is written to:

`security-artifacts/goreecloud-manager-oci-build-identity.json`

### Registry distribution digest

A Buildx distribution digest is **not** proof that an image has been published to a registry. A future approved publication workflow must capture the immutable digest reported by the approved registry for the published artifact and document how that registry object relates to the accepted CI build output.

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

- the metadata JSON written by `--metadata-file`
- the exact image ID written by `--iidfile`

`BUILDX_METADATA_PROVENANCE=disabled` is set because Manager currently needs only the build-output identity fields required for this source-side contract; it does not retain an unnecessary raw Buildx provenance payload.

`scripts/oci_build_identity.py` validates the temporary inputs and retains only:

- exact source revision and repository identity
- exact CI image reference
- exact Buildx image ID
- exact loaded Docker image ID
- optional matching Buildx config digest
- exact Buildx distribution digest
- validated descriptor details when supplied by Buildx
- required OCI labels
- any repository digests already visible to the loaded image
- explicit negative publication/deployment/production claims

Neither raw Buildx temporary file is uploaded as a security artifact.

## Safe fail-closed diagnostics

Identity validation uses static diagnostic codes instead of raw exception messages. This makes a failed CI contract actionable without printing dynamic metadata, paths, provider responses, or other unnecessary details.

Examples include:

- `buildx-image-id-invalid`
- `buildx-loaded-image-id-mismatch`
- `buildx-config-image-id-mismatch`
- `buildx-distribution-digest-invalid`
- `buildx-descriptor-digest-mismatch`
- `buildx-descriptor-media-type-unsupported`
- `loaded-image-contract-invalid`
- `identity-record-mismatch`

The codes identify which contract failed; they do not expose protected content.

## Release-provenance evidence

CI also generates:

`security-artifacts/goreecloud-manager-release-provenance.json`

The existing release-provenance record hashes the accepted OCI build-identity JSON alongside the other security evidence. That binds the distribution identity into the same retained evidence chain as:

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

The identity gate fails on malformed source or digest identity, Buildx/loaded image mismatch, optional config-digest mismatch, missing/malformed distribution digest, inconsistent descriptor data, unsupported non-image descriptor media type, OCI-label/source mismatch, unexpected image reference, or changed identity evidence. Release provenance separately fails on missing, duplicate, changed, or malformed source/security evidence or any positive deployment/production claim.

The final `always()` enforcement step treats any evidence-stage failure as CI failure while still permitting unaffected diagnostic evidence to be retained.

## Rejected candidates during implementation

PR #48 deliberately kept failed candidates unaccepted.

The first frozen candidate, `259f68e115a712419920c2a449ebed48dac60682`, encoded the Buildx descriptor too narrowly. CI #103 rejected the candidate at the new identity boundary and therefore also rejected dependent release provenance. Existing application tests and security scanning remained green. No waiver or bypass was used.

The next candidate, `61e63efd1be5fc603f38e96d41bc7cbfa4d72ee9`, corrected the descriptor model but still failed CI #106. The OCI identity stage and dependent release-provenance stage again failed closed while the full application test suite and all five other permanent readiness workflows passed. The generic exception-only diagnostic was insufficient to identify the exact remaining metadata assumption, so the contract was further improved to use Buildx's dedicated `--iidfile` identity and static reason-coded failures.

No failed candidate is an accepted Manager revision.

## Retention

The accepted OCI build-identity JSON and release-provenance JSON are uploaded inside the existing `manager-supply-chain-security-<source-revision>` artifact retained for 30 days.

Manager does not add another permanent readiness workflow solely for artifact identity. The existing six permanent exact-revision readiness workflows remain the source-side acceptance boundary.

## Future deployment-artifact acceptance

A future approved publication and deployment flow should:

1. Build from the exact accepted source revision.
2. Preserve the OCI source/revision labels.
3. Require the Buildx `--iidfile` identity to equal the loaded Docker image ID.
4. Record and verify the exact Buildx distribution digest from the same build.
5. Generate and verify retained OCI build-identity and release-provenance records.
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

This contract does not create or rotate credentials, publish an image, create a registry/release, modify production Docker state, change DNS/Caddy/NetBird/firewall/backup/monitoring/alerting, deploy or restart Manager, satisfy any of the 28 target-environment production-readiness categories, or change the `not-approved` production boundary.

Its role remains source-side: make the accepted source, exact Buildx image identity, exact loaded image identity, Buildx distribution digest, and retained security evidence cryptographically traceable to one another before any future publication or deployment is authorized.
