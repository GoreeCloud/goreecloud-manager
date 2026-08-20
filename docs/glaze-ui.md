# GoreeCloud Manager — Glaze UI

## Purpose and authority

This document defines the repository-local implementation contract for the GoreeCloud Manager interface. Manager uses **Glaze UI** as its complete visual and interaction language while preserving the application's read-only security model and the authority of integrated systems.

Manager targets **Glaze UI 1.3.0 Stable**. The canonical design-system source is `GoreeCloud/glaze-ui` at reconciled Stable main revision `0cd084d9c888a9697cbd9fdd2c4d2bd91286c56c`; the accepted 1.3 design candidate was validated at `e206c3da3f5c0df1f1d0e73d7339f9b45b0e1f16` and promoted through PR #6. Manager maps those semantics into its existing product layer instead of copying the canonical reference stylesheet wholesale.

This implementation is governed by the shared GoreeCloud Glaze UI Design Language, the Application Branding and User Interface Design Standard, Privacy by Default, and the Code Structure and Documentation Standard. Repository-local rules may make those requirements more specific but do not weaken them.

## Source structure

The presentation layer is deliberately small and auditable:

- `core/templates/core/base.html` — shared application shell, GoreeCloud identity, browser metadata, navigation, appearance control, Glaze 1.3 material/action metadata, and main-content landmark.
- `core/static/core/css/app.css` — Manager-specific layout, component presentation, semantic states, responsive grids, and product-level visual tokens.
- `core/static/core/css/glaze-ui.css` — cross-cutting Glaze UI conformance for identity, touch targets, focus behavior, form semantics, Functional Glass, expressive shape/motion, adaptive grouping, accessibility, and browser capability fallbacks.
- `core/static/core/js/theme.js` — browser-local System/Light/Dark appearance preference with no server or third-party transmission.
- `core/static/core/img/manager-mark.svg` — GoreeCloud-controlled local Manager mark used by the application shell and browser favicon.

Keeping these responsibilities separate makes the design system easier to inspect and prevents one large stylesheet or script from becoming the undocumented authority for unrelated behavior.

## Governing visual language

Manager should be recognizable as GoreeCloud before the user reads the product name. The interface therefore uses the Glaze UI signature deliberately rather than applying generic framework styling.

The shared visual vocabulary includes layered surfaces, softened rounded geometry, restrained shadows, purposeful gradients, consistent typography and spacing, strong System/Light/Dark appearance behavior, responsive administration layouts, and semantic state/focus treatment.

Glaze UI 1.3 adds a stricter material boundary: glass is a functional hierarchy tool, not the default content treatment. Manager therefore keeps ordinary operational information on Solid/Raised surfaces while reserving Functional Glass for navigation and interactive chrome.

## Glaze UI 1.3 expressive-hierarchy mapping

Manager adopts the 1.3 expressive layer conservatively because it is an operational administration product rather than a showcase interface.

The product layer explicitly maps:

- **Functional Glass** to the sticky application header and navigation chrome;
- Solid/Raised treatment to hero, operational cards, metrics, details, protection information, and authentication content;
- Compact, Standard, Expressive, Hero, and Pressed shape semantics, with stronger geometry concentrated in hero and selected/action states;
- separate **effects motion** for color, border, and shadow feedback and **spatial motion** for transform and geometry changes;
- adaptive action grouping for navigation and header controls without changing logical or keyboard order;
- compact reachability behavior that preserves DOM order while maintaining practical touch sizing for frequent actions;
- bounded pressed-state geometry and motion rather than decorative animation;
- dedicated focus-ring and text-selection semantics, canonical placeholder opacity, field/group/message spacing, and 44-pixel minimum targets retained from 1.2.

Manager does not introduce Clear Glass because it does not currently place controls over rich media. It also does not introduce checkbox, radio, switch, segmented-control, progress, or banner primitives solely to demonstrate design-system coverage. When one of those controls becomes functionally necessary, it must use the current Glaze semantic and accessibility contract rather than a product-local substitute.

## GoreeCloud identity

