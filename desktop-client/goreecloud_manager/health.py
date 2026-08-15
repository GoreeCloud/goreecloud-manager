from __future__ import annotations

import os
import platform
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import psutil


@dataclass
class SystemHealth:
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    uptime_seconds: int
    source_name: str
    source_detail: str
    hostname: str = ""
    os_name: str = ""
    kernel: str = ""
    cpu_threads: int = 0
    load_1: float = 0.0
    load_5: float = 0.0
    load_15: float = 0.0
    memory_used_bytes: int = 0
    memory_total_bytes: int = 0
    disk_used_bytes: int = 0
    disk_total_bytes: int = 0
    failed_units: int | None = None


@dataclass
class ServiceHealth:
    state: str
    label: str
    detail: str


class SystemHealthError(RuntimeError):
    pass


def _local_os_name() -> str:
    path = Path("/etc/os-release")
    if not path.exists():
        return platform.system()
    values: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            key, sep, value = line.partition("=")
            if sep:
                values[key] = value.strip().strip('"')
    except OSError:
        return platform.system()
    return values.get("PRETTY_NAME") or values.get("NAME") or platform.system()


def local_health() -> SystemHealth:
    boot = psutil.boot_time()
    root_usage = psutil.disk_usage("/")
    memory = psutil.virtual_memory()
    hostname = socket.gethostname()
    try:
        load_1, load_5, load_15 = os.getloadavg()
    except (AttributeError, OSError):
        load_1 = load_5 = load_15 = 0.0

    os_name = _local_os_name()
    return SystemHealth(
        cpu_percent=psutil.cpu_percent(interval=0.15),
        memory_percent=memory.percent,
        disk_percent=root_usage.percent,
        uptime_seconds=max(0, int(time.time() - boot)),
        source_name="This computer",
        source_detail=f"{os_name} • Local Linux system",
        hostname=hostname,
        os_name=os_name,
        kernel=platform.release(),
        cpu_threads=int(psutil.cpu_count(logical=True) or 0),
        load_1=float(load_1),
        load_5=float(load_5),
        load_15=float(load_15),
        memory_used_bytes=int(memory.total - memory.available),
        memory_total_bytes=int(memory.total),
        disk_used_bytes=int(root_usage.used),
        disk_total_bytes=int(root_usage.total),
        failed_units=None,
    )


def _ssh_failure_detail(output: str) -> str:
    normalized = output.casefold()
    if "host key verification failed" in normalized or "no ed25519 host key is known" in normalized:
        return (
            "SSH host identity is not trusted. Verify the server host key from a terminal "
            "before using GoreeCloud Manager."
        )
    lines = output.strip().splitlines()
    return lines[-1] if lines else "SSH command failed"


