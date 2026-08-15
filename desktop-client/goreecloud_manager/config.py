from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ServiceConfig:
    name: str
    description: str = ""
    url: str = ""
    health_url: str = ""
    enabled: bool = True


@dataclass
class ServerConfig:
    name: str = "goreecloud-vps-01"
    host: str = ""
    port: int = 22
    user: str = ""
    identity_file: str = ""


@dataclass
class MonitoringConfig:
    mode: str = "local"
    auto_refresh_seconds: int = 60
    ssh_timeout_seconds: int = 6


@dataclass
class AppConfig:
    title: str = "GoreeCloud Manager"
    environment: str = "Home / Family Cloud"
    server: ServerConfig = field(default_factory=ServerConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    services: list[ServiceConfig] = field(default_factory=list)


def bundled_config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / "services.yaml"


def user_config_path() -> Path:
    override = os.environ.get("GOREECLOUD_MANAGER_CONFIG", "").strip()
    if override:
        return Path(override).expanduser()
    base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "goreecloud-manager" / "config.yaml"


CURRENT_SCHEMA_VERSION = 3
_CONFIG_FILE_MODE = 0o600
_MAX_AUTO_REFRESH_SECONDS = 3600
_MAX_SSH_TIMEOUT_SECONDS = 60

# v0.1.0-v0.1.3 shipped a fixed catalogue of services. v0.1.4 makes
# services user-managed. These signatures are used only to remove untouched
# legacy defaults during migration; if a user changed an entry, it is kept.
_LEGACY_DEFAULT_SERVICES: dict[str, dict[str, Any]] = {
    "Nextcloud": {
        "description": "Files, synchronization, sharing, and accounts",
        "url": "https://drive.goreecloud.com",
        "health_urls": {"", "https://drive.goreecloud.com/status.php"},
    },
    "ONLYOFFICE Docs": {
        "description": "Document editing backend",
        "url": "https://office.goreecloud.com",
        "health_urls": {"", "https://office.goreecloud.com/healthcheck"},
    },
    "Immich": {
        "description": "Private photo and video library",
        "url": "",
        "health_urls": {""},
    },
    "Jellyfin": {
        "description": "Private media streaming",
        "url": "",
        "health_urls": {""},
    },
    "Navidrome": {
        "description": "Private music streaming",
        "url": "",
        "health_urls": {""},
    },
    "Uptime Kuma": {
        "description": "Service monitoring and status checks",
        "url": "",
        "health_urls": {""},
    },
    "Beszel": {
        "description": "Lightweight server monitoring",
        "url": "",
        "health_urls": {""},
    },
    "Dockhand": {
        "description": "Container administration",
        "url": "",
        "health_urls": {""},
    },
    "Dozzle": {
        "description": "Container log viewer",
        "url": "",
        "health_urls": {""},
    },
}


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _parse_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _write_text_atomically(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.unlink(missing_ok=True)

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    descriptor = os.open(temporary, flags, _CONFIG_FILE_MODE)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, _CONFIG_FILE_MODE)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _write_yaml_atomically(path: Path, data: dict[str, Any]) -> None:
    _write_text_atomically(
        path,
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
    )


def _is_untouched_legacy_service(item: dict[str, Any]) -> bool:
    name = str(item.get("name", "") or "")
    signature = _LEGACY_DEFAULT_SERVICES.get(name)
    if not signature:
        return False
    return (
        str(item.get("description", "") or "") == signature["description"]
        and str(item.get("url", "") or "") == signature["url"]
        and str(item.get("health_url", "") or "") in signature["health_urls"]
        and _parse_bool(item.get("enabled", True), default=True) is True
    )


def migrate_user_config(path: Path) -> bool:
    data = _load_yaml(path)
    meta = data.get("meta", {}) or {}
    try:
        version = int(meta.get("schema_version", 1) or 1)
    except (TypeError, ValueError):
        version = 1

    if version >= CURRENT_SCHEMA_VERSION:
        os.chmod(path, _CONFIG_FILE_MODE)
        return False

    changed = False

    # v3: remove only the untouched service catalogue that older versions
    # injected. Any edited/custom service is preserved exactly as-is.
    if version < 3:
        old_services = data.get("services", []) or []
        if isinstance(old_services, list):
            new_services = [
                item
                for item in old_services
                if not (isinstance(item, dict) and _is_untouched_legacy_service(item))
            ]
            if len(new_services) != len(old_services):
                data["services"] = new_services
                changed = True

    data["meta"] = {**meta, "schema_version": CURRENT_SCHEMA_VERSION}
    changed = True

    if changed:
        _write_yaml_atomically(path, data)
    return changed


def ensure_user_config() -> Path:
    path = user_config_path()
    if not path.exists():
        _write_text_atomically(
            path,
            bundled_config_path().read_text(encoding="utf-8"),
        )
    migrate_user_config(path)
    os.chmod(path, _CONFIG_FILE_MODE)
    return path


def _parse_config(path: Path) -> AppConfig:
    data = _load_yaml(path)
    app_data = data.get("app", {}) or {}
    server_data = data.get("server", {}) or {}
    monitoring_data = data.get("monitoring", {}) or {}

    services: list[ServiceConfig] = []
    for item in data.get("services", []) or []:
        if not isinstance(item, dict) or not str(item.get("name", "") or "").strip():
            continue
        services.append(
            ServiceConfig(
                name=str(item.get("name", "")).strip(),
                description=str(item.get("description", "") or ""),
                url=str(item.get("url", "") or ""),
                health_url=str(item.get("health_url", "") or ""),
                enabled=_parse_bool(item.get("enabled", True), default=True),
            )
        )

    mode = str(monitoring_data.get("mode", "local") or "local").lower()
    if mode not in {"local", "ssh"}:
        mode = "local"

    return AppConfig(
        title=str(app_data.get("title", "GoreeCloud Manager") or "GoreeCloud Manager"),
        environment=str(app_data.get("environment", "Home / Family Cloud") or "Home / Family Cloud"),
        server=ServerConfig(
            name=str(server_data.get("name", "goreecloud-vps-01") or "goreecloud-vps-01"),
            host=str(server_data.get("host", "") or ""),
            port=_bounded_int(server_data.get("port", 22), default=22, minimum=1, maximum=65535),
            user=str(server_data.get("user", "") or ""),
            identity_file=str(server_data.get("identity_file", "") or ""),
        ),
        monitoring=MonitoringConfig(
            mode=mode,
            auto_refresh_seconds=_bounded_int(
                monitoring_data.get("auto_refresh_seconds", 60),
                default=60,
                minimum=0,
                maximum=_MAX_AUTO_REFRESH_SECONDS,
            ),
            ssh_timeout_seconds=_bounded_int(
                monitoring_data.get("ssh_timeout_seconds", 6),
                default=6,
                minimum=1,
                maximum=_MAX_SSH_TIMEOUT_SECONDS,
            ),
        ),
        services=services,
    )


def load_config(path: Path | None = None) -> AppConfig:
    path = path or ensure_user_config()
    return _parse_config(path)


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    path = path or ensure_user_config()

    payload = {
        "meta": {"schema_version": CURRENT_SCHEMA_VERSION},
        "app": {
            "title": config.title,
            "environment": config.environment,
        },
        "monitoring": asdict(config.monitoring),
        "server": asdict(config.server),
        "services": [asdict(service) for service in config.services],
    }

    _write_yaml_atomically(path, payload)
    return path
