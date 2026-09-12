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
    """Keep Manager's current Glaze UI 2.1 source contract reviewable."""

    @staticmethod
    def _read(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_shared_shell_declares_current_goreecloud_identity(self):
        base = self._read(BASE_TEMPLATE)
        for contract in (
            'data-glaze-ui="manager"',
            'data-glaze-version="2.1.0"',
            'data-glaze-density="comfortable"',
            'data-glaze-form-factor="responsive"',
            'data-glaze-touch-assistance="false"',
            'data-glaze-surface="interaction"',
            'data-glaze-material-level="soft-glaze"',
            'data-glaze-clarity="balanced"',
            'data-glaze-depth="navigation"',
            'data-glaze-icon-role="application"',
            'data-glaze-icon-role="security"',
            'data-glaze-action-group="adaptive"',
            'data-glaze-reachability="compact"',
            'data-glaze-material-level="surface"',
            'viewport-fit=cover',
            'content="noindex, nofollow, noarchive"',
            'name="referrer" content="same-origin"',
            'href="#main-content"',
            'id="main-content" tabindex="-1"',
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, base)
        self.assertNotIn('data-glaze-version="1.5.0"', base)
        self.assertNotIn('data-glaze-version="1.3.0"', base)

    def test_glaze_21_semantics_and_interaction_floors_are_explicit(self):
        css = self._read(GLAZE_CSS)
        for contract in (
            '--glaze-contract-version: "2.1.0"',
            "--glaze-canvas: var(--bg)",
            "--glaze-surface: var(--surface)",
            "--glaze-surface-raised: var(--surface-strong)",
            "--glaze-accent: var(--accent)",
            "--glaze-positive: var(--good)",
            "--glaze-security: var(--accent-strong)",
            "--glaze-privacy: var(--accent-strong)",
            "--glaze-target-min: 48px",
            "--glaze-target-touch-assistance: 56px",
            'body[data-glaze-touch-assistance="true"]',
            "--glaze-target-min: var(--glaze-target-touch-assistance)",
            'site-header[data-glaze-material-level="soft-glaze"]',
            "background: var(--glaze-surface-raised)",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, css)
        self.assertNotIn('--glaze-contract-version: "1.5.0"', css)

    def test_glaze_21_uses_current_spacing_density_and_form_factor_signals(self):
        css = self._read(GLAZE_CSS)
        for contract in (
            "--glaze-space-4: 4px",
            "--glaze-space-8: 8px",
            "--glaze-space-12: 12px",
            "--glaze-space-16: 16px",
            "--glaze-space-20: 20px",
            "--glaze-space-24: 24px",
            "--glaze-space-32: 32px",
            "--glaze-space-48: 48px",
            "--glaze-measure-prose: 72ch",
            "--glaze-measure-form: 720px",
            "min-width: 600px",
            "max-width: 1023px",
            "min-width: 1024px",
            "max-width: 1599px",
            "min-width: 1600px",
            "min-block-size: var(--glaze-target-min)",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, css)

    def test_manager_preserves_native_form_and_state_semantics(self):
        css = self._read(GLAZE_CSS)
        login = self._read(REPOSITORY_ROOT / "core/templates/core/login.html")
        for contract in (
            'input:not([type="hidden"])',
            "select",
            "textarea",
            "button:disabled",
            '[aria-disabled="true"]',
            "input[readonly]",
            '[aria-readonly="true"]',
            '[aria-busy="true"]',
        ):
            self.assertIn(contract, css)
        self.assertIn("Username {{ form.username }}", login)
        self.assertIn("Password {{ form.password }}", login)
        self.assertIn('role="alert"', login)

    def test_glaze_21_documentation_pins_release_and_acceptance_boundary(self):
        doc = self._read(GLAZE_DOC)
        for contract in (
            "Glaze UI 2.1.0 Stable",
            "c49113eb8b93c267613fdf1bbca1f814495acad7",
            "Content is solid. Interaction is glazed.",
            "Soft Glaze",
            "48px",
            "56px",
            "Mobile 390×844",
            "Tablet 820×1180",
            "Desktop 1280×900",
            "Wide Desktop 1600×1000",
            "Source conformance is necessary but not sufficient",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, doc)
        self.assertNotIn("targets **Glaze UI 1.5.0 Stable**", doc)

    def test_explicit_appearance_is_applied_before_stylesheets(self):
        base = self._read(BASE_TEMPLATE)
        theme_script = base.index("core/js/theme.js")
        app_stylesheet = base.index("core/css/app.css")
        glaze_stylesheet = base.index("core/css/glaze-ui.css")
        self.assertLess(theme_script, app_stylesheet)
        self.assertLess(theme_script, glaze_stylesheet)
        self.assertNotRegex(base, r'<script[^>]*\bdefer\b[^>]*core/js/theme\.js')
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
            "outline: 3px solid Highlight",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, css)

    def test_user_interface_has_no_remote_browser_dependencies(self):
        sources = [BASE_TEMPLATE, APP_CSS, GLAZE_CSS, THEME_JS, MANAGER_MARK, *PRIMARY_TEMPLATES]
        for path in sources:
            text = self._read(path)
            with self.subTest(path=path.relative_to(REPOSITORY_ROOT)):
                self.assertIsNone(re.search(r"(?:src|href)=[\"']https?://", text, flags=re.IGNORECASE))
                self.assertIsNone(re.search(r"url\(\s*[\"']?https?://", text, flags=re.IGNORECASE))
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
