# Glaze UI 1.0

Glaze UI is GoreeCloud's shared visual and interaction design system. It preserves the polished, layered, rounded, gradient-rich character already used by GoreeCloud while making the underlying rules reusable and testable.

**Beauty is a requirement, not a regression risk.** Glaze UI 1.0 does not replace the existing aesthetic with a generic component kit. It protects the aesthetic by separating a stable semantic foundation from each application's composition and personality.

## Design formula

Material structure + liquid depth and fluidity + One UI ergonomics + GoreeCloud privacy, identity, and simplicity = Glaze UI.

## Surface hierarchy

1. **Canvas** — atmospheric application background; may carry restrained radial/brand gradients.
2. **Solid** — high-readability surface used when translucency would reduce clarity or performance.
3. **Raised** — solid or nearly solid card/panel with soft elevation.
4. **Glaze** — selectively translucent surface with blur/saturation and a mandatory solid fallback.
5. **Overlay** — dialogs, menus, sheets, and other attention-priority surfaces; strongest separation.

Glass is never mandatory everywhere. Depth should be visible, not noisy.

## Component baseline

Glaze UI standardizes the behavior and anatomy of buttons, icon buttons, search fields, text inputs, selects, checkboxes, toggles, cards, chips, tabs, navigation rails, sidebars, bottom navigation, dialogs, sheets, menus, tooltips, toasts, tables, status indicators, empty states, loading states, and error states.

Every relevant component defines default, hover, pressed, focus, selected, disabled, loading, success, warning, error, and destructive states.

## Adaptive layouts

- **Compact:** up to 599px — mobile-first composition; bottom navigation or compact top navigation where appropriate.
- **Medium:** 600–1023px — tablet/small-window composition; rails, split views, or sheets where useful.
- **Expanded:** 1024–1439px — desktop/laptop composition with persistent navigation when useful.
- **Wide:** 1440px+ — additional context may appear, but primary content width remains controlled.

## Motion vocabulary

- Instant: 90ms — tiny acknowledgement only.
- Fast: 160ms — hover/press/focus transitions.
- Standard: 220ms — ordinary state and layout transitions.
- Emphasized: 320ms — dialogs, navigation, and meaningful entrances/exits.

Reduced-motion mode removes nonessential movement rather than merely making it faster.

## Privacy contract

Prefer local assets and system/local fonts. Do not add analytics, trackers, remote UI dependencies, or third-party icon/font delivery as part of Glaze UI. External resources require a product-specific justification.

## Package layout

- `tokens/glaze.tokens.json` — platform-neutral semantic token source.
- `css/glaze.css` — canonical web variables and primitive classes.
- `css/glaze.accessibility.css` — reduced-motion, increased-contrast, forced-colors, and glass fallbacks.
- `CONFORMANCE.md` — stable-release conformance gates.
- `reference/index.html` — dependency-free visual reference.
- `scripts/validate_glaze_ui.py` — zero-dependency token/package validator.

## Versioning

Glaze UI follows semantic versioning. Patch releases clarify or fix compatible behavior. Minor releases add compatible tokens/components. Major releases may change required semantics. Applications should record the Glaze UI version they target.

This directory is the canonical 1.0 reference foundation until GoreeCloud moves it into a dedicated Glaze UI repository. Its structure is intentionally repository-independent so that move does not change the design contract.
