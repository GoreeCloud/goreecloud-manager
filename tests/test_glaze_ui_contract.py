"""Source-level contract tests for GoreeCloud Manager's GLAZE UI V1.1 shell."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = REPOSITORY_ROOT / "core/templates/core/base.html"
APP_CSS = REPOSITORY_ROOT / "core/static/core/css/app.css"
GLAZE_CSS = REPOSITORY_ROOT / "core/static/core/css/glaze-ui.css"
GLAZE_LOCK = REPOSITORY_ROOT / "core/static/core/glaze.lock.json"
GLAZE_VENDOR = REPOSITORY_ROOT / "core/static/core/glaze"
THEME_JS = REPOSITORY_ROOT / "core/static/core/js/theme.js"
MANAGER_MARK = REPOSITORY_ROOT / "core/static/core/img/manager-mark.svg"
GLAZE_DOC = REPOSITORY_ROOT / "docs/glaze-ui.md"
PRIMARY_TEMPLATES = (
    REPOSITORY_ROOT / "core/templates/core/login.html",
    REPOSITORY_ROOT / "core/templates/core/overview.html",
    REPOSITORY_ROOT / "core/templates/core/tasks.html",
)

EXPECTED_RELEASE = "15cc76d2bcd4065552dc31c77145b63f34d9e7b2"
EXPECTED_FILES = {
    "css/glaze-v1.1.0.css": "c689e8e58cefc49f931862996a1e0e871497fe88",
    "css/glaze-v1.0.0.css": "eca2209c5d678830f92907b4d44ea6cc5b1c8536",
    "css/glaze-v1.1.css": "aa0250f01151f17cd3c77e9a67544c6af4b5aa32",
    "css/glaze-v1.1-appearance.css": "c4e10e043d537c68f1e4a5f97bdb8b6f0d371dce",
    "css/glaze-v1.foundation.css": "b01051203831ce011c08f37b79f2e2032d34d0c8",
    "css/glaze-v1.components.css": "f74d5d4a4dd3ae22354812260e06a042d3928507",
    "css/glaze-v1.components.adaptive.css": "e174ea4923ec1ac6e1eb52d7ee33c14f2f77d5ca",
    "css/glaze-v1.components.runtime.css": "a89356172d74b66c62cfda198ae827fe9b71c520",
    "css/glaze-v1.structure.css": "9781c3e162edbac9fce67b93fd3287fdacbcd504",
    "css/glaze-v1.overlay.css": "cb937fae3166289c9c935d7ae25cefe3f82f3ec0",
    "css/glaze-v1.advanced.css": "d6e60a9b23354b1dc62dafac284c93b772e582a4",
    "css/glaze-v1.visual-refinement.css": "f5696fdb81f8deda3ce75e112989d772b7d74909",
    "css/glaze-v1.optical-reachability.css": "6123cff22f06b4c537156a1285e2664763f33316",
}


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    prefix = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(prefix + data, usedforsecurity=False).hexdigest()


class GlazeUiContractTests(SimpleTestCase):
    """Keep V1.1 source identity, authority, accessibility, and UI boundaries reviewable."""

    @staticmethod
    def _read(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_shared_shell_activates_current_stable_v11(self):
        base = self._read(BASE_TEMPLATE)

        self.assertIn('data-glaze-ui="manager"', base)
        self.assertIn('data-glaze-version="1.1"', base)
        self.assertIn('name="goreecloud-glaze-ui" content="1.1.0"', base)
        self.assertIn("core/glaze/glaze-v1.1.0.css", base)
        self.assertIn('data-glaze-ui="1.1.0"', base)
        self.assertIn("glz11-glaze", base)
        self.assertIn("glz11-nav", base)
        self.assertIn("glz11-nav-item", base)
        self.assertIn("glz11-button", base)
        self.assertIn('viewport-fit=cover', base)
        self.assertIn('content="noindex, nofollow, noarchive"', base)
        self.assertIn('name="referrer" content="same-origin"', base)
        self.assertIn("core/img/manager-mark.svg", base)
        self.assertIn('href="#main-content"', base)
        self.assertIn('id="main-content" tabindex="-1"', base)
        self.assertNotIn('data-glaze-version="1.3.0"', base)

    def test_v11_lock_is_exact_and_runtime_local(self):
        lock = json.loads(GLAZE_LOCK.read_text(encoding="utf-8"))

        self.assertEqual(lock["schema"], "goreecloud.glaze-ui.web-source-manifest.v1")
        self.assertEqual(lock["product"], "GLAZE UI V1.1")
        self.assertEqual(lock["version"], "1.1.0")
        self.assertEqual(lock["tag"], "v1.1.0")
        self.assertEqual(lock["release_commit"], EXPECTED_RELEASE)
        self.assertEqual(lock["entrypoint"], "css/glaze-v1.1.0.css")
        self.assertIs(lock["runtime_network_dependency_required"], False)
        self.assertEqual(lock["files"], EXPECTED_FILES)

    def test_committed_v11_source_graph_matches_every_locked_git_blob(self):
        self.assertTrue(GLAZE_VENDOR.is_dir())
        expected_names = {Path(path).name for path in EXPECTED_FILES}
        actual_names = {
            path.name
            for path in GLAZE_VENDOR.iterdir()
            if path.is_file() and not path.is_symlink()
        }
        self.assertEqual(actual_names, expected_names)

        for upstream_path, expected_sha in EXPECTED_FILES.items():
            path = GLAZE_VENDOR / Path(upstream_path).name
            with self.subTest(path=upstream_path):
                self.assertTrue(path.is_file())
                self.assertFalse(path.is_symlink())
                self.assertEqual(git_blob_sha(path), expected_sha)

    def test_manager_v11_adapter_preserves_authority_and_material_boundaries(self):
        css = self._read(GLAZE_CSS)

        for contract in (
            '--glaze-contract-version: "1.1.0"',
            "--glaze-canvas: var(--glz1-canvas, var(--bg))",
            "--glaze-surface: var(--glz1-base, var(--surface))",
            "--glaze-text: var(--glz1-text-primary, var(--text))",
            "--glaze-success: var(--good)",
            "--glaze-warning: var(--warning)",
            "--glaze-danger: var(--danger)",
            "--glaze-target-min: var(--glz11-target-min, 48px)",
            "--glaze-target-assisted: var(--glz1-target-assisted, 56px)",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, css)

        self.assertIn('site-header[data-glaze-material="functional-glass"]', css)
        self.assertIn("Durable operational and authentication content remains Solid/Raised", css)
        self.assertIn("background-image: none", css)
        self.assertIn('data-glaze-action-group="adaptive"', self._read(BASE_TEMPLATE))
        self.assertIn('data-glaze-reachability="compact"', self._read(BASE_TEMPLATE))

    def test_canonical_v11_source_supplies_48_and_56_pixel_target_contracts(self):
        v11 = self._read(GLAZE_VENDOR / "glaze-v1.1.css")
        foundation = self._read(GLAZE_VENDOR / "glaze-v1.foundation.css")

        self.assertIn("--glz11-target-min: 48px", v11)
        self.assertIn('data-glz-touch-assistance="true"', v11)
        self.assertIn("--glz11-target-min: 56px", v11)
        self.assertIn("--glz1-target-shell: 48px", foundation)
        self.assertIn("--glz1-target-assisted: 56px", foundation)

    def test_manager_preserves_native_form_controls_under_v11(self):
        css = self._read(GLAZE_CSS)
        login = self._read(REPOSITORY_ROOT / "core/templates/core/login.html")

        self.assertIn('input:not([type="hidden"])', css)
        self.assertIn("select", css)
        self.assertIn("textarea", css)
        self.assertIn("Username {{ form.username }}", login)
        self.assertIn("Password {{ form.password }}", login)
        self.assertIn('role="alert"', login)
        self.assertNotIn('role="switch"', login)

    def test_v11_documentation_pins_stable_source_and_acceptance_boundary(self):
        doc = self._read(GLAZE_DOC)

        self.assertIn("GLAZE UI V1.1 / 1.1.0", doc)
        self.assertIn(EXPECTED_RELEASE, doc)
        self.assertIn("48", doc)
        self.assertIn("56", doc)
        self.assertIn("Deep Dark", doc)
        self.assertIn("Solid/Raised", doc)
        self.assertIn("does not establish", doc)

    def test_explicit_v11_appearance_is_applied_before_stylesheets(self):
        base = self._read(BASE_TEMPLATE)
        theme_script = base.index("core/js/theme.js")
        app_stylesheet = base.index("core/css/app.css")
        stable_stylesheet = base.index("core/glaze/glaze-v1.1.0.css")
        adapter_stylesheet = base.index("core/css/glaze-ui.css")

        self.assertLess(theme_script, app_stylesheet)
        self.assertLess(theme_script, stable_stylesheet)
        self.assertLess(theme_script, adapter_stylesheet)
        self.assertLess(app_stylesheet, stable_stylesheet)
        self.assertLess(stable_stylesheet, adapter_stylesheet)
        self.assertNotRegex(base, r'<script[^>]*\bdefer\b[^>]*core/js/theme\.js')

        theme = self._read(THEME_JS)
        self.assertIn('const storageKey = "goreecloud-manager-theme"', theme)
        self.assertIn('"deep-dark"', theme)
        self.assertIn('root.setAttribute("data-glz-appearance", value)', theme)
        self.assertIn('root.removeAttribute("data-glz-appearance")', theme)
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
            ".nav-link:focus-visible",
            ".theme-toggle:focus-visible",
            ".link-button:focus-visible",
            "button:focus-visible",
            "input:focus-visible",
            "select:focus-visible",
            "textarea:focus-visible",
            "a:focus-visible",
        ):
            with self.subTest(control=control):
                self.assertIn(control, css)

    def test_user_interface_has_no_remote_browser_dependencies(self):
        product_sources = [
            BASE_TEMPLATE,
            APP_CSS,
            GLAZE_CSS,
            THEME_JS,
            MANAGER_MARK,
            *PRIMARY_TEMPLATES,
        ]

        for path in product_sources:
            text = self._read(path)
            with self.subTest(path=path.relative_to(REPOSITORY_ROOT)):
                self.assertIsNone(
                    re.search(r"(?:src|href)=[\"']https?://", text, flags=re.IGNORECASE)
                )
                self.assertIsNone(
                    re.search(r"url\(\s*[\"']?https?://", text, flags=re.IGNORECASE)
                )
                self.assertNotIn("@import", text.lower())

        for path in GLAZE_VENDOR.iterdir():
            if not path.is_file() or path.is_symlink():
                continue
            text = self._read(path)
            with self.subTest(vendor=path.name):
                self.assertNotRegex(text, r"https?://")
                for line in text.splitlines():
                    if "@import" in line:
                        self.assertRegex(line, r'@import\s+url\(["\']\./[^"\']+["\']\)')

    def test_manager_mark_is_static_and_script_free(self):
        mark = self._read(MANAGER_MARK).lower()

        self.assertIn("<svg", mark)
        self.assertNotIn("<script", mark)
        self.assertNotRegex(mark, r"(?:href|src)=[\"']https?://")

    def test_primary_surfaces_inherit_the_shared_v11_shell(self):
        for template in PRIMARY_TEMPLATES:
            text = self._read(template)
            with self.subTest(template=template.name):
                self.assertIn('{% extends "core/base.html" %}', text)
