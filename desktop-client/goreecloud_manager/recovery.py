from __future__ import annotations

from pathlib import Path

import yaml

from .config import _write_text_atomically, user_config_path


class ConfigRecoveryError(RuntimeError):
    """Raised when neither the active nor recovery configuration is usable."""


def recovery_config_path(path: Path | None = None) -> Path:
    primary = path or user_config_path()
    return primary.with_name(f"{primary.name}.recovery")


def _validated_config_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigRecoveryError(f"Invalid YAML in {path.name}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigRecoveryError(
            f"Invalid configuration structure in {path.name}: the YAML root must be a mapping."
        )
    return text


def protect_config_before_write(path: Path | None = None) -> Path | None:
    """Preserve the currently valid user configuration before replacing it."""
    primary = path or user_config_path()
    if not primary.exists():
        return None

    text = _validated_config_text(primary)
    recovery = recovery_config_path(primary)
    _write_text_atomically(recovery, text)
    return recovery


def prepare_config_recovery(path: Path | None = None) -> str:
    """Validate the active config and recover it from the last-known-good copy when needed."""
    primary = path or user_config_path()
    if not primary.exists():
        return ""

    try:
        _validated_config_text(primary)
    except (ConfigRecoveryError, UnicodeError) as primary_error:
        recovery = recovery_config_path(primary)
        if not recovery.exists():
            raise ConfigRecoveryError(
                f"The active configuration is unreadable and no recovery copy exists: {primary_error}"
            ) from primary_error

        try:
            recovery_text = _validated_config_text(recovery)
        except (ConfigRecoveryError, UnicodeError) as recovery_error:
            raise ConfigRecoveryError(
                "The active configuration and its recovery copy are both unreadable. "
                f"Active error: {primary_error}; recovery error: {recovery_error}"
            ) from recovery_error

        _write_text_atomically(primary, recovery_text)
        return (
            f"Recovered {primary.name} from {recovery.name} because the active configuration "
            "was unreadable. Review the restored settings before making further changes."
        )

    protect_config_before_write(primary)
    return ""