The application shell identifies the product as **GoreeCloud Manager** and uses only GoreeCloud-controlled local presentation assets. The Manager mark is an original repository asset; no remote logo, icon set, font, analytics library, or design CDN is required.

Primary and secondary application surfaces inherit the same shared shell. Authentication is therefore part of the GoreeCloud product experience rather than a default Django presentation surface.

## Private-application browser metadata

The shared shell declares `robots=noindex,nofollow,noarchive`, `referrer=same-origin`, a private-administration description, and a local GoreeCloud Manager SVG favicon. These settings are privacy and presentation defense in depth and do not replace authentication, private networking, Caddy/NetBird publication controls, or server-side authorization.

## Theme behavior and first paint

The default appearance mode is `System`, which follows `prefers-color-scheme`. The appearance control cycles System, Light, and Dark. Only explicit Light or Dark choices are stored; returning to System removes the stored override.

`theme.js` is intentionally loaded before the stylesheets so the root appearance is applied before the first stylesheet-driven paint. The preference is stored only in browser `localStorage` under `goreecloud-manager-theme`; it is not sent to Manager, stored in the Manager database, exposed to an integration, or used for analytics or tracking.

## Accessibility and interaction contract

The shared shell must preserve semantic header/navigation/main landmarks, a keyboard-accessible skip link, visible semantic focus indicators, practical 44-pixel targets, persistent authentication labels, readable contrast, keyboard operation, reduced-motion behavior, reduced-transparency behavior, stronger separation under `prefers-contrast: more`, forced-colors operation, solid fallbacks when backdrop filtering is unavailable, and meaningful authentication-error alerts.

Glaze 1.3 motion remains progressive enhancement. Effects and spatial transitions collapse to effectively instant behavior when reduced motion is requested. Functional Glass becomes a solid strong surface when reduced transparency is requested or backdrop filtering is unavailable. Color is never the sole carrier of state.

## Privacy and dependency boundary

Manager's browser presentation is self-contained. The Glaze UI implementation must not introduce remote fonts, remote JavaScript, remote stylesheets, analytics or behavioral tracking, telemetry SDKs, advertising resources, or externally hosted icons or branding assets.

## Integration presentation

Glaze UI changes presentation only. Manager integrations keep their existing authorization, credential, network, artifact, timeout, fail-soft, and data-minimization boundaries. Resource monitoring, service availability, scheduled-job monitoring, protection state, private-network visibility, and operational work remain visually and semantically distinct. Manager must not imply that one signal proves another.

## Automated conformance

Repository validation for the UI foundation includes:

```bash
python -m pip check
node --check core/static/core/js/theme.js
python manage.py collectstatic --noinput
python manage.py check
python manage.py test
```

The Django/source suite includes regression coverage for:

- GoreeCloud Manager identity and local mark;
- exact Glaze UI 1.3.0 consumer declaration and canonical revision documentation;
- Functional Glass limited to application chrome;
- Solid/Raised operational content defaults;
- expressive shape roles and bounded pressed geometry;
- separate effects/spatial motion tokens and reduced-motion collapse;
- adaptive action-group and compact-reachability markers with preserved DOM order;
- focus, selection, placeholder, form-spacing, native-control, and minimum-target semantics retained from 1.2;
- noindex/noarchive and same-origin browser metadata;
- shared-shell inheritance, local-only presentation dependencies, pre-stylesheet appearance initialization, skip-link/main-target semantics, responsive/accessibility fallbacks, and active-navigation semantics.

These automated tests establish a source-controlled conformance baseline. They do not substitute for visual review in real browsers.

## Release review boundary

Before a production release is visually approved, material interface changes should receive authenticated browser review at representative desktop and mobile widths in System, Light, and Dark modes. Review should include keyboard-only navigation, reduced motion, reduced transparency where supported, increased contrast, forced colors/high contrast, authentication errors, empty states, degraded integration states, long operational values, Functional Glass readability, compact reachability, adaptive action grouping, and confirmation that operational content remains calm rather than becoming decorative glass.

Passing repository tests means the source-level Glaze UI contract is intact. It does not by itself claim that every rendered browser/OS combination has been visually inspected or that Manager is approved for production publication.