def remote_ssh_health(
    *,
    name: str,
    host: str,
    user: str,
    port: int = 22,
    identity_file: str = "",
    timeout: int = 6,
) -> SystemHealth:
    if not host:
        raise SystemHealthError("SSH monitoring requires a server address.")

    remote_script = r'''set -eu
sample_cpu() {
  awk '/^cpu / { idle=$5+$6; total=0; for (i=2; i<=9; i++) total+=$i; print idle, total; exit }' /proc/stat
}
set -- $(sample_cpu)
idle1=$1
total1=$2
sleep 0.25
set -- $(sample_cpu)
idle2=$1
total2=$2
cpu=$(awk -v i1="$idle1" -v i2="$idle2" -v t1="$total1" -v t2="$total2" 'BEGIN { d=t2-t1; if (d<=0) printf "0.0"; else printf "%.1f", 100*(1-((i2-i1)/d)) }')
mem_total_kb=$(awk '/^MemTotal:/ {print $2; exit}' /proc/meminfo)
mem_avail_kb=$(awk '/^MemAvailable:/ {print $2; exit}' /proc/meminfo)
mem=$(awk -v t="$mem_total_kb" -v a="$mem_avail_kb" 'BEGIN { if (t<=0) printf "0.0"; else printf "%.1f", ((t-a)*100/t) }')
mem_total_bytes=$((mem_total_kb * 1024))
mem_used_bytes=$(((mem_total_kb - mem_avail_kb) * 1024))
set -- $(df -Pk / | awk 'NR==2 {gsub("%","",$5); print $5, $3, $2}')
disk=$1
disk_used_bytes=$(($2 * 1024))
disk_total_bytes=$(($3 * 1024))
uptime=$(awk '{printf "%d", $1}' /proc/uptime)
hostname_value=$(hostname 2>/dev/null || printf unknown)
kernel_value=$(uname -r 2>/dev/null || printf unknown)
cpu_threads=$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || printf 0)
set -- $(awk '{print $1, $2, $3}' /proc/loadavg)
load1=$1
load5=$2
load15=$3
os_name="Linux"
if [ -r /etc/os-release ]; then
  . /etc/os-release
  os_name=${PRETTY_NAME:-${NAME:-Linux}}
fi
failed_units=-1
if command -v systemctl >/dev/null 2>&1; then
  failed_units=$(systemctl --failed --no-legend --plain 2>/dev/null | sed '/^[[:space:]]*$/d' | wc -l | tr -d ' ' || printf 0)
fi
printf 'cpu=%s\nmemory=%s\ndisk=%s\nuptime=%s\nhostname=%s\nos_name=%s\nkernel=%s\ncpu_threads=%s\nload1=%s\nload5=%s\nload15=%s\nmem_used_bytes=%s\nmem_total_bytes=%s\ndisk_used_bytes=%s\ndisk_total_bytes=%s\nfailed_units=%s\n' \
  "$cpu" "$mem" "$disk" "$uptime" "$hostname_value" "$os_name" "$kernel_value" "$cpu_threads" \
  "$load1" "$load5" "$load15" "$mem_used_bytes" "$mem_total_bytes" "$disk_used_bytes" "$disk_total_bytes" "$failed_units"
'''

    target = f"{user}@{host}" if user else host
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={timeout}",
        "-o",
        "StrictHostKeyChecking=yes",
        "-p",
        str(port),
    ]
    if identity_file:
        command.extend(["-i", str(Path(identity_file).expanduser())])
    command.extend([target, "sh", "-s"])

    try:
        result = subprocess.run(
            command,
            input=remote_script,
            text=True,
            capture_output=True,
            timeout=timeout + 4,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SystemHealthError("The ssh command is not installed on this computer.") from exc
    except subprocess.TimeoutExpired as exc:
        raise SystemHealthError(f"SSH connection to {host} timed out.") from exc

    if result.returncode != 0:
        output = result.stderr or result.stdout or "SSH command failed"
        raise SystemHealthError(_ssh_failure_detail(output))

    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            values[key.strip()] = value.strip()

    try:
        os_name = values.get("os_name", "Linux") or "Linux"
        failed_raw = int(values.get("failed_units", "-1"))
        return SystemHealth(
            cpu_percent=float(values["cpu"]),
            memory_percent=float(values["memory"]),
            disk_percent=float(values["disk"]),
            uptime_seconds=int(float(values["uptime"])),
            source_name=name or values.get("hostname", host) or host,
            source_detail=f"{os_name} • OpenSSH • Port {port}",
            hostname=values.get("hostname", host),
            os_name=os_name,
            kernel=values.get("kernel", ""),
            cpu_threads=int(values.get("cpu_threads", "0") or 0),
            load_1=float(values.get("load1", "0") or 0),
            load_5=float(values.get("load5", "0") or 0),
            load_15=float(values.get("load15", "0") or 0),
            memory_used_bytes=int(values.get("mem_used_bytes", "0") or 0),
            memory_total_bytes=int(values.get("mem_total_bytes", "0") or 0),
            disk_used_bytes=int(values.get("disk_used_bytes", "0") or 0),
            disk_total_bytes=int(values.get("disk_total_bytes", "0") or 0),
            failed_units=None if failed_raw < 0 else failed_raw,
        )
    except (KeyError, ValueError) as exc:
        raise SystemHealthError("The remote server returned an unexpected metrics response.") from exc


def format_uptime(seconds: int) -> str:
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def format_bytes(value: int) -> str:
    if value <= 0:
        return "—"
    gib = value / (1024 ** 3)
    if gib >= 10:
        return f"{gib:.1f} GiB"
    return f"{gib:.2f} GiB"


def check_url(url: str, timeout: float = 4.0) -> ServiceHealth:
    if not url:
        return ServiceHealth("unconfigured", "Not configured", "URL not configured")

    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "User-Agent": "GoreeCloud-Manager/0.2.5",
            "Accept": "text/html,application/xhtml+xml,application/json,text/plain;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            code = int(getattr(response, "status", 200))
            body = response.read(4096).decode("utf-8", errors="ignore").strip()
            if 200 <= code < 400:
                if body.lower() in {"false", "0"}:
                    return ServiceHealth("degraded", "Degraded", "Health check returned false")
                return ServiceHealth("healthy", "Healthy", f"HTTP {code}")
            if 400 <= code < 500:
                return ServiceHealth("reachable", "Reachable", f"HTTP {code}")
            return ServiceHealth("degraded", "Degraded", f"HTTP {code}")
    except urllib.error.HTTPError as exc:
        if 400 <= exc.code < 500:
            return ServiceHealth("reachable", "Reachable", f"HTTP {exc.code}")
        return ServiceHealth("degraded", "Degraded", f"HTTP {exc.code}")
    except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        return ServiceHealth("offline", "Offline", str(reason))
