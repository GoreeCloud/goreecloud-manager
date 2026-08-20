# GoreeCloud Manager — Glaze UI

## Purpose and authority

This document defines the repository-local implementation contract for the GoreeCloud Manager interface. Manager uses **Glaze UI** as its complete visual and interaction language while preserving the application's read-only security model and the authority of integrated systems.

Manager targets **Glaze UI 1.2.0 Stable**. The canonical design-system source is `GoreeCloud/glaze-ui` at Stable merge revision `3594c056dfb4afe118c3900eecf7e4ceaf084046`. Manager maps those semantics into its existing product layer instead of copying the canonical reference stylesheet wholesale.

This implementation is governed by the shared GoreeCloud Glaze UI Design Language, the Application Branding and User Interface Design Standard, Privacy by Default, and the Code Structure and Documentation Standard. Repository-local rules may make those requirements more specific but do not weaken them.

## Source structure

The presentation layer is deliberately small and auditable:

- `core/templates/core/base.html` — shared application shell, GoreeCloud identity, browser metadata, navigation, appearance control, and main-content landmark.
- `core/static/core/css/app.css` — Manager-specific layout, component presentation, semantic states, responsive grids, and product-level visual tokens.
- `core/static/core/css/glaze-ui.css` — cross-cutting Glaze UI conformance for identity, touch targets, focus behavior, interaction motion, form semantics, contrast, forced colors, and browser capability fallbacks.
- `core/static/core/js/theme.js` — browser-local System/Light/Dark appearance preference with no server or third-party transmission.
- `core/static/core/img/manager-mark.svg` — GoreeCloud-controlled local Manager mark used by the application shell and browser favicon.

Keeping these responsibilities separate makes the design system easier to inspect and prevents one large stylesheet or script from becoming the undocumented authority for unrelated behavior.

## Governing visual language

Manager should be recognizable as GoreeCloud before the user reads the product name. The interface therefore uses the Glaze UI signature deliberately rather than applying generic framework styling.

The shared visual vocabulary includes:

- layered surfaces with selective translucency;
- softened rounded geometry for cards, controls, navigation, fields, and status pills;
- restrained shadows for hierarchy rather than heavy borders;
- purposeful gradients that provide GoreeCloud character without competing with operational content;
- consistent typography, spacing, radii, semantic state presentation, focus treatment, and text selection;
- high-quality System, Light, and Dark appearance behavior;
- responsive information layouts for desktop, laptop, tablet, and mobile administration.

Glass effects are hierarchy tools, not a requirement on every element. Readability and operational comprehension take precedence over decoration.

## Glaze UI 1.2 application-interface mapping

Manager consumes the 1.2 semantic expansion without inventing controls that the product does not need.

The product layer explicitly maps:

- dedicated focus-ring semantics to Manager's established accent identity;
- text-selection semantics to Manager's existing accent surface;
- canonical placeholder opacity;
- canonical field, group, and message spacing relationships;
- 44-pixel minimum targets for actionable and form controls;
- native browser input, select, and textarea behavior rather than unnecessary custom replacements;
- stronger forced-colors coverage for form controls and error presentation.

The current Manager interface does not require checkbox, radio, switch, segmented-control, progress, or banner primitives solely to satisfy the design-system vocabulary. When one of those controls becomes functionally necessary, it must use the corresponding 1.2 semantic and accessibility contract rather than a product-local substitute.

## GoreeCloud identity

The application shell identifies the product as **GoreeCloud Manager** and uses only GoreeCloud-controlled local presentation assets. The Manager mark is an original repository asset; no remote logo, icon set, font, analytics library, or design CDN is required.

Primary and secondary application surfaces inherit the same shared shell. Authentication is therefore part of the GoreeCloud product experience rather than a default Django presentation surface.

## Private-application browser metadata

The shared shell declares:

- `robots=noindex,nofollow,noarchive`;
- `referrer=same-origin`, aligned with Manager's server-side Django referrer policy;
- a private-administration description;
- a local GoreeCloud Manager SVG favicon.

These settings are privacy and presentation defense in depth. They do **not** replace authentication, private networking, Caddy/NetBird publication controls, or server-side authorization.

