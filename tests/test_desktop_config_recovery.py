import importlib
import stat
import sys
import types
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
DESKTOP_ROOT = REPOSITORY_ROOT / "desktop-client"
DESKTOP_PACKAGE_ROOT = DESKTOP_ROOT / "goreecloud_manager"
_TEST_PACKAGE_NAME = "goreecloud_manager_desktop_tests"

# The repository also contains the Django project package named
# ``goreecloud_manager``. Django imports that package before discovering these
# tests, so importing the desktop client by its production package name would
# collide with the already-loaded project package. Mount the desktop package
# under a test-only alias while preserving normal relative imports inside it.
_test_package = types.ModuleType(_TEST_PACKAGE_NAME)
_test_package.__path__ = [str(DESKTOP_PACKAGE_ROOT)]
sys.modules[_TEST_PACKAGE_NAME] = _test_package
_recovery = importlib.import_module(f"{_TEST_PACKAGE_NAME}.recovery")

ConfigRecoveryError = _recovery.ConfigRecoveryError
prepare_config_recovery = _recovery.prepare_config_recovery
protect_config_before_write = _recovery.protect_config_before_write
recovery_config_path = _recovery.recovery_config_path


_VALID_CONFIG = """\
meta:
  schema_version: 4
app:
  title: GoreeCloud Manager
  environment: Home / Family Cloud
  appearance: system
monitoring:
  mode: local
  auto_refresh_seconds: 60
  ssh_timeout_seconds: 6
server:
  name: goreecloud-vps-01
  host: ""
  port: 22
  user: ""
  identity_file: ""
services: []
"""


class DesktopConfigRecoveryTests(TestCase):
    def test_protection_copy_is_private_and_exact(self):
        with TemporaryDirectory() as temporary_directory:
            primary = Path(temporary_directory) / "config.yaml"
            primary.write_text(_VALID_CONFIG, encoding="utf-8")

            recovery = protect_config_before_write(primary)

            self.assertEqual(recovery, recovery_config_path(primary))
            self.assertEqual(recovery.read_text(encoding="utf-8"), _VALID_CONFIG)
            mode = stat.S_IMODE(recovery.stat().st_mode)
            self.assertEqual(mode, 0o600)

    def test_invalid_primary_is_restored_from_valid_recovery_copy(self):
        with TemporaryDirectory() as temporary_directory:
            primary = Path(temporary_directory) / "config.yaml"
            primary.write_text(_VALID_CONFIG, encoding="utf-8")
            recovery = protect_config_before_write(primary)
            primary.write_text("app: [unterminated\n", encoding="utf-8")

            notice = prepare_config_recovery(primary)

            self.assertIn("Recovered config.yaml", notice)
            self.assertEqual(primary.read_text(encoding="utf-8"), _VALID_CONFIG)
            self.assertEqual(recovery.read_text(encoding="utf-8"), _VALID_CONFIG)
            self.assertEqual(stat.S_IMODE(primary.stat().st_mode), 0o600)

    def test_empty_primary_is_restored_from_valid_recovery_copy(self):
        with TemporaryDirectory() as temporary_directory:
            primary = Path(temporary_directory) / "config.yaml"
            primary.write_text(_VALID_CONFIG, encoding="utf-8")
            recovery = protect_config_before_write(primary)
            primary.write_text("", encoding="utf-8")

            notice = prepare_config_recovery(primary)

            self.assertIn("Recovered config.yaml", notice)
            self.assertEqual(primary.read_text(encoding="utf-8"), _VALID_CONFIG)
            self.assertEqual(recovery.read_text(encoding="utf-8"), _VALID_CONFIG)

    def test_invalid_primary_and_invalid_recovery_fail_closed(self):
        with TemporaryDirectory() as temporary_directory:
            primary = Path(temporary_directory) / "config.yaml"
            recovery = recovery_config_path(primary)
            primary.write_text("app: [unterminated\n", encoding="utf-8")
            recovery.write_text("server: [unterminated\n", encoding="utf-8")

            with self.assertRaises(ConfigRecoveryError):
                prepare_config_recovery(primary)

            self.assertEqual(primary.read_text(encoding="utf-8"), "app: [unterminated\n")

    def test_non_mapping_root_is_not_accepted_as_recoverable_configuration(self):
        with TemporaryDirectory() as temporary_directory:
            primary = Path(temporary_directory) / "config.yaml"
            primary.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

            with self.assertRaises(ConfigRecoveryError):
                prepare_config_recovery(primary)
