# Container Image Security Evidence

## Purpose

GoreeCloud Manager validates the operating-system package layer of the exact container image built from an accepted source revision. This evidence complements, rather than replaces, the deterministic Python dependency SBOM and OSV policy defined in `docs/software-supply-chain.md`.

This source/disposable validation does not inspect a production host, approve production deployment, or satisfy any target-environment production-readiness evidence category.

## Evidence identity

For pull requests, every permanent Manager workflow checks out:

```text
github.event.pull_request.head.sha
```

For `main` pushes, the workflows check out:

```text
github.sha
```

The expression is source-controlled as:

```text
${{ github.event.pull_request.head.sha || github.sha }}
```

This is an execution-integrity requirement, not merely an artifact-labeling convention. GitHub pull-request workflows otherwise default to a temporary merge ref, which is not the immutable pull-request head. Manager requires the code executed by every permanent gate to be the same revision named by its acceptance evidence.

The CI security artifact additionally records:

- the exact 40-character Manager source revision;
- the locally built image reference;
- the locally built Docker image ID;
- the exact digest-pinned Python base-image reference;
- the Trivy version used;
- the SHA-256 of the raw Trivy vulnerability report.

## Scanner acquisition

CI uses Aqua Security Trivy `0.74.0`.

Manager does not use a floating Trivy installer or a mutable `trivy-action` tag. CI downloads the official Linux amd64 release archive from the fixed `v0.74.0` GitHub release and verifies the archive before execution with this source-controlled SHA-256:

```text
2ae6fe3ee734b7fdf11335663e18c75ea12dccc76062f09f164a3b0f8be4371a
```

If download, checksum verification, extraction, or execution fails, CI fails closed.

The selected scanner version and checksum are maintenance inputs. They must be deliberately reviewed and updated together rather than automatically following a moving release.

Trivy telemetry and version checks are disabled for these evidence runs. The vulnerability database remains intentionally current because the purpose of the gate is to evaluate the accepted image against current known operating-system security information.

## Exact image build

CI builds the Manager Dockerfile from the exact checked-out source revision and assigns a disposable local tag containing that source SHA.

The Dockerfile remains authoritative for the runtime base image. At the time this contract was created, the base image is:

```text
python:3.14.6-slim@sha256:cea0e6040540fb2b965b6e7fb5ffa00871e632eef63719f0ea54bca189ce14a6
```

The security evaluator rejects a Dockerfile that does not use the expected patch-tagged, SHA-256-pinned Python slim form.

The scan targets the final built Manager image, not only the upstream base image. This ensures that the evidence covers the operating-system packages actually present after the Manager Docker build completes.

## Container CycloneDX SBOM

CI generates a Trivy CycloneDX JSON SBOM for the built image and stamps its metadata with GoreeCloud-specific evidence identity:

- exact source revision;
- scope `built-container-image`;
- disposable image reference;
- local image ID;
- exact base-image reference and digest;
- scanner name and version.

The resulting file is:

```text
security-artifacts/goreecloud-manager-image.cdx.json
```

The image SBOM is intentionally separate from `goreecloud-manager-python.cdx.json`. The Python SBOM is derived deterministically from the hash lock and proves the approved Python dependency graph. The image SBOM inventories the assembled container image and may include both operating-system and language packages discovered by Trivy.

## Operating-system vulnerability scan

CI runs Trivy against the built image with the vulnerability scanner restricted to operating-system packages:

```text
--scanners vuln
--pkg-types os
--vuln-severity-source debian
```

The complete JSON result is preserved as:

```text
security-artifacts/trivy-container-os-vulnerabilities.json
```

Manager does not use `--ignore-unfixed`. Unfixed findings remain visible in evidence instead of disappearing from the report.

CI also uses Trivy's end-of-life enforcement. If the detected operating-system release is end-of-life, the scan step fails and the final evidence gate rejects the candidate.

### Distribution-authoritative severity

The current Manager image is Debian-based. The acceptance gate therefore requires Debian to be the severity authority for Debian operating-system packages.

This is deliberate. Trivy can fall back to severity values from NVD or another vendor when the target distribution has not assigned a severity. That fallback is useful for broad visibility, but it can make a Debian package appear `HIGH` or `CRITICAL` even when Debian has assigned no corresponding severity or has explicitly classified the issue as minor/no-DSA.

The first disposable candidate for this control demonstrated that difference: the default Trivy severity selection produced 23 `HIGH`/`CRITICAL` findings, but none of those blocking severities came from Debian. The candidate was rejected rather than waived. The evidence contract was then corrected to request Debian severity explicitly.

With `--vuln-severity-source debian`:

- a Debian-assigned severity is retained with `SeveritySource=debian`;
- if Debian has not assigned a severity, Trivy reports the finding as `UNKNOWN` rather than substituting another vendor or NVD severity;
- the finding itself remains in the report, including affected/fixed state and package identity;
- the Manager evaluator rejects any non-`UNKNOWN` finding whose severity source is not Debian;
- the evaluator also rejects an unexpected non-Debian OS result.