## Theme behavior and first paint

The default appearance mode is `System`, which follows `prefers-color-scheme`. The appearance control cycles:

1. System
2. Light
3. Dark

Only explicit Light or Dark choices are stored. Returning to System removes the stored override.

`theme.js` is a small local script intentionally loaded before the stylesheets. It reads the browser-local preference and applies the root appearance attribute before the initial stylesheet-driven paint, reducing a light/dark appearance flash. DOM interaction binding is deferred until `DOMContentLoaded`, so the early execution does not depend on controls already existing in the document.

The preference is stored only in browser `localStorage` under `goreecloud-manager-theme`. It is not sent to Manager, stored in the Manager database, exposed to an integration, or used for analytics or tracking. If browser storage is unavailable, the in-memory/System behavior continues without failing the application.

## Accessibility and interaction contract

The shared shell must preserve:

- semantic header, navigation, and main landmarks;
- a keyboard-accessible skip link targeting a programmatically focusable main region;
- visible semantic focus indicators for links, buttons, fields, selects, and textareas;
- practical minimum 44-pixel control targets;
- persistent visible form labels for the authentication workflow;
- readable contrast in both themes;
- keyboard operation for navigation, sign-in, appearance selection, and sign-out;
- reduced-motion behavior;
- reduced-transparency behavior;
- stronger separation when `prefers-contrast: more` is requested;
- operable Windows High Contrast/forced-colors presentation;
- solid-surface fallback when backdrop filtering is unavailable;
- meaningful authentication error presentation using alert semantics.

Motion is progressive enhancement. Hover transitions are used only on hover-capable devices when reduced motion is not requested. A visual effect must be reduced or removed whenever it makes operational information harder to read or use.

## Privacy and dependency boundary

Manager's browser presentation is self-contained. The Glaze UI implementation must not introduce:

- remote fonts;
- remote JavaScript;
- remote stylesheets;
- analytics or behavioral tracking;
- telemetry SDKs;
- advertising resources;
- externally hosted icons or branding assets.

The source-level Glaze contract tests inspect the primary templates and presentation assets for remote browser dependencies. This supports GoreeCloud privacy-by-default and technology-independence requirements while keeping Manager usable without a third-party frontend service.

## Integration presentation

Glaze UI changes presentation only. Manager integrations keep their existing authorization, credential, network, artifact, timeout, fail-soft, and data-minimization boundaries.

Resource monitoring, service availability, scheduled-job monitoring, protection state, private-network visibility, and operational work remain visually and semantically distinct. Manager must not imply that one signal proves another—for example, Beszel resource health does not prove service availability or backup/restore readiness.

Color is not the sole carrier of state: status text remains visible in the interface, and forced-color environments retain textual status meaning even when custom semantic colors are unavailable.

## Automated conformance

Repository validation for the UI foundation includes:

```bash
python -m pip check
node --check core/static/core/js/theme.js
python manage.py collectstatic --noinput
python manage.py check
python manage.py test
```

The Django suite includes source- and rendered-shell regression coverage for:

- GoreeCloud Manager identity and local mark;
- exact Glaze UI 1.2.0 consumer version declaration;
- dedicated 1.2 focus-ring, selection, placeholder, and form-spacing semantics;
- native form-control preservation and minimum target sizing;
- noindex/noarchive and same-origin browser metadata;
- shared-shell inheritance by primary surfaces;
- local-only browser presentation dependencies;
- pre-stylesheet appearance initialization;
- skip-link/main-target semantics;
- responsive/accessibility preference fallbacks;
- active-navigation semantics.

These automated tests establish a source-controlled conformance baseline. They do not substitute for visual review in real browsers.

## Release review boundary

Before a production release is visually approved, material interface changes should receive authenticated browser review at representative desktop and mobile widths in System, Light, and Dark modes. Review should include keyboard-only navigation, reduced-motion behavior, increased contrast where available, forced-colors/high-contrast behavior where practical, authentication errors, empty states, degraded integration states, and long operational values.

Passing repository tests means the source-level Glaze UI contract is intact. It does not by itself claim that every rendered browser/OS combination has been visually inspected or that Manager is approved for production publication.
