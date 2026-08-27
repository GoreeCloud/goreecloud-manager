# GoreeCloud Manager — Glaze UI

## Purpose and authority

This document defines the repository-local implementation contract for the GoreeCloud Manager interface. Manager uses **Glaze UI** as its complete visual and interaction language while preserving the application's read-only security model and the authority of integrated systems.

Manager targets **Glaze UI 1.5.0 Stable**, the mandatory current production design-system baseline. The reviewed Stable promotion revision is `2e1618397f6ebcdd254a76bfdd7e98846f2c5aa3` in `GoreeCloud/goreecloud-glaze-ui`. Earlier Manager mappings to Glaze UI 1.3.0 remain historical migration evidence only and do not satisfy current conformance.

Glaze UI governs presentation. Privacy Shield remains authoritative for privacy state, Wardveil Security for security/protection state, Everkeep for resilience/recovery/preservation state, and GoreeCloud Mesh for coordination/governance state. Manager never upgrades those claims through color, iconography, material, motion, or layout.

## Source structure

- `core/templates/core/base.html` — shared shell, local identity assets, navigation, material/depth roles, density metadata, application/security icon roles, appearance control, and main landmark.
- `core/static/core/css/app.css` — Manager-specific layout and product presentation.
- `core/static/core/css/glaze-ui.css` — Glaze UI 1.5 semantic mapping for adaptive color, material and depth, spacing, density, interaction states, form semantics, motion, accessibility, and browser fallbacks.
- `core/static/core/js/theme.js` — browser-local System/Light/Dark preference with no server or third-party transmission.
- `core/static/core/img/manager-mark.svg` — repository-controlled application identity artwork.

## Material and depth

Manager preserves the Glaze UI semantic material hierarchy:

- **Canvas** for the application environment;
- **Solid/Raised** for ordinary operational content, dense information, authentication, protection details, recovery information, and other reading-focused surfaces;
- **Functional Glass** only for bounded navigation/application chrome;
- **Overlay** only when a real transient high-authority surface requires it;
- **Clear Glass** is not used because Manager does not currently place controls over rich media.

Depth is semantic rather than decorative. The shared header maps to `navigation`; ordinary page content maps to `base`. No depth, blur, tint, or shadow implies security, privacy, backup, recovery, or service-health truth.

## Adaptive color

Manager maps current application tokens to the Glaze UI 1.5 adaptive color families it can truthfully consume: accent, information, success, warning, danger, privacy, security, online, offline, syncing, protected, restricted, and unavailable.

These are presentation aliases, not state producers. Existing domain data and integration adapters remain authoritative. Semantic state always retains text, structure, iconography, or programmatic meaning so color is never the sole carrier of information. Product accent and identity treatment cannot recolor destructive, privacy, security, availability, or protection meaning into ambiguity.

## Iconography

The shared shell marks the repository-controlled Manager mark as an application-identity icon and the existing Wardveil artwork as security presentation identity. Icon roles do not convert artwork into runtime evidence. No remote icon set, font, image CDN, or third-party design runtime is required.

## Layout and density

Manager adopts the Glaze UI 1.5 spacing primitives `2, 4, 8, 12, 16, 24, 32, 48, 64, 96` pixels and the semantic content measures for prose, forms, standard workspaces, and wide workspaces.

Responsive gutters follow current window signals:

- compact below 600px: 16px;
- medium 600–1023px: 24px;
- expanded 1024–1599px: 32px;
- large display 1600px and above: 48px.

The default density is **comfortable**. Density changes spacing only and may never reduce practical minimum targets, focus treatment, text legibility, or safe separation. Adaptive grouping and compact reachability may change visual allocation but never DOM order, reading order, meaning, or keyboard/focus order.

## Interaction state

Glaze UI 1.5 distinguishes default, hover, focus-visible, pressed, selected, expanded, disabled, read-only, loading, invalid, and success semantics where they are functionally present.

Manager keeps native HTML semantics authoritative. Disabled controls use native `disabled` or `aria-disabled`; read-only content remains legible and distinct through native `readonly` or equivalent semantics; loading regions may use truthful `aria-busy`; invalid content retains accessible explanation. Hover is enhancement only, and focus-visible remains available for keyboard and assistive workflows.

## Stable motion

Manager consumes the **Glaze UI 1.5 Stable motion contract**, not the separately evolving Glaze Motion subsystem. Stable duration roles are mapped locally as instant `0ms`, micro `90ms`, short `160ms`, medium `240ms`, long `360ms`, and ambient `700ms`.

Motion is limited to purposeful interaction feedback such as short tonal, border, shadow, and bounded pressed-state changes. Reduced motion collapses nonessential geometry and transitions without changing state meaning or delaying tasks.

**Glaze Motion is currently Experimental and is not a Manager production dependency.** Its experimental lifecycle does not alter the mandatory Glaze UI 1.5 Stable contract.

## Appearance and accessibility

The default appearance is System, following the platform color-scheme preference. Explicit Light or Dark choices are stored only in browser `localStorage` under `goreecloud-manager-theme`; returning to System removes the override. The theme initializer runs before stylesheets to avoid a mismatched first paint.

The source contract preserves:

- visible semantic focus treatment;
- practical 44px minimum targets;
- persistent form labels and native controls;
- reduced-motion behavior;
- reduced-transparency fallback through both progressive web preference support and the explicit `data-glaze-reduced-transparency="true"` adapter path;
- stronger separation under increased contrast;
- forced-colors/high-contrast operation;
- solid fallbacks when backdrop filtering is unavailable;
- keyboard-accessible skip navigation and semantic landmarks;
- meaningful authentication error alerts.

## Privacy and dependency boundary

Manager presentation remains self-contained. Glaze UI integration must not introduce remote fonts, remote JavaScript, remote stylesheets, analytics, behavioral tracking, advertising resources, externally hosted icons, or design CDNs. Theme and layout preferences are presentation state, not analytics inputs.

## Integration presentation

Manager is a read-only observer. Integration cards and details may present sanitized evidence received from approved adapters, but Glaze presentation cannot manufacture or strengthen underlying claims. Wardveil Security, Privacy Shield, Everkeep, GoreeCloud Mesh, resource monitoring, service availability, scheduled-job monitoring, and operational tasks remain semantically distinct.

## Automated conformance

Repository validation includes:

```bash
python -m pip check
node --check core/static/core/js/theme.js
python manage.py collectstatic --noinput
python manage.py check
python manage.py test
```

The source suite enforces the exact Glaze UI 1.5.0 consumer declaration and Stable promotion revision, adaptive semantic-color aliases, material/depth boundaries, application/security icon roles, spacing and content-measure primitives, comfortable density, current responsive gutters, Stable motion roles, native disabled/read-only/loading semantics, accessibility fallbacks, local-only dependencies, appearance initialization, landmarks, and inheritance of the shared shell. Superseded 1.3 shell/CSS markers fail closed.

## Acceptance boundary

Source conformance is necessary but not sufficient for current application conformance. Authenticated rendered acceptance remains required at representative compact, medium, desktop, and wide widths in System, Light, and Dark appearances, including keyboard-only navigation, screen-reader semantics, reduced motion, reduced transparency, increased contrast, forced colors, long values, authentication errors, degraded integration states, and material readability.

Applicable Linux desktop-client, resilience, interaction-state, material/depth, layout/density, and target-device evidence also remains separately acceptance-controlled. Passing source CI does not by itself establish production deployment, Manager Stable qualification, or completion of GoreeCloud-wide Glaze UI 1.5 migration evidence.
