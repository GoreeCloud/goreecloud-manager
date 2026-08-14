#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/scripts/runtime_publication.compose.yml"
WORK_DIR="$(mktemp -d)"
export MANAGER_RUNTIME_WORK_DIR="$WORK_DIR"

cleanup() {
  docker compose -f "$COMPOSE_FILE" down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

chmod 700 "$WORK_DIR"
python - <<'PY' > "$WORK_DIR/django-secret-key"
import secrets
print(secrets.token_urlsafe(64))
PY
python - <<'PY' > "$WORK_DIR/admin-password"
import secrets
print(secrets.token_urlsafe(48))
PY
# Local Compose secrets are bind-mounted by the hosted runner. The enclosing
# mktemp directory remains mode 0700; files are readable only inside that private
# directory and by the explicitly mounted disposable containers.
chmod 0444 "$WORK_DIR/django-secret-key" "$WORK_DIR/admin-password"

DJANGO_SECRET_VALUE="$(cat "$WORK_DIR/django-secret-key")"
ADMIN_PASSWORD_VALUE="$(cat "$WORK_DIR/admin-password")"

cd "$REPO_ROOT"

echo "Rendering disposable Manager runtime/publication topology..."
docker compose -f "$COMPOSE_FILE" config --format json > "$WORK_DIR/rendered.json"
python - "$WORK_DIR/rendered.json" <<'PY'
import json
import sys

config = json.load(open(sys.argv[1], encoding="utf-8"))
services = config["services"]
for name, service in services.items():
    if service.get("ports"):
        raise SystemExit(f"service {name!r} unexpectedly publishes a host port")

expected_networks = {
    "manager": {"proxy"},
    "caddy": {"proxy", "approved_ingress", "unapproved_ingress"},
    "approved-client": {"approved_ingress"},
    "unapproved-client": {"unapproved_ingress"},
}
for service_name, expected in expected_networks.items():
    actual = set(services[service_name].get("networks", {}))
    if actual != expected:
        raise SystemExit(
            f"{service_name} network drift: expected {sorted(expected)!r}, got {sorted(actual)!r}"
        )

manager = services["manager"]
if manager.get("read_only") is not True:
    raise SystemExit("Manager disposable runtime must use a read-only root filesystem")
if "ALL" not in manager.get("cap_drop", []):
    raise SystemExit("Manager disposable runtime must drop all Linux capabilities")
security_opt = manager.get("security_opt", [])
if not any(str(item).startswith("no-new-privileges") for item in security_opt):
    raise SystemExit("Manager disposable runtime must enforce no-new-privileges")
if manager.get("environment", {}).get("DJANGO_SECRET_KEY_FILE") != "/run/secrets/django_secret_key":
    raise SystemExit("Manager must consume the Django secret through the file-backed secret path")
if manager.get("environment", {}).get("DJANGO_SECRET_KEY"):
    raise SystemExit("Manager disposable runtime must not carry a direct Django secret value")

print("Rendered topology assertions passed: zero host ports, exact network boundaries, hardened Manager runtime.")
PY

echo "Building candidate Manager image..."
docker compose -f "$COMPOSE_FILE" build manager

echo "Proving production mode fails closed without an approved Django secret..."
if docker compose -f "$COMPOSE_FILE" run --rm \
  -e DJANGO_SECRET_KEY_FILE= \
  -e DJANGO_SECRET_KEY= \
  manager python -c 'import goreecloud_manager.settings' >/dev/null 2>&1; then
  echo "ERROR: production settings accepted the development default secret" >&2
  exit 1
fi

echo "Starting hardened Manager runtime..."
docker compose -f "$COMPOSE_FILE" up -d manager

wait_healthy() {
  local service="$1"
  local container
  container="$(docker compose -f "$COMPOSE_FILE" ps -q "$service")"
  for _ in $(seq 1 36); do
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container")"
    if [[ "$status" == "healthy" ]]; then
      return 0
    fi
    if [[ "$status" == "unhealthy" || "$status" == "exited" || "$status" == "dead" ]]; then
      docker compose -f "$COMPOSE_FILE" logs "$service" >&2 || true
      return 1
    fi
    sleep 2
  done
  docker compose -f "$COMPOSE_FILE" logs "$service" >&2 || true
  return 1
}

wait_healthy manager

echo "Creating a disposable administrative identity through the file-backed test password..."
docker compose -f "$COMPOSE_FILE" exec -T manager python manage.py shell -c \
  "from pathlib import Path; from django.contrib.auth import get_user_model; User=get_user_model(); password=Path('/run/secrets/admin_password').read_text(encoding='utf-8').strip(); user, _=User.objects.get_or_create(username='synthetic-admin'); user.is_staff=True; user.is_superuser=True; user.set_password(password); user.save()" \
  >/dev/null

echo "Starting Caddy and synthetic private/unapproved clients..."
docker compose -f "$COMPOSE_FILE" up -d caddy approved-client unapproved-client
wait_healthy caddy

for _ in $(seq 1 20); do
  if docker compose -f "$COMPOSE_FILE" exec -T approved-client python /client.py tls >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [[ "$_" == "20" ]]; then
    docker compose -f "$COMPOSE_FILE" logs caddy >&2 || true
    echo "ERROR: verified disposable TLS path did not become ready" >&2
    exit 1
  fi
done

echo "Validating private HTTPS, authentication, cookies, denial, and isolation..."
docker compose -f "$COMPOSE_FILE" exec -T approved-client python /client.py tls
docker compose -f "$COMPOSE_FILE" exec -T approved-client python /client.py approved
docker compose -f "$COMPOSE_FILE" exec -T approved-client python /client.py isolation
docker compose -f "$COMPOSE_FILE" exec -T unapproved-client python /client.py denied

echo "Inspecting live Manager runtime security properties..."
MANAGER_ID="$(docker compose -f "$COMPOSE_FILE" ps -q manager)"
docker inspect "$MANAGER_ID" > "$WORK_DIR/manager-inspect.json"
python - "$WORK_DIR/manager-inspect.json" <<'PY'
import json
import sys

inspect = json.load(open(sys.argv[1], encoding="utf-8"))[0]
config = inspect["Config"]
host = inspect["HostConfig"]
mounts = inspect["Mounts"]

if config.get("User") != "manager":
    raise SystemExit(f"Manager runtime user drifted from non-root 'manager': {config.get('User')!r}")
if host.get("ReadonlyRootfs") is not True:
    raise SystemExit("Manager runtime root filesystem is not read-only")
if "ALL" not in (host.get("CapDrop") or []):
    raise SystemExit("Manager runtime did not drop ALL capabilities")
if not any(str(item).startswith("no-new-privileges") for item in (host.get("SecurityOpt") or [])):
    raise SystemExit("Manager runtime is missing no-new-privileges")
if host.get("PortBindings"):
    raise SystemExit(f"Manager unexpectedly has host port bindings: {host['PortBindings']!r}")
if any(mount.get("Destination") == "/var/run/docker.sock" for mount in mounts):
    raise SystemExit("Manager unexpectedly received the Docker socket")

data_mounts = [mount for mount in mounts if mount.get("Destination") == "/app/data"]
if len(data_mounts) != 1 or data_mounts[0].get("RW") is not True:
    raise SystemExit("Manager SQLite data volume is not the single writable persistent data mount")
secret_mounts = [mount for mount in mounts if str(mount.get("Destination", "")).startswith("/run/secrets/")]
if not secret_mounts or any(mount.get("RW") is True for mount in secret_mounts):
    raise SystemExit("Manager disposable secrets are not mounted read-only")

print("Live runtime assertions passed: non-root, read-only rootfs, cap-drop, no-new-privileges, no host ports/socket, bounded writable data.")
PY

echo "Proving SQLite authentication state survives full Manager container replacement..."
docker compose -f "$COMPOSE_FILE" rm -sf manager >/dev/null
docker compose -f "$COMPOSE_FILE" up -d manager
wait_healthy manager
docker compose -f "$COMPOSE_FILE" restart caddy >/dev/null
wait_healthy caddy
docker compose -f "$COMPOSE_FILE" exec -T approved-client python /client.py approved

echo "Checking rendered configuration, inspection data, and logs for synthetic secret leakage..."
docker compose -f "$COMPOSE_FILE" logs --no-color > "$WORK_DIR/runtime.log"
for sensitive_value in "$DJANGO_SECRET_VALUE" "$ADMIN_PASSWORD_VALUE"; do
  if grep -Fq "$sensitive_value" "$WORK_DIR/rendered.json" "$WORK_DIR/manager-inspect.json" "$WORK_DIR/runtime.log"; then
    echo "ERROR: synthetic secret value leaked into rendered configuration, inspection data, or logs" >&2
    exit 1
  fi
done

if grep -R -Fq "$DJANGO_SECRET_VALUE" "$REPO_ROOT" --exclude-dir=.git; then
  echo "ERROR: synthetic Django secret value appeared in repository files" >&2
  exit 1
fi
if grep -R -Fq "$ADMIN_PASSWORD_VALUE" "$REPO_ROOT" --exclude-dir=.git; then
  echo "ERROR: synthetic admin password appeared in repository files" >&2
  exit 1
fi

echo "Manager runtime and private-publication readiness validation passed."
