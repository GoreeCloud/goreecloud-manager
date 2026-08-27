"""Source-level contract tests for GoreeCloud Manager's Glaze UI shell."""

from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = REPOSITORY_ROOT / "core/templates/core/base.html"
APP_CSS = REPOSITORY_ROOT / "core/static/core/css/app.css"
GLAZE_CSS = REPOSITORY_ROOT / "core/static/core/css/glaze-ui.css"
THEME_JS = REPOSITORY_ROOT / "core/static/core/js/theme.js"
MANAGER_MARK = REPOSITORY_ROOT / "core/static/core/img/manager-mark.svg"
GLAZE_DOC = REPOSITORY_ROOT / "docs/glaze-ui.md"
PRIMARY_TEMPLATES = (
    REPOSITORY_ROOT / "core/templates/core/login.html",
    REPOSITORY_ROOT / "core/templates/core/overview.html",
    REPOSITORY_ROOT / "core/templates/core/tasks.html",
)


class GlazeUiContractTests(SimpleTestCase):
    """Keep identity, privacy, accessibility, and Glaze 1.5 semantics reviewable."""

    @staticmethod
    def _read(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_shared_shell_declares_private_goreecloud_identity(self):
        base = self._read(BASE_TEMPLATE)

        self.assertIn('data-glaze-ui="manager"', base)
        self.assertIn('data-glaze-version="1.5.0"', base)
        self.assertIn('data-glaze-density="comfortable"', base)
        self.assertIn('data-glaze-form-factor="responsive"', base)
        self.assertIn('data-glaze-surface="glaze"', base)
        self.assertIn('data-glaze-material="functional-glass"', base)
        self.assertIn('data-glaze-depth="navigation"', base)
        self.assertIn('data-glaze-icon-role="application"', base)
        self.assertIn('data-glaze-icon-role="security"', base)
        self.assertIn('data-glaze-action-group="adaptive"', base)
        self.assertIn('data-glaze-reachability="compact"', base)
        self.assertIn('viewport-fit=cover', base)
        self.assertIn('content="noindex, nofollow, noarchive"', base)
        self.assertIn('name="referrer" content="same-origin"', base)
        self.assertIn("core/img/manager-mark.svg", base)
        self.assertIn("core/css/app.css", base)
        self.assertIn("core/css/glaze-ui.css", base)
        self.assertIn('href="#main-content"', base)
        self.assertIn('id="main-content" tabindex="-1"', base)
        self.assertNotIn('data-glaze-version="1.3.0"', base)

    def test_glaze_15_semantics_are_explicit_and_product_mapped(self):
        css = self._read(GLAZE_CSS)

        for contract in (
            '--glaze-contract-version: "1.5.0"',
            "--glaze-canvas: var(--bg)",
            "--glaze-surface: var(--surface)",
            "--glaze-surface-strong: var(--surface-strong)",
            "--glaze-accent: var(--accent)",
            "--glaze-information: var(--accent)",
            "--glaze-success: var(--good)",
            "--glaze-warning: var(--warning)",
            "--glaze-danger: var(--danger)",
            "--glaze-privacy: var(--accent-strong)",
            "--glaze-security: var(--accent-strong)",
            "--glaze-online: var(--good)",
            "--glaze-offline: var(--text-muted)",
            "--glaze-syncing: var(--accent)",
            "--glaze-protected: var(--good)",
            "--glaze-restricted: var(--warning)",
            "--glaze-unavailable: var(--text-muted)",
            "--glaze-focus-ring: var(--accent)",
            "--glaze-selection: var(--accent-surface)",
            "--glaze-placeholder-opacity: .72",
            "--glaze-target-min: 2.75rem",
            "--glaze-shape-compact: .625rem",
            "--glaze-shape-standard: 1rem",
            "--glaze-shape-expressive: 1.375rem",
            "--glaze-shape-hero: 2rem",
            "--glaze-shape-pressed: .75rem",
            "--glaze-glass-functional-blur: 18px",
            "--glaze-depth-base: 0",
            "--glaze-depth-navigation: 20",
            "--glaze-depth-overlay: 40",
            "--glaze-motion-instant: 0ms",
            "--glaze-motion-micro: 90ms",
            "--glaze-motion-short: 160ms",
            "--glaze-motion-medium: 240ms",
            "--glaze-motion-long: 360ms",
            "--glaze-motion-ambient: 700ms",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, css)

        self.assertIn('site-header[data-glaze-material="functional-glass"]', css)
        self.assertIn("background: var(--glaze-surface-strong)", css)
        self.assertIn("border-radius: var(--glaze-shape-hero)", css)
        self.assertIn("background-color var(--glaze-motion-short)", css)
        self.assertIn("transform var(--glaze-motion-short)", css)
        self.assertIn("border-radius: var(--glaze-shape-pressed)", css)
        self.assertNotIn('--glaze-contract-version: "1.3.0"', css)

    def test_glaze_15_layout_density_and_measure_contract_is_explicit(self):
        css = self._read(GLAZE_CSS)
        base = self._read(BASE_TEMPLATE)

        for contract in (
            "--glaze-space-2: 2px",
            "--glaze-space-4: 4px",
            "--glaze-space-8: 8px",
            "--glaze-space-12: 12px",
            "--glaze-space-16: 16px",
            "--glaze-space-24: 24px",
            "--glaze-space-32: 32px",
            "--glaze-space-48: 48px",
            "--glaze-space-64: 64px",
            "--glaze-space-96: 96px",
            "--glaze-measure-prose: 72ch",
            "--glaze-measure-form: 720px",
            "--glaze-measure-standard: 1200px",
            "--glaze-measure-wide: 1600px",
            "min-width: 600px",
            "max-width: 1023px",
            "min-width: 1024px",
            "max-width: 1599px",
            "min-width: 1600px",
            "--glaze-gutter: var(--glaze-space-48)",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, css)

        self.assertIn('data-glaze-density="comfortable"', base)
        self.assertIn("min-block-size: var(--glaze-target-min)", css)

    def test_manager_preserves_native_form_and_state_semantics(self):
        css = self._read(GLAZE_CSS)
        login = self._read(REPOSITORY_ROOT / "core/templates/core/login.html")

        self.assertIn('input:not([type="hidden"])', css)
        self.assertIn("select", css)
        self.assertIn("textarea", css)
        self.assertIn("button:disabled", css)
        self.assertIn('[aria-disabled="true"]', css)
        self.assertIn("input[readonly]", css)
        self.assertIn('[aria-readonly="true"]', css)
        self.assertIn('[aria-busy="true"]', css)
        self.assertIn("Username {{ form.username }}", login)
        self.assertIn("Password {{ form.password }}", login)
        self.assertIn('role="alert"', login)
        self.assertNotIn('role="switch"', login)

    def test_glaze_15_documentation_pins_stable_source_and_material_boundary(self):
        doc = self._read(GLAZE_DOC)

        self.assertIn("Glaze UI 1.5.0 Stable", doc)
        self.assertIn("2e1618397f6ebcdd254a76bfdd7e98846f2c5aa3", doc)
        self.assertIn("Functional Glass", doc)
        self.assertIn("Solid/Raised", doc)
        self.assertIn("adaptive color", doc.lower())
        self.assertIn("material and depth", doc.lower())
        self.assertIn("interaction state", doc.lower())
        self.assertIn("comfortable", doc)
        self.assertIn("Glaze Motion", doc)
        self.assertIn("Experimental", doc)

    def test_explicit_appearance_is_applied_before_stylesheets(self):
        base = self._read(BASE_TEMPLATE)
        theme_script = base.index("core/js/theme.js")
        app_stylesheet = base.index("core/css/app.css")
        glaze_stylesheet = base.index("core/css/glaze-ui.css")

        self.assertLess(theme_script, app_stylesheet)
        self.assertLess(theme_script, glaze_stylesheet)
        self.assertNotRegex(
            base,
            r'<script[^>]*\bdefer\b[^>]*core/js/theme\.js',
        )

        theme = self._read(THEME_JS)
        self.assertIn('const storageKey = "goreecloud-manager-theme"', theme)
        self.assertIn("applyRootAppearance(current);", theme)
        self.assertIn("DOMContentLoaded", theme)

    def test_glaze_accessibility_fallbacks_are_source_controlled(self):
        css = self._read(APP_CSS) + "\n" + self._read(GLAZE_CSS)

        for contract in (
            "prefers-reduced-motion: reduce",
            "prefers-reduced-transparency: reduce",
            'data-glaze-reduced-transparency="true"',
            "prefers-contrast: more",
            "forced-colors: active",
            "@supports not (backdrop-filter: blur(1px))",
            "transition-duration: .01ms",
            "backdrop-filter: none",
            "outline: 2px solid Highlight",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, css)

        for control in (
            "button:focus-visible",
            "input:focus-visible",
            "select:focus-visible",
            "textarea:focus-visible",
            "a:focus-visible",
        ):
            with self.subTest(control=control):
                self.assertIn(control, css)

    def test_user_interface_has_no_remote_browser_dependencies(self):
        sources = [
            BASE_TEMPLATE,
            APP_CSS,
            GLAZE_CSS,
            THEME_JS,
            MANAGER_MARK,
            *PRIMARY_TEMPLATES,
        ]

        for path in sources:
            text = self._read(path)
            with self.subTest(path=path.relative_to(REPOSITORY_ROOT)):
                self.assertIsNone(
                    re.search(r"(?:src|href)=[\"']https?://", text, flags=re.IGNORECASE)
                )
                self.assertIsNone(
                    re.search(r"url\(\s*[\"']?https?://", text, flags=re.IGNORECASE)
                )
                self.assertNotIn("@import", text.lower())

    def test_manager_mark_is_static_and_script_free(self):
        mark = self._read(MANAGER_MARK).lower()

        self.assertIn("<svg", mark)
        self.assertNotIn("<script", mark)
        self.assertNotRegex(mark, r"(?:href|src)=[\"']https?://")

    def test_primary_surfaces_inherit_the_shared_glaze_shell(self):
        for template in PRIMARY_TEMPLATES:
            text = self._read(template)
            with self.subTest(template=template.name):
                self.assertIn('{% extends "core/base.html" %}', text)
