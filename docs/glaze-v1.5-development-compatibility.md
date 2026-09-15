# GoreeCloud Manager — GLAZE UI V1.5 Development Compatibility

## Status

**Lifecycle:** Development  
**Integration type:** Repository-local compatibility exercise only  
**GLAZE UI Development version:** `1.5.0-dev.1`  
**Exact Glaze Development revision:** `e7c397837908e4644d6230f17d0f73e84e3d1558`  
**Manager implemented Glaze source:** V1.3 / `1.3.0`  
**Manager required current Stable Glaze target:** V1.4.1 / `1.4.1`  
**Exact current Stable Glaze authority:** `4fab9da0fad2e5c974e0e66ec88632c61745751c`

This record documents a bounded Manager compatibility exercise for the GLAZE UI V1.5 Context + Capability Resolution Layer. It does not change Manager's shipped presentation source, Platform Contract Stable target, Django runtime, browser runtime, CSS, templates, integrations, application version, lifecycle, or production state.

## Stable and migration boundary

Manager still implements its repository-local V1.3 presentation mapping. The required current Stable consumer target is V1.4.1, and substantive V1.4.1 source migration plus Manager-specific rendered, accessibility, representative-target, Human Visual Excellence, rollback, release, and production acceptance remain outstanding.

The V1.5 compatibility exercise cannot substitute for those V1.4.1 obligations. V1.5 remains Development and non-consumer-eligible, while Manager remains Development, nonconformant, and `applicable-migration-required`.

## Authority model under test

The exercise preserves authority rather than centralizing it in Glaze:

- GoreeCloud Manager retains application behavior and operational authority.
- Manager policy authority owns administrative authorization truth.
- Privacy Shield remains privacy authority.
- Wardveil Security remains security authority.
- GoreeCloud Identity remains identity authority.
- GoreeCloud Mesh remains coordination and transport authority within its governed contracts.
- Everkeep remains continuity and recovery authority.
- Glaze remains presentation-only and may not infer authorization, grant permission, invent provider precedence, navigate automatically, execute consequential actions automatically, or execute fallback actions automatically.

## Repository-local scenarios

`contracts/glaze-ui/manager-glaze-v1.5-development.json` and `scripts/validate_glaze_v1_5_development.mjs` exercise four bounded scenarios against the exact upstream representative profile `goreecloud-manager-desktop`:

1. **Restricted administration:** application refresh remains available while the policy-owned administrative capability remains restricted; the administrative destination is preserved but disabled and the consequential change action cannot execute automatically.
2. **Policy-authorized administration:** when policy explicitly reports the administrative capability as available, Glaze may enable presentation but still cannot navigate or execute the consequential action automatically.
3. **Conflicting authorization providers:** duplicate ownership of the administrative capability fails closed; Glaze does not invent provider precedence, while unrelated Manager refresh behavior remains usable.
4. **Refresh temporarily unavailable:** temporary loss of the Manager-owned refresh capability disables only refresh presentation and does not rewrite policy-owned administrative authorization state.

Across all scenarios, diagnostics must omit provider identities and raw context, local-first processing remains required, telemetry is not required, remote analysis is not required, and task/navigation continuity must be preserved.

## Validation

The dedicated `Manager Glaze V1.5 Development Compatibility` workflow:

- checks out the exact Manager PR head;
- verifies that exact revision;
- fetches exact Glaze Development revision `e7c397837908e4644d6230f17d0f73e84e3d1558` into a detached checkout;
- verifies the exact upstream revision;
- runs the repository-local V1.5 validator; and
- fails if V1.5 leaks into Manager's Platform Contract Stable requirement or if the existing V1.3 implemented-source truth is relabeled as migrated.

Manager's normal repository CI and readiness workflows remain independent required evidence for the exact PR revision. A green V1.5 compatibility workflow proves only the source-level scenarios it executes.

## Acceptance boundary

This exercise does **not** establish:

- substantive Manager V1.4.1 source migration;
- rendered or browser V1.5 adoption;
- accessibility or assistive-technology acceptance;
- representative desktop/mobile browser acceptance;
- Privacy Shield, Wardveil, Everkeep, Identity, Mesh, or other runtime acceptance;
- protected signing, release provenance, production publication, or deployment;
- Manager consumer conformance;
- Release Candidate qualification;
- Stable qualification; or
- production acceptance.

Any later V1.5 integration must be evaluated against the then-current Stable Glaze authority and normal GoreeCloud lifecycle, privacy, security, resilience, accessibility, release, and production gates.
