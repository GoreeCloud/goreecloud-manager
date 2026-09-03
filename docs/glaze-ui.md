# GoreeCloud Manager — GLAZE UI V1.0 Django-Web Consumer Contract

## Status

- **Target:** GLAZE UI V1.0 (`1.0.0`)
- **Canonical repository:** `GoreeCloud/goreecloud-glaze-ui`
- **Exact source authority:** `70909bbdccad378fb7281ae1842e2f5beed64c38`
- **Upstream lifecycle:** Official reset baseline; production acceptance pending
- **Manager consumer state:** Migration in progress
- **Scope:** Django-rendered Manager operating interface owned by this repository
- **Excluded from this acceptance unit:** desktop client, Android client, and the repository's public Manager website

This record defines the repository-local GLAZE UI V1.0 mapping for the GoreeCloud Manager Django web application. It does **not** establish Manager-wide V1 conformance, Production Stable status, release approval, deployment acceptance, or production approval. Other Manager clients remain separate migration and acceptance surfaces.

## Authority boundary

The implementation-facing authority is the canonical Glaze repository at the exact source revision above, including `VERSION`, `GLAZE_UI_V1_0.md`, `registry/lifecycle.json`, `css/glaze-v1.0.0.css`, applicable V1 component and System Shell contracts, `acceptance/v1.0-stable.md`, and `scripts/validate_glaze_v1.py`.

Manager does not create a competing design system. `core/static/core/css/glaze-ui.css` is a repository-local consumer mapping that mirrors applicable canonical `glz1` semantic roles while preserving Manager-specific information architecture, read-only operational workflows, and integration authority boundaries.

Pre-reset Glaze product versions and their acceptance evidence remain historical audit evidence only. They do not establish V1 conformance.

## Surface scope

This migration unit covers the server-rendered Django interface:

- shared application shell;
- authenticated Overview;
- GoreeCloud Tasks integration view;
- Everkeep status view;
- Privacy Shield status view;
- authentication view.

It does not claim that the Python desktop client, Android client, or static public Manager website have adopted V1. Those surfaces must be evaluated against their own implementation technology and acceptance requirements before Manager-wide adoption can be declared complete.

## V1 presentation rule

**Solid where users read or make explicit critical decisions. Glazed where users interact with transient navigation, command, search, control, or feedback chrome.**

Manager is an operational console, so durable platform state, metrics, integration details, protection information, authentication content, warnings, and critical decisions stay on Solid or Raised surfaces. The sticky application header is bounded System Overlay navigation chrome and may use Glaze material. Nested backdrop blur is suppressed.

Glaze presentation never manufactures authorization, security, privacy, backup, recovery, Identity, Mesh, health, or production-readiness state. Integrated systems remain authoritative for their own facts and permissions.

## Source structure

- `core/templates/core/base.html` — V1 application-shell classification, exact source provenance, private browser metadata, navigation, appearance control, and stable main-content landmark.
- `core/static/core/css/app.css` — Manager-specific layout and component composition.
- `core/static/core/css/glaze-ui.css` — repository-local V1 semantic mapping, material boundaries, target geometry, accessibility modes, and browser fallbacks. It loads after `app.css`.
- `core/static/core/js/theme.js` — browser-local System/Light/Dark preference with no server or third-party transmission.
- `tests/test_glaze_ui_contract.py` — fail-closed source-contract validation.
- `tests/test_glaze_ui_rendered.py` — representative real-template Chromium validation.

No remote font, icon, stylesheet, JavaScript, analytics, advertising, telemetry, tracking, or presentation dependency is introduced by this migration.

## V1 semantic mapping

The local mapping exposes the canonical V1 namespace for applicable roles, including:

- `--glz1-canvas`, `--glz1-base`, and `--glz1-raised`;
- `--glz1-text-primary`, `--glz1-text-secondary`, and `--glz1-line`;
- `--glz1-focus`, `--glz1-info`, `--glz1-success`, `--glz1-warning`, and `--glz1-critical`;
- V1 spacing and radius roles;
- `--glz1-target-shell: 48px`;
- `--glz1-target-assisted: 56px`;
- System Overlay background, blur, and shadow semantics;
- V1 motion duration and easing roles.

The existing Manager product variables are mapped onto those semantic roles so the application keeps its own composition without becoming a second design-language authority.

## Input and target geometry

