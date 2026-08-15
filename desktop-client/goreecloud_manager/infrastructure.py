from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import AppConfig


@dataclass
class ContainerInfo:
    name: str
    container_id: str = ""
    image: str = ""
    state: str = ""
    status: str = ""
    health: str = ""
    ports: str = ""
    cpu: str = "—"
    memory: str = "—"
    memory_percent: str = "—"
    created_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    restart_count: int = 0
    restart_policy: str = ""
    pid: int = 0
    exit_code: int = 0
    oom_killed: bool = False
    health_failing_streak: int = 0
    networks: str = ""
    network_mode: str = ""
    network_addresses: str = ""
    mounts: str = ""


@dataclass
class DockerOverview:
    state: str = "unknown"  # available, not_installed, unavailable
    version: str = ""
    running: int = 0
    stopped: int = 0
    healthy: int = 0
    unhealthy: int = 0
    health_starting: int = 0
    no_healthcheck: int = 0
    health_monitored: int = 0
    total: int = 0
    containers: list[ContainerInfo] = field(default_factory=list)
    detail: str = ""


@dataclass
class NetBirdPeer:
    name: str
    ip: str = ""
    status: str = ""
    connection_type: str = ""
    latency: str = ""


@dataclass
class NetBirdOverview:
    state: str = "unknown"  # available, not_installed, unavailable
    cli_version: str = ""
    daemon_version: str = ""
    management: str = ""
    signal: str = ""
    netbird_ip: str = ""
    interface_type: str = ""
    peers_connected: int = 0
    peers_connecting: int = 0
    peers_disconnected: int = 0
    peers_total: int = 0
    peers: list[NetBirdPeer] = field(default_factory=list)
    detail: str = ""


@dataclass
class InfrastructureOverview:
    docker: DockerOverview = field(default_factory=DockerOverview)
    netbird: NetBirdOverview = field(default_factory=NetBirdOverview)


class InfrastructureError(RuntimeError):
    pass


def _ssh_command(config: AppConfig) -> list[str]:
    target = f"{config.server.user}@{config.server.host}" if config.server.user else config.server.host
    command = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", f"ConnectTimeout={config.monitoring.ssh_timeout_seconds}",
        "-o", "StrictHostKeyChecking=accept-new",
        "-p", str(config.server.port),
    ]
    if config.server.identity_file:
        command.extend(["-i", str(Path(config.server.identity_file).expanduser())])
    command.extend([target, "sh", "-s"])
    return command


def _run_script(config: AppConfig, script: str) -> str:
    timeout = config.monitoring.ssh_timeout_seconds
    if config.monitoring.mode == "ssh":
        if not config.server.host:
            raise InfrastructureError("SSH monitoring requires a server address.")
        command = _ssh_command(config)
    else:
        command = ["sh", "-s"]

    try:
        result = subprocess.run(
            command,
            input=script,
            text=True,
            capture_output=True,
            timeout=timeout + 10,
            check=False,
        )
    except FileNotFoundError as exc:
        raise InfrastructureError("Required shell/SSH command is not installed.") from exc
    except subprocess.TimeoutExpired as exc:
        raise InfrastructureError("Infrastructure discovery timed out.") from exc

    if result.returncode != 0:
        message = (result.stderr or result.stdout or "Infrastructure discovery failed").strip().splitlines()
        raise InfrastructureError(message[-1] if message else "Infrastructure discovery failed")
    return result.stdout


