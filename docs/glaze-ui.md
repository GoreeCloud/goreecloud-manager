# GoreeCloud Manager — Glaze UI 2.2 implementation contract

## Purpose and authority

This document defines the repository-local Glaze UI implementation contract for **GoreeCloud Manager**. Manager uses Glaze UI as its visual and interaction language while preserving its read-only operational model and the independent authority of GoreeCloud Identity, Privacy Shield, Wardveil Security, Everkeep, GoreeCloud Mesh, and integrated applications.

The required current design-system target is **Glaze UI 2.2.0 Stable** from `GoreeCloud/goreecloud-glaze-ui`, pinned for this migration to exact release revision `6731098b28dd0393faa878c70d989a221d714a20`. The historical rollback baseline is Glaze UI 2.1.0. Candidate-named Glaze source files are release provenance and are not production compatibility aliases.

Central Glaze UI promotion does not make Manager conformant by declaration. Manager must earn repository-local source, automated, rendered web, native, accessibility, device, release, and production evidence as applicable.

## Controlled surfaces

Manager has several controlled user-facing surfaces with separate evidence boundaries:

- the public Manager product website, which already consumes the Glaze UI 2.2 Stable entrypoint under its own website validation;
- the authenticated Django application shell under `core/templates/core/` and `core/static/core/`;
- the PySide6/Linux desktop client under `desktop-client/`;
- the Android client under `android-client/`, including its secure WebView wrapper and native connection-error/retry fallback.

This migration makes the authenticated web shell and native presentation mappings source-native to Glaze UI 2.2. It does **not** inherit the public website's acceptance evidence into those other surfaces.

## Stable presentation rule

Manager follows the 2.2 Stable rule:

> Solid where users read or make explicit critical decisions. Glazed where users interact with transient navigation, command, search, or feedback chrome.

Operational metrics, service state, protection information, authentication content, tables, details, and other durable reading surfaces remain solid. The authenticated web shell maps the sticky application header to one bounded **System Overlay**. Manager currently consumes no dominant System Panel by default; the ordinary System Glaze budget remains one dominant panel, and nested backdrop blur is prohibited.

The desktop client intentionally stays toolkit-native and solid instead of imitating browser blur. Android's native error state is likewise a solid raised surface. Native mapping is conformance work, not an exemption from Glaze UI.

## Authenticated web mapping

The shared Django shell declares Glaze UI `2.2.0`, records the exact Stable release in the repository-local stylesheet, and keeps all presentation assets same-origin and local.

`core/static/core/css/glaze-ui.css` maps the consumed 2.2 semantics without importing the canonical Candidate implementation wholesale. It provides:

- the 48px minimum shell/control floor;
- the 56px Touch Assistance/far-view floor through `data-glz-touch-assistance="true"`;
- explicit touch input mapping through `data-glz-input="touch"`;
- 200% text reflow through `data-glz-text-scale="200"` and large-text host state;
- Reduced Motion behavior;
- Reduced Transparency through browser preference and `data-glz-transparency="reduced"`;
- Increased Contrast through browser preference and the explicit host mode;
- Forced Colors operation;
- solid fallbacks when backdrop filtering is unavailable;
- visible focus stronger than hover decoration;
- deterministic rest/hover/focus/pressed/selected/disabled presentation;
- one dominant System Panel budget; and
- nested-blur suppression.

The shell retains semantic landmarks, a skip link, noindex/noarchive metadata, same-origin referrer behavior, native form controls, and browser-local appearance preference. Glaze changes presentation only; it does not broaden authentication, authorization, network, data, privacy, security, recovery, or integration authority.

## Desktop native mapping

`desktop-client/goreecloud_manager/theme.py` records:

- `GLAZE_UI_VERSION = "2.2.0"`;
- the exact Stable release revision;
- a 48px effective native control floor;
- a 56px Touch Assistance floor when the host enables that mode; and
- the one-dominant-System-Panel budget as an auditable application property.

The Qt mapping keeps durable content solid and uses native widgets, focus, selection, appearance, and semantic-state behavior. It does not introduce simulated web glass, arbitrary animation, or product-local authority for platform accessibility state. Real Linux accessibility/high-contrast/device behavior still requires native acceptance evidence.

## Android native mapping

`MainActivity.kt` records the same Glaze UI 2.2 version and release revision. The secure WebView continues to allow only the configured HTTPS Manager origin, rejects mixed content, disables file/content access, disables third-party cookies, and cancels TLS errors.

The native connection-error/retry surface is a solid platform-native fallback. Its retry target is at least 48dp and rises to 56dp when Android touch exploration is enabled. The fallback follows the current light/dark system appearance and exposes the error as an accessibility live region. These source declarations do not constitute emulator or real-device acceptance.

## Accessibility and performance boundary

2.2 acceptance requires keyboard, pointer, touch, RTL/localization where applicable, 200% text, Reduced Motion, Reduced Transparency, Increased Contrast, Forced Colors, Touch Assistance, focus restoration, non-color semantic state, and representative performance validation.

The browser mapping removes effects before meaning or target geometry. The Qt mapping is already effects-light/solid. The Android fallback is solid and native. If future Manager UI adds Universal Search, Control Center, Intelligence components, or a dominant System Panel, those features must be mapped to their actual 2.2 semantic contracts instead of borrowing the name or appearance.

## Privacy and dependency boundary

Manager presentation remains self-contained. Glaze UI adoption must not add remote fonts, remote JavaScript, remote stylesheets, analytics, tracking, advertising resources, externally hosted icons, or design CDNs to the authenticated application.

The Android WebView's network access is application functionality, not a presentation dependency, and remains restricted to the approved Manager HTTPS origin.

## Automated conformance

Repository validation includes the existing Django/source and client-packaging gates. The Glaze UI source contract specifically verifies:

- exact `2.2.0` declarations and Stable release revision;
- no active 1.x/2.0/2.1 or Candidate design-system declaration in the controlled app shell;
- bounded System Overlay material and solid durable content;
- 48px and 56px target floors;
- canonical `data-glz-*` accessibility override spellings consumed by Manager;
- 200% text and accessibility fallbacks;
- no nested backdrop blur strategy;
- local-only browser presentation dependencies;
- Qt 2.2 provenance and native target mapping; and
- Android 2.2 provenance, secure-origin behavior, and native target mapping.

Typical validation commands remain:

```bash
python -m pip check
node --check core/static/core/js/theme.js
python manage.py collectstatic --noinput
python manage.py check
python manage.py test
```

Client packaging/compile workflows provide additional source/build evidence for the desktop and Android trees.

## Acceptance status and release boundary

This document records an **implementation contract**, not production acceptance. Source implementation and passing repository CI are necessary but not sufficient.

Before Manager can claim Glaze UI 2.2 conformance or Stable product eligibility, applicable exact-revision evidence must include authenticated browser review at representative desktop/mobile widths, keyboard and accessibility modes, native client validation, applicable emulator/real-device review, Human Visual Excellence review where required, release approval, and production verification.

Previous Glaze UI 2.1 or public-website 2.2 acceptance does not automatically satisfy those Manager application gates. Production eligibility remains false until Manager's own evidence says otherwise.