V1 uses a 48 CSS-pixel reference floor for touch-oriented application controls and 56 CSS pixels for Touch Assistance or far-view contexts where applicable.

The Django web mapping applies the normal floor to application branding/navigation controls, appearance controls, buttons, text-like inputs, and selects. The explicit V1 host vocabulary includes `data-glz-input="touch"` and `data-glz-touch-assistance="true"`, allowing target behavior to be validated independently of pointer heuristics.

## Accessibility and resilience

The migration preserves or strengthens:

- keyboard skip link and stable focusable main target;
- deterministic focus and `:focus-visible` treatment;
- System, Light, and Dark appearances;
- explicit Deep Dark host semantics;
- 200% text/reflow support;
- Reduced Motion;
- Reduced Transparency;
- Increased Contrast;
- Forced Colors / High Contrast;
- explicit touch and Touch Assistance geometry;
- no-backdrop-filter solid fallback;
- reduced-performance effects-free fallback;
- semantic state presentation that does not rely on color alone.

Accessibility and capability outrank optical effects. Removing blur, shadow, or nonessential motion must not remove controls, state, target geometry, or authorization boundaries.

## Privacy and security boundary

Manager is private administrative software. The shared shell retains `robots=noindex,nofollow,noarchive`, `referrer=same-origin`, local presentation assets, Django authentication, CSRF protection, and the existing authorization model.

This migration changes presentation semantics only. It does not widen permissions, introduce write-capable administration, create credentials, alter integration scopes, publish Manager publicly, or convert private-network reachability into authorization.

## Automated source validation

`tests/test_glaze_ui_contract.py` fails closed on the current active Django-web contract, including:

- exact V1 version and canonical source revision;
- migration-in-progress consumer status;
- Application shell and System Overlay classifications;
- V1 semantic namespace and 48/56 target floors;
- durable-content Solid/Raised boundary;
- explicit adaptive/accessibility host vocabulary;
- focus, Reduced Motion, Reduced Transparency, Increased Contrast, Forced Colors, Deep Dark, no-backdrop-filter, and reduced-performance fallbacks;
- local-only presentation dependencies;
- removal of active pre-reset Glaze identity from the controlled V1 records.

## Automated rendered evidence

`tests/test_glaze_ui_rendered.py` renders real Manager templates and validates them in a Chromium-family browser. Representative surfaces are:

- Overview;
- Tasks;
- Everkeep;
- Privacy Shield;
- login.

The gate exercises 390 x 844 compact and 1280 x 900 desktop layouts in Light and Dark, plus Reduced Motion, Forced Colors, Touch Assistance, 200% text, Reduced Transparency, and Increased Contrast cases. It checks exact V1 provenance, stylesheet ordering, target geometry, horizontal reflow, appearance tokens, and relevant adaptive behavior.

A green automated rendered gate is application-specific automated evidence only. It is not Human Visual Excellence approval, release approval, upstream production eligibility, deployment acceptance, or production approval.

## Platform Contract relationship

`goreecloud.platform.yaml` may record the Django-web V1 source mapping as Glaze UI `partial` at `1.0.0`, while overall Manager conformance remains evidence-based and incomplete. A Glaze version declaration cannot substitute for implementation or acceptance evidence.

Manager is itself the Manager Platform System, so Manager-to-Manager integration is not applicable. Privacy Shield and Everkeep remain partial; Wardveil Security, Mesh, and Identity remain separately incomplete according to current accepted evidence. This V1 migration does not upgrade those statuses.

## Promotion conditions

The Django web migration may advance beyond migration-in-progress only when the applicable requirements are satisfied against the exact final Manager revision, including:

1. source-contract validation;
2. normal Manager CI and permanent readiness gates;
3. automated rendered browser validation;
4. human visual/accessibility acceptance where automation is insufficient;
5. applicable upstream GLAZE UI V1.0 production eligibility;
6. release approval;
7. deployment and target-environment acceptance;
8. evidence-backed Platform Contract and canonical documentation reconciliation.

Manager-wide V1 adoption additionally requires explicit disposition and acceptance of the desktop, Android, and public-website surfaces.

No gate may be weakened merely to obtain a pass.

## Rollback

If the Django-web V1 migration causes a regression, revert the exact accepted Manager migration merge/commit to the previously accepted Manager source revision rather than restoring a retired Glaze product version or weakening canonical V1 requirements or validators.