def discover_infrastructure(config: AppConfig) -> InfrastructureOverview:
    script = r'''set +e
printf '%s\n' '__GCM_DOCKER_BEGIN__'
if command -v docker >/dev/null 2>&1; then
  printf '%s\n' 'installed=1'
  docker_version=$(docker version --format '{{.Server.Version}}' 2>/tmp/gcm-docker-error)
  docker_rc=$?
  if [ "$docker_rc" -ne 0 ]; then
    printf '%s\n' 'available=0'
    printf 'error=%s\n' "$(tail -n 1 /tmp/gcm-docker-error 2>/dev/null)"
  else
    printf '%s\n' 'available=1'
    printf 'version=%s\n' "$docker_version"
    printf '%s\n' '__GCM_DOCKER_PS__'
    docker ps -a --format json 2>/dev/null
    printf '%s\n' '__GCM_DOCKER_STATS__'
    docker stats --all --no-stream --format json 2>/dev/null
    printf '%s\n' '__GCM_DOCKER_INSPECT__'
    docker_ids=$(docker ps -aq 2>/dev/null)
    if [ -n "$docker_ids" ]; then
      docker inspect --format '{{json .}}' $docker_ids 2>/dev/null
    fi
  fi
else
  printf '%s\n' 'installed=0'
fi
rm -f /tmp/gcm-docker-error
printf '%s\n' '__GCM_DOCKER_END__'

printf '%s\n' '__GCM_NETBIRD_BEGIN__'
if command -v netbird >/dev/null 2>&1; then
  printf '%s\n' 'installed=1'
  printf '%s\n' '__GCM_NETBIRD_TEXT__'
  netbird status -d 2>/tmp/gcm-netbird-error
  nb_rc=$?
  if [ "$nb_rc" -ne 0 ]; then
    printf '%s\n' '__GCM_NETBIRD_ERROR__'
    tail -n 1 /tmp/gcm-netbird-error 2>/dev/null
  fi
else
  printf '%s\n' 'installed=0'
fi
rm -f /tmp/gcm-netbird-error
printf '%s\n' '__GCM_NETBIRD_END__'
'''
    return parse_infrastructure_output(_run_script(config, script))


def _section(text: str, begin: str, end: str) -> str:
    if begin not in text or end not in text:
        return ""
    return text.split(begin, 1)[1].split(end, 1)[0].strip("\n")