This choice does not redefine an `UNKNOWN` issue as safe. It means the automated blocking threshold is based on the security authority responsible for the installed Debian package while unscored issues remain visible for review and future reclassification.

## Acceptance policy

`security/trivy-container-policy.json` is the source-controlled acceptance policy.

The current default is:

- the expected OS distribution is `debian`;
- the required severity authority is `debian`;
- Debian-assessed `HIGH` findings block;
- Debian-assessed `CRITICAL` findings block;
- `UNKNOWN`, `LOW`, and `MEDIUM` findings remain visible but do not automatically block;
- at least one Trivy `os-pkgs` result is required so a misconfigured or incomplete scan cannot be mistaken for zero findings.

A Debian-assessed `HIGH` or `CRITICAL` finding blocks whether or not Debian currently publishes a fixed version. An unavailable patch is not treated as evidence that the risk is acceptable. If such a finding cannot yet be remediated, acceptance requires an explicit, reviewable exception.

## Exceptions

A container vulnerability exception must match both:

- the exact vulnerability identifier; and
- the exact normalized operating-system package name.

Every exception must also include:

- an ISO `YYYY-MM-DD` expiration date;
- a non-empty reason.

Wildcard exceptions are not supported. Duplicate exceptions are rejected. Expired exceptions fail policy validation even if the current scan contains no matching vulnerability.

The repository begins with an empty exception list.

## Sanitized Manager summary

`scripts/container_supply_chain_security.py` converts the Trivy report into a stable Manager-owned evidence summary:

```text
security-artifacts/manager-container-os-vulnerability-summary.json
```

The summary records only security-relevant package identity and classification fields, including vulnerability ID, package, installed version, fixed version when available, status, severity, severity source, and distribution.

It deliberately omits long vulnerability descriptions and raw scanner exception details.

A processing failure writes a sanitized error report containing only a safe error type and a statement that evidence could not be established.

## Evidence-preserving fail-closed behavior

Scanner-related CI steps use `continue-on-error` only so that:

- the remaining Django validation can still run;
- any evidence already generated can still be uploaded;
- a failure artifact can remain available for review.

This does not permit acceptance.

The final `always()` enforcement step separately checks the outcomes of:

- Python OSV evidence;
- checksum-pinned Trivy installation;
- exact Manager image build;
- container CycloneDX SBOM generation;
- Trivy operating-system scan;
- Manager container vulnerability policy evaluation.

Any failed outcome makes CI fail.

## Artifact retention

The existing Manager supply-chain artifact now contains both dependency layers and is retained for thirty days:

- deterministic Python CycloneDX SBOM;
- OSV Python vulnerability report;
- built-container CycloneDX SBOM;
- raw Trivy operating-system vulnerability report;
- sanitized Manager container vulnerability summary.

The artifact name is bound to the exact source revision.

## Maintenance procedure

For a Trivy update:

1. select an official immutable Trivy release;
2. obtain the official Linux amd64 release asset;
3. independently verify the asset digest from authoritative release metadata;
4. update the version and SHA-256 together in CI;
5. run the container-security regression suite;
6. inspect the generated evidence;
7. run all six permanent workflows against the exact candidate head.

For a base-image update:

1. retain the readable Python patch tag and immutable image digest together;
2. build the exact candidate image;
3. generate both SBOM layers;
4. run both Python and operating-system vulnerability policies;
5. review new findings rather than weakening the policy simply to make CI green;
6. run runtime, restore, rollback, monitoring, and manifest gates against that same exact source revision.

For an `UNKNOWN` Debian finding:

1. retain it in the raw and sanitized evidence;
2. inspect Debian Security Tracker status and notes when it is material to acceptance;
3. do not invent a Debian severity from a different distribution or NVD;
4. allow future CI runs to pick up a later Debian severity or fixed-version classification automatically;
5. escalate to a source-controlled exception only if Debian later classifies the issue as blocking and a temporary, explicit risk acceptance is justified.

## Scope and limitations

This evidence covers:

- the source-controlled Manager Dockerfile;
- the exact disposable image built by CI;
- packages detected in that image by Trivy;
- current Trivy vulnerability-database knowledge;
- Debian-authoritative severity selection for the Debian image.

It does not prove that:

- an undisclosed vulnerability does not exist;
- a vulnerability database is complete;
- an `UNKNOWN` finding is harmless;
- a production host is patched;
- a production Docker daemon is configured safely;
- the image deployed in production matches this disposable CI image;
- target-environment network, secret, backup, monitoring, or recovery controls are valid.

Those remain separate production-readiness evidence requirements.

## Production boundary

This increment does not:

- deploy or replace a production Manager image;
- pull or rebuild Manager on a production host;
- change production Docker, Compose, Caddy, DNS, NetBird, firewall, or port state;
- create or rotate production credentials;
- create monitoring, notification, or backup resources;
- mark a target-environment evidence category satisfied;
- approve production activation.

The production-readiness manifest remains authoritative. Production stays `not-approved` until the separately governed target-environment evidence and approval requirements are completed.
