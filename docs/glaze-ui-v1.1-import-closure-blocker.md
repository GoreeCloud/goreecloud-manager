# GoreeCloud Manager — GLAZE UI V1.1 Import-Closure Blocker

## Status

**Current consumer state:** Blocked  
**Pinned published release:** GLAZE UI V1.1 / `1.1.0`  
**Pinned immutable revision:** `15cc76d2bcd4065552dc31c77145b63f34d9e7b2`  
**Corrective upstream work:** `GoreeCloud/goreecloud-glaze-ui` PR #129, `1.1.1-rc.1` Release Candidate preparation

This record is a current dependency blocker, not a replacement for `docs/glaze-ui.md` and not a Glaze release authority.

## Verified defect

Manager's committed V1.1 vendor graph is byte-identical to the published `v1.1.0` source identities. That exact graph contains this transitive dependency in `glaze-v1.components.css`:

`@import url("./glaze-v1.candidate.css");`

`glaze-v1.candidate.css` is not present in the immutable published V1.1 web graph. The reset already carried the required inherited foundation forward as `glaze-v1.foundation.css`, and the official entrypoint loads that foundation before the component layer.

Manager must not invent, recreate, or locally patch a competing Candidate foundation to make the build pass.

## Current failure boundary

Django static collection traverses CSS references. On Manager PR #90 exact head `d19b472334af5412af8fc8f5f02e23fc5624e177`, `collectstatic` fails before Django checks/tests because the immutable vendored graph refers to the missing file.

This is a dependency-integrity failure and must remain fail closed. Removing the reference only inside Manager would create a local fork whose bytes no longer match the locked canonical release.

## Consumer hardening

`scripts/vendor_glaze_v1_1.py` validates the complete transitive local CSS import closure before mutating Manager's committed vendor directory. It rejects missing imports, remote imports, root-absolute imports, query/fragment imports, root escapes, unsafe source files, and cycles, in addition to verifying all locked Git blob identities.

This ensures future vendoring cannot accept a byte-perfect but dependency-incomplete design-system release.

## Upstream repair boundary

GLAZE UI PR #129 removes the stale import at the canonical source, adds fail-closed recursive import-closure validation, and identifies the intended correction as `1.1.1`. Its exact candidate head has passed current Glaze repository source and rendered checks, but it remains Release Candidate preparation and does not make `1.1.1` Stable.

Manager must remain pinned to published immutable authority until a corrected Stable release exists.

## Required continuation

Before Manager may claim current Glaze conformance:

1. publish a governed corrected immutable GLAZE UI Stable release without rewriting or moving `v1.1.0`;
2. update Manager's Glaze lock to that new release identity and exact source blobs;
3. re-vendor only through the import-closure and blob-integrity gate;
4. rerun exact-head Manager CI and readiness workflows;
5. complete Manager-specific authenticated rendered-browser, accessibility, supported-client/device, and production deployed-byte acceptance.

Passing Platform Contract validation or preserving source markup does not bypass this dependency gate.

## Authority boundary

GLAZE UI remains presentation authority only. This blocker does not transfer Identity, Wardveil Security, Privacy Shield, Everkeep, Mesh, Manager operational, deployment, or production authority.
