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
PRIMARY_TEMPLATES = (
    REPOSITORY_ROOT / "core/templates/core/login.html",
    REPOSITORY_ROOT / "core/templates/core/overview.html",
    REPOSITORY_ROOT / "core/templates/core/tasks.html",
)


class GlazeUiContractTests(SimpleTestCase):
    """Keep identity, privacy, accessibility, and Glaze 1.2 semantics reviewable."""

    @staticmethod
    def _read(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_shared_shell_declares_private_goreecloud_identity(self):
        base = self._read(BASE_TEMPLATE)

        self.assertIn('data-glaze-ui="manager"', base)
        self.assertIn('data-glaze-version="1.2.0"', base)
        self.assertIn('data-glaze-surface="glaze"', base)
        self.assertIn('viewport-fit=cover', base)
        self.assertIn('content="noindex, nofollow, noarchive"', base)
        self.assertIn('name="referrer" content="same-origin"', base)
        self.assertIn("core/img/manager-mark.svg", base)
        self.assertIn("core/css/app.css", base)
        self.assertIn("core/css/glaze-ui.css", base)
        self.assertIn('href="#main-content"', base)
        self.assertIn('id="main-content" tabindex="-1"', base)

    def test_glaze_12_semantics_are_explicit_and_product_mapped(self):
        css = self._read(GLAZE_CSS)

        for contract in (
            '--glaze-contract-version: "1.2.0"',
            "--glaze-canvas: var(--bg)",
            "--glaze-surface: var(--surface)",
            "--glaze-surface-strong: var(--surface-strong)",
            "--glaze-accent: var(--accent)",
            "--glaze-info: var(--accent)",
            "--glaze-success: var(--good)",
            "--glaze-warning: var(--warning)",
            "--glaze-danger: var(--danger)",
            "--glaze-focus-ring: var(--accent)",
            "--glaze-selection: var(--accent-surface)",
            "--glaze-placeholder-opacity: .72",
            "--glaze-control-field-gap: .5rem",
            "--glaze-control-group-gap: 1rem",
            "--glaze-control-message-gap: .375rem",
            "--glaze-target-min: 2.75rem",
            "--glaze-state-hover: .08",
            "--glaze-state-pressed: .12",
            "--glaze-state-focus: .14",
            "--glaze-state-selected: .12",
            "--glaze-gutter: 1rem",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, css)

        self.assertIn("min-block-size: var(--glaze-target-min)", css)
        self.assertIn("outline: 3px solid var(--glaze-focus-ring)", css)
        self.assertIn("background: var(--glaze-selection)", css)
        self.assertIn("opacity: var(--glaze-placeholder-opacity)", css)
        self.assertIn("gap: var(--glaze-control-field-gap)", css)
        self.assertIn("gap: var(--glaze-control-group-gap)", css)

    def test_manager_preserves_native_form_controls_under_glaze_12(self):
        css = self._read(GLAZE_CSS)
        login = self._read(REPOSITORY_ROOT / "core/templates/core/login.html")

        self.assertIn("input:not([type=\"hidden\"])", css)
        self.assertIn("select", css)
        self.assertIn("textarea", css)
        self.assertIn("Username {{ form.username }}", login)
        self.assertIn("Password {{ form.password }}", login)
        self.assertIn('role="alert"', login)
        self.assertNotIn("role=\"switch\"", login)

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
