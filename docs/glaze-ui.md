# GoreeCloud Manager — Glaze UI

## Purpose

This document defines the repository-local implementation contract for the GoreeCloud Manager interface. It applies the shared GoreeCloud Glaze UI design language to Manager without changing the application's read-only security model or the authority of integrated systems.

## Design goals

Manager should feel visibly GoreeCloud while remaining an operational console first. The interface prioritizes clear hierarchy, dense-but-readable status information, predictable navigation, accessible interaction, and restrained visual depth.

The shared shell uses:

- system-aware light and dark appearance;
- an explicit browser-local appearance preference with System, Light, and Dark modes;
- layered surfaces with restrained translucency and blur;
- rounded geometry and consistent spacing tokens;
- semantic healthy, degraded, unavailable, warning, and neutral states;
- visible keyboard focus indicators;
- touch-friendly navigation and controls;
- responsive layouts for desktop, laptop, tablet, and mobile administration;
- reduced-motion and reduced-transparency fallbacks where supported.

## Privacy boundary

The appearance preference is stored only in browser `localStorage` under `goreecloud-manager-theme`. It is not sent to Manager, written to the Manager database, exposed to an integration, or used for analytics or tracking.

No third-party browser script, font, analytics package, telemetry SDK, or remote design dependency is required by the Glaze UI implementation.

## Navigation

The shared authenticated shell provides Overview and Tasks navigation with `aria-current="page"` on the active destination. A keyboard-accessible skip link moves directly to the main content region. Sign-out remains a POST action protected by Django CSRF middleware.

## Theme behavior

The default mode is `System`, which follows `prefers-color-scheme`. The appearance control cycles:

1. System
2. Light
3. Dark

Only explicit Light or Dark choices are stored. Returning to System removes the stored override.

## Accessibility

The shell must preserve:

- semantic landmarks and navigation labels;
- visible focus states;
- readable contrast in both themes;
- keyboard operation for navigation, sign-in, appearance selection, and sign-out;
- minimum practical touch target sizing on narrow screens;
- reduced-motion behavior;
- meaningful error presentation with alert semantics on authentication failure.

A visual effect must be removed or reduced if it makes operational information harder to read or use.

## Integration presentation

Glaze UI changes presentation only. Manager integrations keep their existing authorization, credential, network, artifact, timeout, fail-soft, and data-minimization boundaries.

Resource monitoring, service availability, scheduled-job monitoring, protection state, and operational work remain visually and semantically distinct. Manager must not imply that one signal proves another—for example, Beszel resource health does not prove service availability or backup/restore readiness.

## Validation

Repository validation for this UI foundation includes:

```bash
python -m pip check
node --check core/static/core/js/theme.js
python manage.py collectstatic --noinput
python manage.py check
python manage.py test
```

Material interface changes should also receive authenticated browser review at supported desktop and mobile widths in both light and dark appearance modes before release promotion.
