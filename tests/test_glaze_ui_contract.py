"""Source-level contract tests for GoreeCloud Manager's Glaze UI 2.2 surfaces."""

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
DESKTOP_THEME = REPOSITORY_ROOT / "desktop-client/goreecloud_manager/theme.py"
ANDROID_ACTIVITY = REPOSITORY_ROOT / "android-client/app/src/main/java/com/goreecloud/manager/MainActivity.kt"
PRIMARY_TEMPLATES = (
    REPOSITORY_ROOT / "core/templates/core/login.html",
    REPOSITORY_ROOT / "core/templates/core/overview.html",
    REPOSITORY_ROOT / "core/templates/core/tasks.html",
)
GLAZE_VERSION = "2.2.0"
GLAZE_RELEASE_REVISION = "6731098b28dd0393faa878c70d989a221d714a20"


class GlazeUiContractTests(SimpleTestCase):
    """Keep Manager's web/native 2.2 mapping explicit and separately reviewable."""

    @staticmethod
    def _read(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_shared_shell_declares_private_goreecloud_identity_and_glaze_22(self):
        base = self._read(BASE_TEMPLATE)

        self.assertIn('name="goreecloud-glaze-ui" content="2.2.0"', base)
        self.assertIn('data-glaze-ui="manager"', base)
        self.assertIn('data-glaze-version="2.2.0"', base)
        self.assertIn('class="glz22-workspace"', base)
        self.assertIn('site-header glz22-system-overlay', base)
        self.assertIn('data-glaze-surface="system-overlay"', base)
        self.assertIn('data-glaze-material="functional-glass"', base)
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

        for stale in ('data-glaze-version="1.3.0"', 'data-glaze-version="2.0.0"', 'data-glaze-version="2.1.0"'):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, base)

    def test_glaze_22_semantics_are_explicit_and_product_mapped(self):
        css = self._read(GLAZE_CSS)

        for contract in (
            '--glaze-contract-version: "2.2.0"',
            f'--glaze-source-revision: "{GLAZE_RELEASE_REVISION}"',
            "--glz22-target-shell: 48px",
            "--glz22-target-assisted: 56px",
            "--glz22-system-panel-budget: 1",
            "--glaze-canvas: var(--bg)",
            "--glaze-surface-strong: var(--surface-strong)",
            "--glaze-focus-ring: var(--accent)",
            "--glaze-overlay-blur: 22px",
            "--glaze-motion-spatial-standard: 250ms",
            '[data-glz-input="touch"]',
            '[data-glz-touch-assistance="true"]',
            '[data-glz-transparency="reduced"]',
            '[data-glz-text-scale="200"]',
            'html[data-mode="large-text"]',
            'html[data-mode="increased-contrast"]',
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, css)

        self.assertIn('site-header.glz22-system-overlay[data-glaze-material="functional-glass"]', css)
        self.assertIn("background: var(--glaze-surface-strong)", css)
        self.assertIn("glz22-system-panel .glz22-system-panel", css)
        self.assertIn("backdrop-filter: none", css)
        self.assertIn("border-radius: var(--glaze-shape-pressed)", css)
        self.assertNotIn('--glaze-contract-version: "1.3.0"', css)
        self.assertNotIn("@import", css.lower())
        self.assertNotIn(".candidate.css", css.lower())

    def test_manager_preserves_native_form_controls_under_glaze_22(self):
        css = self._read(GLAZE_CSS)
        login = self._read(REPOSITORY_ROOT / "core/templates/core/login.html")

        self.assertIn('input:not([type="hidden"])', css)
        self.assertIn("select", css)
        self.assertIn("textarea", css)
        self.assertIn("Username {{ form.username }}", login)
        self.assertIn("Password {{ form.password }}", login)
        self.assertIn('role="alert"', login)
        self.assertNotIn('role="switch"', login)

    def test_glaze_22_documentation_pins_stable_source_and_acceptance_boundary(self):
        doc = self._read(GLAZE_DOC)

        for marker in (
            "Glaze UI 2.2.0 Stable",
            GLAZE_RELEASE_REVISION,
            "GoreeCloud/goreecloud-glaze-ui",
            "historical rollback baseline is Glaze UI 2.1.0",
            "System Overlay",
            "one dominant System Panel",
            "nested backdrop blur is prohibited",
            "48px minimum shell/control floor",
            "56px Touch Assistance",
            "200% text",
            "desktop client",
            "Android client",
            "does not automatically satisfy",
            "Production eligibility remains false",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, doc)

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

    def test_desktop_client_declares_native_glaze_22_mapping(self):
        desktop = self._read(DESKTOP_THEME)

        for marker in (
            'GLAZE_UI_VERSION = "2.2.0"',
            f'GLAZE_UI_SOURCE_REVISION = "{GLAZE_RELEASE_REVISION}"',
            "GLAZE_TARGET_PX = 48",
            "GLAZE_TOUCH_ASSISTED_PX = 56",
            "GLAZE_SYSTEM_PANEL_BUDGET = 1",
            "def control_target_px(touch_assistance: bool = False)",
            'app.setProperty("goreecloudGlazeVersion", GLAZE_UI_VERSION)',
            'app.setProperty("goreecloudGlazeSourceRevision", GLAZE_UI_SOURCE_REVISION)',
            'app.setProperty("goreecloudTouchAssistance", bool(touch_assistance))',
            'app.setProperty("goreecloudTargetMinimum", target)',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, desktop)

        self.assertIn("min-height: {control_target}px", desktop)
        self.assertNotIn("backdrop-filter", desktop.lower())

    def test_android_client_declares_secure_native_glaze_22_mapping(self):
        android = self._read(ANDROID_ACTIVITY)

        for marker in (
            'const val GLAZE_UI_VERSION = "2.2.0"',
            f'const val GLAZE_UI_SOURCE_REVISION = "{GLAZE_RELEASE_REVISION}"',
            "const val GLAZE_TARGET_DP = 48",
            "const val GLAZE_TOUCH_ASSISTED_DP = 56",
            "const val GLAZE_SYSTEM_PANEL_BUDGET = 1",
            "isTouchExplorationEnabled",
            "minimumHeight = target",
            "minWidth = target",
            "ACCESSIBILITY_LIVE_REGION_POLITE",
            "MIXED_CONTENT_NEVER_ALLOW",
            "setAcceptThirdPartyCookies(this, false)",
            'uri.scheme == "https" && uri.host == managerUri.host',
            "handler.cancel()",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, android)

    def test_user_interface_has_no_remote_browser_presentation_dependencies(self):
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