def _kv_lines(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            values[key.strip()] = value.strip()
    return values


def _parse_json_lines(text: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            items.append(value)
    return items


def _parse_docker(text: str) -> DockerOverview:
    section = _section(text, "__GCM_DOCKER_BEGIN__", "__GCM_DOCKER_END__")
    if not section:
        return DockerOverview(state="unavailable", detail="Docker discovery returned no data")
    base = section.split("__GCM_DOCKER_PS__", 1)[0]
    values = _kv_lines(base)
    if values.get("installed") != "1":
        return DockerOverview(state="not_installed", detail="Docker CLI not installed")
    if values.get("available") != "1":
        return DockerOverview(state="unavailable", detail=values.get("error") or "Docker daemon is not accessible")

    ps_text = _section(section, "__GCM_DOCKER_PS__", "__GCM_DOCKER_STATS__")
    stats_blob = section.split("__GCM_DOCKER_STATS__", 1)[1] if "__GCM_DOCKER_STATS__" in section else ""
    if "__GCM_DOCKER_INSPECT__" in stats_blob:
        stats_text, inspect_text = stats_blob.split("__GCM_DOCKER_INSPECT__", 1)
    else:
        stats_text, inspect_text = stats_blob, ""
    ps_rows = _parse_json_lines(ps_text)
    stats_rows = _parse_json_lines(stats_text)
    inspect_rows = _parse_json_lines(inspect_text)
    stats_by_name: dict[str, dict[str, Any]] = {}
    stats_by_id: dict[str, dict[str, Any]] = {}
    for row in stats_rows:
        name = str(row.get("Name") or row.get("Container") or "")
        cid = str(row.get("ID") or "")
        if name:
            stats_by_name[name] = row
        if cid:
            stats_by_id[cid] = row

    inspect_by_id: dict[str, dict[str, Any]] = {}
    inspect_by_name: dict[str, dict[str, Any]] = {}
    for row in inspect_rows:
        cid = str(row.get("Id") or row.get("ID") or "")
        name = str(row.get("Name") or "").lstrip("/")
        if cid:
            inspect_by_id[cid] = row
            inspect_by_id[cid[:12]] = row
        if name:
            inspect_by_name[name] = row

    containers: list[ContainerInfo] = []
    for row in ps_rows:
        name = str(row.get("Names") or row.get("Name") or "Unnamed")
        cid = str(row.get("ID") or "")
        stats = stats_by_name.get(name) or stats_by_id.get(cid) or {}
        inspect = inspect_by_name.get(name) or inspect_by_id.get(cid) or {}
        state = str(row.get("State") or _pick(inspect.get("State", {}) if isinstance(inspect.get("State"), dict) else {}, "Status") or "")
        inspect_state = inspect.get("State", {}) if isinstance(inspect.get("State"), dict) else {}
        health_data = inspect_state.get("Health", {}) if isinstance(inspect_state.get("Health"), dict) else {}
        health = str(health_data.get("Status") or "")
        if not health:
            status_lower = str(row.get("Status") or "").casefold()
            if "(healthy)" in status_lower:
                health = "healthy"
            elif "(unhealthy)" in status_lower:
                health = "unhealthy"
            elif "health: starting" in status_lower or "(health: starting)" in status_lower:
                health = "starting"

        network_data = inspect.get("NetworkSettings", {}) if isinstance(inspect.get("NetworkSettings"), dict) else {}
        networks_obj = network_data.get("Networks", {}) if isinstance(network_data.get("Networks"), dict) else {}
        networks = ", ".join(sorted(str(name) for name in networks_obj.keys()))
        address_parts: list[str] = []
        for network_name, network in sorted(networks_obj.items(), key=lambda item: str(item[0]).casefold()):
            if not isinstance(network, dict):
                continue
            ipv4 = str(network.get("IPAddress") or "").strip()
            ipv6 = str(network.get("GlobalIPv6Address") or "").strip()
            addresses = [value for value in (ipv4, ipv6) if value]
            if addresses:
                address_parts.append(f"{network_name}: {', '.join(addresses)}")

        host_config = inspect.get("HostConfig", {}) if isinstance(inspect.get("HostConfig"), dict) else {}
        restart_policy_obj = host_config.get("RestartPolicy", {}) if isinstance(host_config.get("RestartPolicy"), dict) else {}
        restart_policy = str(restart_policy_obj.get("Name") or "").strip()
        max_retry = restart_policy_obj.get("MaximumRetryCount")
        if restart_policy == "on-failure" and isinstance(max_retry, int) and max_retry > 0:
            restart_policy = f"{restart_policy}:{max_retry}"

        mount_parts: list[str] = []
        mounts_obj = inspect.get("Mounts", []) if isinstance(inspect.get("Mounts"), list) else []
        for mount in mounts_obj:
            if not isinstance(mount, dict):
                continue
            source = str(mount.get("Source") or mount.get("Name") or "")
            destination = str(mount.get("Destination") or "")
            kind = str(mount.get("Type") or "mount")
            mode = "rw" if bool(mount.get("RW", False)) else "ro"
            if source and destination:
                mount_parts.append(f"{kind}: {source} → {destination} ({mode})")
            elif destination:
                mount_parts.append(f"{kind}: {destination} ({mode})")

        containers.append(
            ContainerInfo(
                name=name,
                container_id=str(inspect.get("Id") or cid),
                image=str(row.get("Image") or ""),
                state=state,
                status=str(row.get("Status") or state),
                health=health,
                ports=str(row.get("Ports") or ""),
                cpu=str(stats.get("CPUPerc") or "—"),
                memory=str(stats.get("MemUsage") or "—"),
                memory_percent=str(stats.get("MemPerc") or "—"),
                created_at=str(inspect.get("Created") or row.get("CreatedAt") or ""),
                started_at=str(inspect_state.get("StartedAt") or ""),
                finished_at=str(inspect_state.get("FinishedAt") or ""),
                restart_count=int(inspect.get("RestartCount") or 0),
                restart_policy=restart_policy,
                pid=int(inspect_state.get("Pid") or 0),
                exit_code=int(inspect_state.get("ExitCode") or 0),
                oom_killed=bool(inspect_state.get("OOMKilled", False)),
                health_failing_streak=int(health_data.get("FailingStreak") or 0),
                networks=networks,
                network_mode=str(host_config.get("NetworkMode") or ""),
                network_addresses="; ".join(address_parts),
                mounts="; ".join(mount_parts),
            )
        )
    containers.sort(key=lambda item: (item.state.lower() != "running", item.name.casefold()))
    running = sum(1 for item in containers if item.state.lower() == "running")
    healthy = sum(1 for item in containers if item.health.casefold() == "healthy")
    unhealthy = sum(1 for item in containers if item.health.casefold() == "unhealthy")
    health_starting = sum(1 for item in containers if item.health.casefold() == "starting")
    health_monitored = healthy + unhealthy + health_starting
    no_healthcheck = max(0, len(containers) - health_monitored)
    return DockerOverview(
        state="available",
        version=values.get("version", ""),
        running=running,
        stopped=max(0, len(containers) - running),
        healthy=healthy,
        unhealthy=unhealthy,
        health_starting=health_starting,
        no_healthcheck=no_healthcheck,
        health_monitored=health_monitored,
        total=len(containers),
        containers=containers,
        detail="Docker Engine available",
    )


def _human_netbird_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        # Peer detail fields are indented. Only consume the top-level status block so
        # a remote peer's NetBird IP cannot overwrite this host's own NetBird IP.
        if line != line.lstrip():
            continue
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip().lower()] = value.strip()
    return fields


def _find_peer_dicts(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        keys = {str(k).lower() for k in value.keys()}
        looks_like_peer = (
            any(k in keys for k in {"fqdn", "hostname", "name"})
            and any(k in keys for k in {"netbirdip", "netbird_ip", "ip", "ipaddress"})
        ) or (
            any(k in keys for k in {"netbirdip", "netbird_ip"})
            and any(k in keys for k in {"status", "connectionstatus", "connected"})
        )
        if looks_like_peer:
            found.append(value)
        for child in value.values():
            found.extend(_find_peer_dicts(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_find_peer_dicts(child))
    return found


def _pick(data: dict[str, Any], *names: str) -> Any:
    lowered = {str(k).lower(): v for k, v in data.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return ""


def _parse_netbird_peers(text: str) -> list[NetBirdPeer]:
    """Parse the stable human-readable peer detail block from `netbird status -d`.

    We intentionally use the CLI's already-formatted latency here rather than guessing
    the unit of the JSON duration field. This also naturally excludes the local peer,
    matching NetBird's own "Peers count" value.
    """
    marker = "Peers detail:"
    if marker not in text:
        return []

    peer_text = text.split(marker, 1)[1]
    lines = peer_text.splitlines()
    known_top_level = {
        "os", "daemon version", "cli version", "management", "signal", "relays",
        "nameservers", "netbird ip", "interface type", "quantum resistance",
        "routes", "peers count", "dns", "forwarding rules", "networks",
        "events", "events log", "debug",
    }

    peers: list[NetBirdPeer] = []
    current_name = ""
    current: dict[str, str] = {}

    def flush() -> None:
        nonlocal current_name, current
        if not current_name:
            return
        peers.append(
            NetBirdPeer(
                name=current_name,
                ip=current.get("netbird ip", ""),
                status=current.get("status", ""),
                connection_type=current.get("connection type", ""),
                latency=current.get("latency", ""),
            )
        )
        current_name = ""
        current = {}

    for raw in lines:
        if not raw.strip():
            continue
        stripped = raw.strip()
        key, sep, value = stripped.partition(":")
        key_l = key.strip().lower()

        # Once a non-indented top-level status/event section begins, peer detail is complete.
        # NetBird versions differ slightly here: some emit `Events:` as a heading with
        # no value, which older GoreeCloud Manager builds accidentally treated as a peer.
        if raw == raw.lstrip() and key_l in known_top_level and (sep or stripped.endswith(":")):
            flush()
            break

        # Peer names are headings ending in ':' and do not use a known detail key.
        if stripped.endswith(":") and key_l not in {
            "netbird ip", "public key", "status", "connection type", "direct",
            "ice candidate (local/remote)", "ice candidate endpoints (local/remote)",
            "relay server address", "last connection update", "last wireguard handshake",
            "last wireguard handshake", "transfer status (received/sent)",
            "quantum resistance", "routes", "networks", "latency",
        }:
            flush()
            current_name = stripped[:-1].strip()
            continue

        if current_name and sep:
            current[key_l] = value.strip()

    flush()
    # Defensive de-duplication while retaining NetBird's reported order.
    unique: list[NetBirdPeer] = []
    seen: set[tuple[str, str]] = set()
    for peer in peers:
        key = (peer.name, peer.ip)
        if key not in seen:
            seen.add(key)
            unique.append(peer)
    return unique


def _parse_netbird(text: str) -> NetBirdOverview:
    section = _section(text, "__GCM_NETBIRD_BEGIN__", "__GCM_NETBIRD_END__")
    if not section:
        return NetBirdOverview(state="unavailable", detail="NetBird discovery returned no data")
    prefix = section.split("__GCM_NETBIRD_TEXT__", 1)[0]
    values = _kv_lines(prefix)
    if values.get("installed") != "1":
        return NetBirdOverview(state="not_installed", detail="NetBird CLI not installed")

    text_status = section.split("__GCM_NETBIRD_TEXT__", 1)[1] if "__GCM_NETBIRD_TEXT__" in section else ""
    if "__GCM_NETBIRD_ERROR__" in text_status:
        normal, error = text_status.split("__GCM_NETBIRD_ERROR__", 1)
        detail = error.strip().splitlines()[-1] if error.strip() else "NetBird daemon is not accessible"
        return NetBirdOverview(state="unavailable", detail=detail)

    fields = _human_netbird_fields(text_status)
    peers = _parse_netbird_peers(text_status)

    peers_connected = peers_connecting = peers_disconnected = peers_total = 0
    peer_count = fields.get("peers count", "")
    if "/" in peer_count:
        try:
            left, right = peer_count.split("/", 1)
            peers_connected = int(left.strip())
            peers_total = int(right.strip().split()[0])
        except (TypeError, ValueError):
            pass

    if peers:
        calculated_connected = sum(1 for p in peers if p.status.casefold() == "connected")
        peers_connecting = sum(1 for p in peers if p.status.casefold() in {"connecting", "idle"})
        peers_disconnected = sum(1 for p in peers if p.status.casefold() in {"disconnected", "offline"})
        # Trust the visible rows when they match/complete the summary, otherwise keep
        # NetBird's own count for the headline and use rows for the breakdown.
        if not peers_total:
            peers_total = len(peers)
            peers_connected = calculated_connected
        elif len(peers) == peers_total:
            peers_connected = calculated_connected

    return NetBirdOverview(
        state="available",
        cli_version=fields.get("cli version", ""),
        daemon_version=fields.get("daemon version", ""),
        management=fields.get("management", ""),
        signal=fields.get("signal", ""),
        netbird_ip=fields.get("netbird ip", ""),
        interface_type=fields.get("interface type", ""),
        peers_connected=peers_connected,
        peers_connecting=peers_connecting,
        peers_disconnected=peers_disconnected,
        peers_total=peers_total,
        peers=peers,
        detail="NetBird agent available",
    )


def parse_infrastructure_output(text: str) -> InfrastructureOverview:
    return InfrastructureOverview(docker=_parse_docker(text), netbird=_parse_netbird(text))
