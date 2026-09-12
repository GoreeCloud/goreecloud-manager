# GoreeCloud Manager — Glaze UI 2.1 adoption

GoreeCloud Manager targets **Glaze UI 2.1.0 Stable**. The canonical release tag `v2.1.0` resolves to reviewed source commit `c49113eb8b93c267613fdf1bbca1f814495acad7` in `GoreeCloud/goreecloud-glaze-ui`. Earlier Manager mappings to Glaze UI 1.3 and 1.5 remain historical migration evidence only and do not satisfy current conformance.

This is a repository-local consumer mapping, not a copy of the reference application. Glaze UI governs presentation. Privacy Shield remains authoritative for privacy state, Wardveil Security for security/protection state, Everkeep for resilience/recovery/preservation state, GoreeCloud Mesh for coordination/governance state, and Manager adapters for the operational evidence they expose.

## Source structure

- `core/templates/core/base.html` declares the active `2.1.0` consumer contract, local identity assets, navigation, appearance control, density/form-factor metadata, and material roles.
- `core/static/core/css/app.css` owns Manager-specific layout and product presentation.
- `core/static/core/css/glaze-ui.css` maps current 2.1 material, geometry, spacing, density, interaction, accessibility, motion, and resilience semantics.
- `core/static/core/js/theme.js` provides browser-local System/Light/Dark appearance preference without server or third-party transmission.
- `core/static/core/img/manager-mark.svg` remains repository-controlled presentation artwork; branding approval remains separate from Glaze UI conformance.

## Current material principle

**Content is solid. Interaction is glazed.**

Durable Manager information—hero copy, metrics, cards, details, authentication, protection information, and other reading/data surfaces—uses solid Canvas/Surface presentation. The persistent header is a bounded secondary interaction surface and may use **Soft Glaze** with Balanced clarity. Reduced-transparency, unsupported-backdrop, increased-contrast, and forced-colors paths retain readable opaque boundaries.

Glaze is never used as evidence of security, privacy, health, backup, recovery, or authorization state.

## Geometry, spacing, and density

Manager uses the 2.1 4pt spacing rhythm and current hierarchy-aware shape roles. Comfortable density is the default; compact density may alter padding but must not reduce interaction floors or legibility.

The **general interaction floor is 48px**. When Touch Assistance is enabled, the floor becomes **56px**. Density, narrow viewports, and compact reachability cannot reduce those floors.

Representative web composition is reviewed around the current 2.1 profiles: Mobile 390×844, Tablet 820×1180, Desktop 1280×900, and Wide Desktop 1600×1000. Width adaptation may recompose allocation but must preserve semantic, reading, and keyboard order.

## Color and authority

Manager maps its existing product tokens to Glaze semantic roles for accent, information, positive, warning, danger, privacy, security, online/offline, syncing, protected, restricted, and unavailable presentation. These aliases do not become state producers. Text, structure, labels, and programmatic semantics remain available so state is not color-only.

## Controls and interaction state

Native HTML controls remain authoritative where they provide stronger browser semantics and accessibility. The mapping preserves persistent labels, help/error relationships, disabled/read-only/loading distinctions, visible focus, current destination state, and selection semantics.

Adaptive action grouping and reachability may change visual allocation but never DOM order, focus order, authorization meaning, or underlying state.

## Motion and resilience

Motion is limited to short purposeful interaction feedback. `prefers-reduced-motion` collapses nonessential animation and transformation. Reduced transparency uses an opaque strong surface through both the web media-query path and the explicit `data-glaze-reduced-transparency="true"` adapter path. Increased contrast, forced colors, and lack of backdrop-filter support remain operable.

Glaze Motion experimentation is not required for Manager's Stable 2.1 adoption.

## Appearance and privacy

System is the default appearance. Explicit Light or Dark preferences remain browser-local under `goreecloud-manager-theme`; returning to System removes the override. The initializer runs before stylesheets to avoid mismatched first paint.

Manager presentation is local-only by default: no remote fonts, remote JavaScript, remote stylesheets, analytics, tracking, advertising resources, external icon sets, or design CDN are introduced by this adoption.

The shared shell retains private-administration metadata (`noindex`, `nofollow`, `noarchive`, same-origin referrer policy). Those are defense-in-depth presentation controls and do not replace authentication, private networking, publication controls, or server-side authorization.

## Source validation

Repository checks include:

```bash
python -m pip check
python manage.py check
python manage.py test
```

The source contract fails closed on active 1.x markup, a non-2.1 contract version, a general target below 48px, missing 56px Touch Assistance support, missing current material roles, remote presentation dependencies, or absent accessibility/resilience fallbacks.

## Acceptance boundary

Source conformance is necessary but not sufficient. Before a current application-conformance or production claim, Manager still requires authenticated rendered review of representative task flows in supported appearances and widths, keyboard-only operation, zoom/large text, reduced motion, reduced transparency, increased contrast, forced colors, loading/empty/error/disabled/selected/focus states, and applicable target-platform evidence.

A passing PR does not itself establish deployment, production acceptance, Manager Stable lifecycle status, or acceptance of any integrated GoreeCloud platform system.