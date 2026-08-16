# Glaze UI 1.0 Component Contract

Glaze UI standardizes component semantics and interaction quality without forcing every GoreeCloud application into the same composition.

## Universal component rules

Every interactive component must have a clear accessible name, a visible focus state, a minimum 44px practical pointer/touch target when the component is directly actionable, and predictable disabled/loading behavior. Components should use semantic tokens instead of product-local literal colors, radii, spacing, or motion values when a corresponding token exists.

State vocabulary, where relevant: **default, hover, pressed, focused, selected, disabled, loading, success, warning, error, destructive**.

## Buttons

Primary buttons use the Glaze accent treatment and may use the characteristic accent-to-secondary gradient. Secondary buttons use a quieter surface. Destructive actions use the danger semantic and must not rely on color alone. Loading buttons retain their label context and expose busy state to assistive technology.

## Icon buttons

Icon-only controls require an accessible name. They use compact rounded geometry, minimum target sizing, visible focus, and optional tooltip support for unfamiliar actions.

## Inputs, search, and selects

Inputs use readable labels, persistent error/help relationships, and rounded surface geometry. Placeholder text is not a substitute for a label. Search may use pill geometry where appropriate but must preserve normal keyboard and screen-reader behavior.

## Selection controls

Checkboxes, radio controls, switches, tabs, and chips expose selected/checked state semantically. Custom visual controls must retain platform accessibility semantics and remain usable in forced-colors mode.

## Cards and panels

Cards may use solid, raised, or Glaze surfaces. A card is not automatically translucent. Interactive cards must have a clear focus/hover affordance and cannot hide separate nested actions behind one ambiguous click target.

## Navigation

Compact layouts may use bottom navigation, compact headers, drawers, or sheets. Expanded layouts may use sidebars or navigation rails. Current location must be visually and semantically identifiable. Navigation transforms by breakpoint rather than simply shrinking.

## Dialogs, menus, sheets, and overlays

Overlays use the Overlay surface level, trap focus only while modal, restore focus on close, support Escape when appropriate, expose a programmatic name, and remain readable without blur/translucency.

## Tables and dense data

Tables prioritize scanability and accessible header relationships. Compact layouts may transform tables into card/list presentations when horizontal compression would harm readability. Status must not be communicated by color alone.

## Feedback

Toasts, banners, status indicators, loading states, empty states, and errors are first-class components. Feedback is concise, actionable when possible, and announced to assistive technology when the state change requires it.

## Product-specific expression

Applications may vary accent emphasis, artwork, information density, navigation composition, hero treatments, data visualization, and specialized components. The goal is a family resemblance, not identical screens.
