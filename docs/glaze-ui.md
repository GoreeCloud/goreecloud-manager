# GoreeCloud Manager — GLAZE UI V1.1

## Purpose and authority

This document defines the repository-local presentation contract for GoreeCloud Manager. Manager uses **GLAZE UI V1.1 / 1.1.0**, the current Stable GoreeCloud design-system target, while preserving Manager's visibility-first authority and the separate authority of the systems whose state it presents.

The canonical design-system source is `GoreeCloud/goreecloud-glaze-ui` at immutable Stable release commit `15cc76d2bcd4065552dc31c77145b63f34d9e7b2`, tag `v1.1.0`. Manager's source migration is not, by itself, rendered-browser acceptance, target-device acceptance, production publication, or Stable product qualification.

## Immutable source model

Manager carries a repository-local lock at `core/static/core/glaze.lock.json`. It records the Stable release identity, `css/glaze-v1.1.0.css` entrypoint, and the exact Git blob identity of all thirteen files in the canonical Stable web import graph.

The exact locked files are committed under `core/static/core/glaze/`. `scripts/vendor_glaze_v1_1.py` may refresh that directory only from an explicitly supplied local checkout of the immutable release. The helper verifies every source and destination Git blob before accepting the copy. The application then serves those files through its ordinary first-party static path.

This produces two distinct boundaries:

- maintenance may consult the immutable canonical repository revision to refresh the committed copy;
- application builds and browser runtime consume only repository-local static assets and require no GitHub, CDN, remote font, remote script, or remote stylesheet dependency.

## Source structure

- `core/templates/core/base.html` — shared private application shell, V1.1 activation, local Stable stylesheet entrypoint, navigation semantics, appearance control, and main-content landmark.
- `core/static/core/glaze.lock.json` — immutable Stable V1.1 source graph and Git blob identities.
- `core/static/core/glaze/` — exact locally served canonical Stable V1.1 CSS graph.
- `core/static/core/css/app.css` — Manager-specific layout, product palette, operational content, and protected state presentation.
- `core/static/core/css/glaze-ui.css` — Manager's bounded V1.1 adapter, accessibility behavior, target sizing, material boundary, and progressive fallbacks.
- `core/static/core/js/theme.js` — browser-local System, Light, Dark, and Deep Dark appearance preference.
- `core/static/core/img/manager-mark.svg` — GoreeCloud-controlled local Manager product mark.

The canonical source and Manager adapter remain separate so Manager does not fork or silently redefine the design-system source.

## V1.1 activation and appearance

The document root declares `data-glaze-version="1.1"` and loads the locally committed `glaze-v1.1.0.css` Stable entrypoint. Manager uses the V1.1 `glz11-*` navigation and button semantics on its shared shell without changing logical navigation order or application authority.

Appearance supports:

- System;
- Light;
- Dark;
- Deep Dark.

Explicit modes use the canonical `data-glz-appearance` attribute. System removes the explicit override and follows platform color-scheme preference. Manager retains a local `data-theme` compatibility attribute only for its pre-existing product palette while the canonical Glaze appearance contract is `data-glz-appearance`.

The preference is browser-local under `goreecloud-manager-theme`. It is not transmitted to Manager, another GoreeCloud system, analytics, or any third party. `theme.js` loads before stylesheets so an explicit local preference can be applied before first paint.

## Material and authority boundary

V1.1's presentation rule is applied directly: durable information stays solid; Glaze is bounded to transient interaction chrome.

Manager therefore uses Glaze on the persistent header/navigation interaction layer while keeping the following on Solid/Raised surfaces:

- authentication content;
- platform and integration summaries;
- operational cards;
- metrics;
- detailed state records;
- resilience/protection information;
- other durable evidence users read to make administrative decisions.

Glaze presentation never creates security, privacy, identity, recovery, monitoring, Mesh, or integration truth. Protected Manager status colors remain producer/product-authoritative rather than being synthesized from appearance.

## Interaction geometry

The ordinary V1.1 interaction floor is **48 px**. Manager maps its navigation, buttons, native form controls, selects, and text areas to the canonical `--glz11-target-min` contract instead of retaining the historical 44 px floor.

When V1.1 Touch Assistance is explicitly active, the canonical design system raises the interaction target to **56 px**. Manager inherits that value rather than defining a competing product-specific target.

Responsive composition must preserve keyboard/DOM order and deliberately recompose the header, navigation, action groups, cards, and operational data at narrow widths rather than relying on horizontal scrolling as the primary adaptation mechanism.

## Accessibility and resilience

Manager preserves:

- semantic header, navigation, main, form, and authentication-error structure;
- keyboard-accessible skip navigation and visible focus;
- Reduced Motion;
- Reduced Transparency;
- Increased Contrast;
- Forced Colors / High Contrast;
- native form semantics;
- readable operation when backdrop filtering is unavailable;
- platform/System color-scheme behavior;
- 200% text and narrow-width reflow as acceptance requirements;
- pointer, keyboard, and touch operability.

Reduced Transparency and unsupported-backdrop environments remove Glaze effects from the header rather than weakening content readability. Reduced Motion collapses optional transition and transform behavior. Forced Colors removes decorative material effects and uses system colors.

## Privacy and dependency boundary

Manager's browser presentation remains self-contained. It must not introduce remote fonts, analytics, behavioral tracking, advertising, telemetry SDKs, remote scripts, remote stylesheets, or externally hosted icons/branding.

The canonical V1.1 CSS entrypoint uses only relative imports within the committed locked source graph. Repository tests reject remote runtime dependencies and source-graph drift.

## Automated source contract

Repository validation must include the ordinary Manager checks plus the V1.1 source contract. The V1.1 regression layer verifies at minimum:

- root V1.1 activation and local Stable entrypoint;
- exact release commit, version, tag, entrypoint, and thirteen-file lock;
- committed local vendor filename set and every exact Git blob identity;
- no unsafe symlinked vendor files;
- local-only browser dependencies;
- V1.1 navigation/button semantics;
- canonical 48 px normal and 56 px Touch Assistance target contracts;
- bounded header Glaze and Solid/Raised durable content;
- System/Light/Dark/Deep Dark behavior through `data-glz-appearance`;
- first-paint appearance ordering;
- native form controls;
- Reduced Motion, Reduced Transparency, Increased Contrast, Forced Colors, and no-backdrop fallbacks;
- shared-shell inheritance and GoreeCloud Manager identity.

A passing source suite establishes only that the reviewed repository revision implements the source contract.

## Rendered and release acceptance boundary

Current GLAZE UI V1.1 consumer acceptance requires fresh Manager-specific exact-revision evidence. Before Manager may claim current V1.1 conformance or Stable qualification, applicable evidence must separately cover authenticated rendered browser behavior, representative desktop and mobile widths, appearance modes, keyboard use, 200% text, Reduced Motion, Reduced Transparency, Increased Contrast, Forced Colors, long/empty/degraded states, and the supported Manager client/device surfaces required by the governing specification.

Source validation, a pull request, or a successful CI run does **not establish** production publication, deployed-byte identity, target-environment visual acceptance, desktop-client acceptance, Android acceptance, broader platform integration acceptance, or production approval.

Manager remains a Development product until its independent governing acceptance requirements are satisfied.
