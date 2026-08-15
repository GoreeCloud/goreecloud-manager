from pathlib import Path
from unittest import TestCase


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
DESKTOP_ROOT = REPOSITORY_ROOT / "desktop-client"
PACKAGE_ROOT = DESKTOP_ROOT / "goreecloud_manager"


class DesktopClientStabilityContractTests(TestCase):
    def test_desktop_python_sources_compile(self):
        for path in sorted(PACKAGE_ROOT.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            compile(source, str(path), "exec")

    def test_desktop_runtime_dependencies_are_exactly_pinned(self):
        requirements = {
            line.strip()
            for line in (DESKTOP_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertEqual(
            requirements,
            {
                "PySide6==6.11.1",
                "psutil==7.2.2",
                "PyYAML==6.0.3",
            },
        )

    def test_ssh_requires_preestablished_host_trust(self):
        for relative_path in ("health.py", "infrastructure.py"):
            source = (PACKAGE_ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn("StrictHostKeyChecking=yes", source)
            self.assertNotIn("StrictHostKeyChecking=accept-new", source)
            self.assertIn("SSH host identity is not trusted", source)

    def test_configuration_writes_are_private_and_atomic(self):
        source = (PACKAGE_ROOT / "config.py").read_text(encoding="utf-8")
        self.assertIn("_CONFIG_FILE_MODE = 0o600", source)
        self.assertIn("os.O_EXCL", source)
        self.assertIn("os.fsync", source)
        self.assertIn("os.replace", source)
        self.assertIn("os.chmod(path, _CONFIG_FILE_MODE)", source)
        self.assertIn("def _bounded_int", source)
        self.assertIn("def _parse_bool", source)

    def test_setup_checks_installed_dependency_graph(self):
        source = (DESKTOP_ROOT / "scripts" / "setup.sh").read_text(encoding="utf-8")
        self.assertIn("python -m pip install -r requirements.txt", source)
        self.assertIn("python -m pip check", source)
        self.assertNotIn("pip install --upgrade pip", source)

    def test_installer_stages_and_validates_before_replacing_current_install(self):
        source = (DESKTOP_ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        self.assertIn('.goreecloud-manager.stage.', source)
        self.assertIn('.goreecloud-manager.rollback.', source)
        self.assertIn('"$STAGE/.venv/bin/python" -m pip check', source)
        self.assertIn('"$STAGE/.venv/bin/python" -m compileall -q "$STAGE/goreecloud_manager"', source)
        self.assertLess(source.index('tar --exclude='), source.index('mv "$TARGET" "$BACKUP"'))
        self.assertLess(source.index('-m compileall -q'), source.index('mv "$TARGET" "$BACKUP"'))
        self.assertLess(source.index('mv "$TARGET" "$BACKUP"'), source.index('mv "$STAGE" "$TARGET"'))

    def test_installer_restores_previous_install_when_cutover_fails(self):
        source = (DESKTOP_ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        self.assertIn('if [[ -d "$BACKUP" && ! -e "$TARGET" ]]; then', source)
        self.assertIn('mv "$BACKUP" "$TARGET" || true', source)
        self.assertIn('if ! "$TARGET/scripts/install-desktop-entry.sh"; then', source)
        self.assertIn('mv "$BACKUP" "$TARGET"', source)
        self.assertIn('the previous installation was restored', source)

    def test_desktop_client_remains_read_only(self):
        source = (PACKAGE_ROOT / "infrastructure.py").read_text(encoding="utf-8").casefold()
        prohibited_commands = (
            "docker start ",
            "docker stop ",
            "docker restart ",
            "docker rm ",
            "docker kill ",
            "netbird up",
            "netbird down",
        )
        for command in prohibited_commands:
            self.assertNotIn(command, source)

    def test_stabilization_version_is_0_2_5(self):
        source = (PACKAGE_ROOT / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('__version__ = "0.2.5"', source)
