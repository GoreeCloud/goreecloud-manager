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
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "goreecloud-manager" / "config.yaml"


CURRENT_SCHEMA_VERSION = 3

# v0.1.0-v0.1.3 shipped a fixed catalogue of services.  v0.1.4 makes
# services user-managed.  These signatures are used only to remove untouched
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


def _is_untouched_legacy_service(item: dict[str, Any]) -> bool:
    name = str(item.get("name", "") or "")
    signature = _LEGACY_DEFAULT_SERVICES.get(name)
    if not signature:
        return False
    return (
        str(item.get("description", "") or "") == signature["description"]
        and str(item.get("url", "") or "") == signature["url"]
        and str(item.get("health_url", "") or "") in signature["health_urls"]
        and bool(item.get("enabled", True)) is True
    )


def migrate_user_config(path: Path) -> bool:
    data = _load_yaml(path)
    meta = data.get("meta", {}) or {}
    try:
        version = int(meta.get("schema_version", 1) or 1)
    except (TypeError, ValueError):
        version = 1

    if version >= CURRENT_SCHEMA_VERSION:
        return False

    changed = False

    # v3: remove only the untouched service catalogue that older versions
    # injected.  Any edited/custom service is preserved exactly as-is.
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
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        temporary.replace(path)
    return changed


def ensure_user_config() -> Path:
    path = user_config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled_config_path(), path)
    migrate_user_config(path)
    return path


def _parse_config(path: Path) -> AppConfig:
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
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
                enabled=bool(item.get("enabled", True)),
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
            port=max(1, min(65535, int(server_data.get("port", 22) or 22))),
            user=str(server_data.get("user", "") or ""),
            identity_file=str(server_data.get("identity_file", "") or ""),
        ),
        monitoring=MonitoringConfig(
            mode=mode,
            auto_refresh_seconds=max(0, int(monitoring_data.get("auto_refresh_seconds", 60) or 0)),
            ssh_timeout_seconds=max(1, int(monitoring_data.get("ssh_timeout_seconds", 6) or 6)),
        ),
        services=services,
    )


def load_config(path: Path | None = None) -> AppConfig:
    path = path or ensure_user_config()
    return _parse_config(path)


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    path = path or ensure_user_config()
    path.parent.mkdir(parents=True, exist_ok=True)

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

    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    temporary.replace(path)
    return path
