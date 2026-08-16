# Glaze UI 1.0 Conformance

Glaze UI conformance protects both beauty and usability. An application is conformant when it uses the shared semantic contract without flattening its product personality.

## Required gates

1. **Identity** — recognizably GoreeCloud; no accidental upstream/default-framework identity.
2. **Tokens** — semantic colors, spacing, radii, motion, focus, and target sizes map to Glaze tokens or documented platform-native equivalents.
3. **Surface hierarchy** — canvas, solid, raised, glaze, and overlay roles are intentional; translucency is selective.
4. **States** — default, hover where applicable, pressed, focus, selected, disabled, loading, success, warning, error, and destructive behavior are defined when relevant.
5. **Accessibility** — keyboard access where applicable, visible focus, semantic labels, target sizing, reduced motion, increased contrast, forced colors, and solid glass fallback.
6. **Adaptive layout** — compact, medium, expanded, and wide layouts transform navigation and information density rather than merely shrinking.
7. **Privacy** — no tracking UI dependencies; remote fonts/scripts/icons are prohibited unless explicitly justified and documented; appearance preference remains local unless a product requirement needs synchronization.
8. **Resilience** — core content and critical actions remain understandable when blur, animation, remote assets, or nonessential JavaScript features are unavailable.
9. **Product personality** — applications may vary composition, accent emphasis, imagery, and information architecture while retaining the Glaze contract.
10. **Visual acceptance** — light and dark modes are reviewed visually at representative compact and expanded widths before stable release.

## Evidence

Each stable GoreeCloud application should expose a small automated Glaze contract test and record any exception with the affected rule, reason, user impact, approved fallback, and review condition.
