#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/scripts/backup_restore.compose.yml"
WORK_DIR="$(mktemp -d)"
export MANAGER_BACKUP_WORK_DIR="$WORK_DIR"
export MANAGER_BACKUP_VOLUME_PREFIX="gcm-backup-${GITHUB_RUN_ID:-local}-$$"

cleanup() {
  docker compose -f "$COMPOSE_FILE" down --volumes --remove-orphans >/dev/null 2>&1 || true
  docker volume rm \
    "${MANAGER_BACKUP_VOLUME_PREFIX}-primary" \
    "${MANAGER_BACKUP_VOLUME_PREFIX}-restored" \
    "${MANAGER_BACKUP_VOLUME_PREFIX}-backup" >/dev/null 2>&1 || true
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
chmod 0444 "$WORK_DIR/django-secret-key" "$WORK_DIR/admin-password"

DJANGO_SECRET_VALUE="$(cat "$WORK_DIR/django-secret-key")"
ADMIN_PASSWORD_VALUE="$(cat "$WORK_DIR/admin-password")"

cd "$REPO_ROOT"

echo "Validating SQLite backup utility syntax..."
python -m py_compile ops/sqlite-backup.py

echo "Rendering disposable Manager backup/restore topology..."
docker compose -f "$COMPOSE_FILE" config --format json > "$WORK_DIR/rendered.json"
python - "$WORK_DIR/rendered.json" "$MANAGER_BACKUP_VOLUME_PREFIX" <<'PY'
import json
import sys

config = json.load(open(sys.argv[1], encoding="utf-8"))
prefix = sys.argv[2]
services = config["services"]
for name, service in services.items():
    if service.get("ports"):
        raise SystemExit(f"service {name!r} unexpectedly publishes a host port")

for name in ("manager-primary", "manager-restored"):
    service = services[name]
    if service.get("read_only") is not True:
        raise SystemExit(f"{name} must use a read-only root filesystem")
    if "ALL" not in service.get("cap_drop", []):
        raise SystemExit(f"{name} must drop all Linux capabilities")
    if not any(str(item).startswith("no-new-privileges") for item in service.get("security_opt", [])):
        raise SystemExit(f"{name} must enforce no-new-privileges")
    if service.get("environment", {}).get("DJANGO_SECRET_KEY_FILE") != "/run/secrets/django_secret_key":
        raise SystemExit(f"{name} must use the file-backed Django secret")
    if service.get("environment", {}).get("DJANGO_SECRET_KEY"):
        raise SystemExit(f"{name} must not carry a direct Django secret value")

for name in ("backup-primary", "backup-restored", "restore-helper", "verify-backup", "secret-scan"):
    if services[name].get("network_mode") != "none":
        raise SystemExit(f"{name} must not have network access")

volume_names = {key: value.get("name") for key, value in config["volumes"].items()}
expected = {
    "manager_primary_data": f"{prefix}-primary",
    "manager_restored_data": f"{prefix}-restored",
    "manager_backup_data": f"{prefix}-backup",
}
if volume_names != expected:
    raise SystemExit(f"backup volume naming drift: expected {expected!r}, got {volume_names!r}")
if len(set(volume_names.values())) != 3:
    raise SystemExit("primary, restore-target, and backup storage must be distinct volumes")

print("Rendered topology assertions passed: no host ports, hardened Manager runtimes, offline helpers, independent backup volume.")
PY

echo "Building candidate Manager backup/restore images..."
docker compose -f "$COMPOSE_FILE" build

wait_healthy() {
  local service="$1"
  local container status
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

echo "Starting the primary disposable Manager runtime..."
docker compose -f "$COMPOSE_FILE" up -d manager-primary
wait_healthy manager-primary

echo "Seeding synthetic Manager-owned authentication and relational state..."
docker compose -f "$COMPOSE_FILE" exec -T manager-primary python manage.py shell -c \
  "from pathlib import Path; from django.contrib.auth import get_user_model; from django.contrib.auth.models import Group; User=get_user_model(); password=Path('/run/secrets/admin_password').read_text(encoding='utf-8').strip(); group,_=Group.objects.get_or_create(name='Synthetic Recovery Reviewers'); user,_=User.objects.get_or_create(username='synthetic-admin'); user.first_name='Pre Backup'; user.last_name='Recovery'; user.email='synthetic-admin@example.invalid'; user.is_staff=True; user.is_superuser=True; user.set_password(password); user.save(); user.groups.set([group]); assert user.check_password(password)" >/dev/null

docker compose -f "$COMPOSE_FILE" exec -T manager-primary python manage.py shell -c \
  "from django.contrib.auth import get_user_model; from django.contrib.auth.models import Group; User=get_user_model(); u=User.objects.get(username='synthetic-admin'); assert u.first_name=='Pre Backup'; assert u.groups.filter(name='Synthetic Recovery Reviewers').exists(); assert not User.objects.filter(username='post-backup-only').exists(); assert Group.objects.filter(name='Synthetic Recovery Reviewers').count()==1; print('Pre-backup Manager state assertions passed.')"

echo "Creating an online-consistent SQLite recovery point while Manager remains running..."
docker compose -f "$COMPOSE_FILE" run --rm backup-primary | tee "$WORK_DIR/pre-backup.json"
docker compose -f "$COMPOSE_FILE" run --rm verify-backup | tee "$WORK_DIR/pre-verify.json"
python - "$WORK_DIR/pre-backup.json" "$WORK_DIR/pre-verify.json" <<'PY'
import json
import sys

records = []
for filename in sys.argv[1:]:
    lines = [line.strip() for line in open(filename, encoding="utf-8") if line.strip().startswith("{")]
    if not lines:
        raise SystemExit(f"no JSON verification record found in {filename}")
    records.append(json.loads(lines[-1]))
for record in records:
    if record.get("integrity") != "ok" or record.get("foreign_keys") != "ok":
        raise SystemExit(f"invalid SQLite verification record: {record!r}")
    checksum = record.get("sha256", "")
    if len(checksum) != 64:
        raise SystemExit(f"invalid SHA-256 metadata: {record!r}")
if records[0]["sha256"] != records[1]["sha256"]:
    raise SystemExit("backup checksum changed between creation and immediate verification")
print("Pre-loss recovery point integrity and checksum assertions passed.")
PY

echo "Proving an existing recovery point cannot be silently overwritten..."
if docker compose -f "$COMPOSE_FILE" run --rm backup-primary > "$WORK_DIR/overwrite.log" 2>&1; then
  echo "ERROR: backup utility overwrote an existing recovery point" >&2
  exit 1
fi
if ! grep -Fq "refusing to overwrite" "$WORK_DIR/overwrite.log"; then
  echo "ERROR: expected fail-closed overwrite message was not observed" >&2
  cat "$WORK_DIR/overwrite.log" >&2
  exit 1
fi

echo "Mutating the primary database after the recovery point to prove point-in-time restoration..."
docker compose -f "$COMPOSE_FILE" exec -T manager-primary python manage.py shell -c \
  "from django.contrib.auth import get_user_model; User=get_user_model(); u=User.objects.get(username='synthetic-admin'); u.first_name='Post Backup Mutation'; u.save(update_fields=['first_name']); User.objects.create_user(username='post-backup-only', password=None); assert User.objects.filter(username='post-backup-only').exists()" >/dev/null

echo "Destroying the primary disposable Manager container and its entire data volume..."
docker compose -f "$COMPOSE_FILE" stop manager-primary >/dev/null
docker compose -f "$COMPOSE_FILE" rm -sf manager-primary >/dev/null
docker volume rm "${MANAGER_BACKUP_VOLUME_PREFIX}-primary" >/dev/null
if docker volume inspect "${MANAGER_BACKUP_VOLUME_PREFIX}-primary" >/dev/null 2>&1; then
  echo "ERROR: primary Manager data volume still exists after destructive-loss step" >&2
  exit 1
fi
docker volume inspect "${MANAGER_BACKUP_VOLUME_PREFIX}-backup" >/dev/null

echo "Creating and verifying a clean replacement Manager data volume..."
docker compose -f "$COMPOSE_FILE" run --rm --no-deps manager-restored python manage.py migrate --noinput >/dev/null
docker compose -f "$COMPOSE_FILE" run --rm --no-deps manager-restored python manage.py shell -c \
  "from django.contrib.auth import get_user_model; User=get_user_model(); assert not User.objects.filter(username='synthetic-admin').exists(); assert not User.objects.filter(username='post-backup-only').exists(); print('Clean restore-target assertions passed.')"

echo "Removing only the clean placeholder database before offline restoration..."
docker compose -f "$COMPOSE_FILE" run --rm --no-deps manager-restored python -c \
  "from pathlib import Path; root=Path('/app/data'); [path.unlink() for path in root.glob('db.sqlite3*') if path.is_file()]; assert not (root/'db.sqlite3').exists()"

echo "Restoring the verified recovery point into the clean replacement volume..."
docker compose -f "$COMPOSE_FILE" run --rm restore-helper | tee "$WORK_DIR/restore.json"

if docker compose -f "$COMPOSE_FILE" run --rm restore-helper > "$WORK_DIR/repeat-restore.log" 2>&1; then
  echo "ERROR: restore utility overwrote the restored Manager database" >&2
  exit 1
fi
if ! grep -Fq "refusing to overwrite" "$WORK_DIR/repeat-restore.log"; then
  echo "ERROR: repeated restore did not fail closed as expected" >&2
  cat "$WORK_DIR/repeat-restore.log" >&2
  exit 1
fi

echo "Starting the restored Manager and reapplying compatible migrations..."
docker compose -f "$COMPOSE_FILE" up -d manager-restored
wait_healthy manager-restored

echo "Validating recovered point-in-time state, relationships, health, and authentication..."
docker compose -f "$COMPOSE_FILE" exec -T manager-restored python manage.py shell -c \
  "from pathlib import Path; from django.contrib.auth import get_user_model; from django.contrib.auth.models import Group; from django.test import Client; User=get_user_model(); password=Path('/run/secrets/admin_password').read_text(encoding='utf-8').strip(); u=User.objects.get(username='synthetic-admin'); assert u.first_name=='Pre Backup'; assert u.last_name=='Recovery'; assert u.email=='synthetic-admin@example.invalid'; assert u.groups.filter(name='Synthetic Recovery Reviewers').exists(); assert Group.objects.filter(name='Synthetic Recovery Reviewers').count()==1; assert not User.objects.filter(username='post-backup-only').exists(); assert u.check_password(password); client=Client(); assert client.login(username='synthetic-admin', password=password); response=client.get('/', secure=True, HTTP_HOST='manager.goreecloud.com'); assert response.status_code==200; assert b'GoreeCloud Manager' in response.content; health=client.get('/healthz/', secure=True, HTTP_HOST='manager.goreecloud.com'); assert health.status_code==200; assert health.json()=={'status':'ok','service':'goreecloud-manager'}; print('Recovered Manager state, authentication, Overview, and health assertions passed.')"

echo "Creating a distinct post-recovery backup to prove backup protection can resume..."
docker compose -f "$COMPOSE_FILE" run --rm backup-restored | tee "$WORK_DIR/post-backup.json"
docker compose -f "$COMPOSE_FILE" run --rm verify-backup \
  python /app/ops/sqlite-backup.py verify /app/backups/manager-post-recovery.sqlite3 \
  | tee "$WORK_DIR/post-verify.json"

echo "Proving the post-recovery recovery point can itself be restored to a separate file..."
docker compose -f "$COMPOSE_FILE" run --rm restore-helper \
  python /app/ops/sqlite-backup.py restore \
  /app/backups/manager-post-recovery.sqlite3 \
  /app/data/post-recovery-verify.sqlite3 \
  | tee "$WORK_DIR/post-restore.json"
docker compose -f "$COMPOSE_FILE" run --rm --no-deps manager-restored \
  python /app/ops/sqlite-backup.py verify /app/data/post-recovery-verify.sqlite3 \
  | tee "$WORK_DIR/post-restore-verify.json"

python - "$WORK_DIR/post-backup.json" "$WORK_DIR/post-verify.json" "$WORK_DIR/post-restore.json" "$WORK_DIR/post-restore-verify.json" <<'PY'
import json
import sys

for filename in sys.argv[1:]:
    lines = [line.strip() for line in open(filename, encoding="utf-8") if line.strip().startswith("{")]
    if not lines:
        raise SystemExit(f"no JSON verification record found in {filename}")
    record = json.loads(lines[-1])
    if record.get("integrity") != "ok" or record.get("foreign_keys") != "ok":
        raise SystemExit(f"post-recovery SQLite validation failed: {record!r}")
    if len(record.get("sha256", "")) != 64:
        raise SystemExit(f"post-recovery SHA-256 metadata invalid: {record!r}")
print("Post-recovery backup, restore, integrity, and checksum assertions passed.")
PY

echo "Checking backup artifacts for plaintext synthetic secrets and restrictive modes..."
docker compose -f "$COMPOSE_FILE" run --rm secret-scan

echo "Checking rendered configuration, live inspection, and runtime logs for synthetic secret leakage..."
docker compose -f "$COMPOSE_FILE" logs --no-color > "$WORK_DIR/runtime.log"
RESTORED_ID="$(docker compose -f "$COMPOSE_FILE" ps -q manager-restored)"
docker inspect "$RESTORED_ID" > "$WORK_DIR/restored-inspect.json"
for sensitive_value in "$DJANGO_SECRET_VALUE" "$ADMIN_PASSWORD_VALUE"; do
  if grep -Fq "$sensitive_value" "$WORK_DIR/rendered.json" "$WORK_DIR/restored-inspect.json" "$WORK_DIR/runtime.log"; then
    echo "ERROR: synthetic secret value leaked into rendered configuration, inspection data, or logs" >&2
    exit 1
  fi
done

python - "$WORK_DIR/restored-inspect.json" <<'PY'
import json
import sys

inspect = json.load(open(sys.argv[1], encoding="utf-8"))[0]
if inspect["Config"].get("User") != "manager":
    raise SystemExit("restored Manager did not run as the non-root manager user")
if inspect["HostConfig"].get("ReadonlyRootfs") is not True:
    raise SystemExit("restored Manager root filesystem is not read-only")
if inspect["HostConfig"].get("PortBindings"):
    raise SystemExit("restored Manager unexpectedly has host-published ports")
if any(mount.get("Destination") == "/var/run/docker.sock" for mount in inspect["Mounts"]):
    raise SystemExit("restored Manager unexpectedly received the Docker socket")
print("Restored runtime boundary remained hardened after recovery.")
PY

echo "Manager backup and restore readiness validation passed."
