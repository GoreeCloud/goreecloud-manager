#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_KEY="${GITHUB_RUN_ID:-local}-$$"
WORK_DIR="$(mktemp -d)"
BASE_DIR="$WORK_DIR/baseline-source"
SECRET_DIR="$WORK_DIR/secrets"
BASELINE_IMAGE="goreecloud-manager-upgrade-baseline:${RUN_KEY}"
CANDIDATE_IMAGE="goreecloud-manager-upgrade-candidate:${RUN_KEY}"
DATA_VOLUME="gcm-upgrade-${RUN_KEY}-data"
BACKUP_VOLUME="gcm-upgrade-${RUN_KEY}-backup"
BASELINE_CONTAINER="gcm-upgrade-${RUN_KEY}-baseline"
CANDIDATE_CONTAINER="gcm-upgrade-${RUN_KEY}-candidate"
ROLLBACK_CONTAINER="gcm-upgrade-${RUN_KEY}-rollback"
WORKTREE_ADDED=false

fail() {
  printf 'upgrade-rollback validation failed: %s\n' "$1" >&2
  exit 1
}

cleanup() {
  docker rm -f "$BASELINE_CONTAINER" "$CANDIDATE_CONTAINER" "$ROLLBACK_CONTAINER" >/dev/null 2>&1 || true
  docker volume rm "$DATA_VOLUME" "$BACKUP_VOLUME" >/dev/null 2>&1 || true
  docker image rm "$BASELINE_IMAGE" "$CANDIDATE_IMAGE" >/dev/null 2>&1 || true
  if [[ "$WORKTREE_ADDED" == "true" && -d "$BASE_DIR" ]]; then
    git worktree remove --force "$BASE_DIR" >/dev/null 2>&1 || true
  fi
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

mkdir -p "$SECRET_DIR"
chmod 700 "$SECRET_DIR"
python - <<'PY' > "$SECRET_DIR/django-secret-key"
import secrets
print(secrets.token_urlsafe(64))
PY
python - <<'PY' > "$SECRET_DIR/admin-password"
import secrets
print(secrets.token_urlsafe(48))
PY
# Docker bind-mounts these runtime-random files into a non-root container. Keep the
# parent directory private (0700), make only the ephemeral mounted files readable,
# and delete the entire directory during cleanup.
chmod 0444 "$SECRET_DIR/django-secret-key" "$SECRET_DIR/admin-password"

DJANGO_SECRET_VALUE="$(cat "$SECRET_DIR/django-secret-key")"
ADMIN_PASSWORD_VALUE="$(cat "$SECRET_DIR/admin-password")"

TARGET_REF="${UPGRADE_TARGET_REF:-$(git rev-parse HEAD)}"
BASE_REF="${UPGRADE_BASE_REF:-}"

if [[ -z "$BASE_REF" ]]; then
  CURRENT_BRANCH="$(git branch --show-current || true)"
  if [[ "$CURRENT_BRANCH" == "main" || "${GITHUB_REF_NAME:-}" == "main" ]]; then
    BASE_REF="$(git rev-parse "${TARGET_REF}^")"
  elif git show-ref --verify --quiet refs/remotes/origin/main; then
    BASE_REF="$(git merge-base "$TARGET_REF" refs/remotes/origin/main)"
  else
    BASE_REF="$(git rev-parse "${TARGET_REF}^")"
  fi
fi

if ! git cat-file -e "${TARGET_REF}^{commit}" 2>/dev/null; then
  fail "target revision $TARGET_REF is unavailable"
fi
if ! git cat-file -e "${BASE_REF}^{commit}" 2>/dev/null; then
  fail "baseline revision $BASE_REF is unavailable; CI must check out full history"
fi
TARGET_SHA="$(git rev-parse "$TARGET_REF")"
BASE_SHA="$(git rev-parse "$BASE_REF")"
if [[ "$TARGET_SHA" == "$BASE_SHA" ]]; then
  fail "baseline and target revisions must be different"
fi

printf 'Upgrade baseline: %s\n' "$BASE_SHA"
printf 'Upgrade target:   %s\n' "$TARGET_SHA"

git worktree add --detach "$BASE_DIR" "$BASE_SHA" >/dev/null
WORKTREE_ADDED=true

for required in Dockerfile manage.py ops/sqlite-backup.py; do
  [[ -f "$BASE_DIR/$required" ]] || fail "baseline revision does not contain $required"
  [[ -f "$ROOT_DIR/$required" ]] || fail "candidate revision does not contain $required"
done

printf '%s\n' 'Building previous accepted and candidate Manager images...'
docker build --quiet -t "$BASELINE_IMAGE" "$BASE_DIR" >/dev/null
docker build --quiet -t "$CANDIDATE_IMAGE" "$ROOT_DIR" >/dev/null
BASE_IMAGE_ID="$(docker image inspect "$BASELINE_IMAGE" --format '{{.Id}}')"
CANDIDATE_IMAGE_ID="$(docker image inspect "$CANDIDATE_IMAGE" --format '{{.Id}}')"
printf 'Baseline image: %s\nCandidate image: %s\n' "$BASE_IMAGE_ID" "$CANDIDATE_IMAGE_ID"

docker volume create "$DATA_VOLUME" >/dev/null
docker volume create "$BACKUP_VOLUME" >/dev/null

common_run_args=(
  --network none
  --read-only
  --tmpfs /tmp:rw,nosuid,nodev,noexec,size=32m
  --cap-drop ALL
  --security-opt no-new-privileges
  --pids-limit 256
  -e DJANGO_DEBUG=false
  -e DJANGO_SECRET_KEY_FILE=/run/secrets/django_secret_key
  -e DJANGO_ALLOWED_HOSTS=manager.goreecloud.com,127.0.0.1,localhost
  -e DJANGO_CSRF_TRUSTED_ORIGINS=https://manager.goreecloud.com
  -e DJANGO_DB_PATH=/app/data/db.sqlite3
  -e NETBIRD_ENABLED=false
  -e HEALTHCHECKS_ENABLED=false
  -e UPTIME_KUMA_ENABLED=false
  -e BESZEL_ENABLED=false
  -e KOPIA_ENABLED=false
  -e TASKS_ENABLED=false
  -v "$SECRET_DIR/django-secret-key:/run/secrets/django_secret_key:ro"
  -v "$SECRET_DIR/admin-password:/run/secrets/admin_password:ro"
)

run_app() {
  local image="$1"
  shift
  docker run --rm "${common_run_args[@]}" -v "$DATA_VOLUME:/app/data" "$image" "$@"
}

snapshot_state() {
  local image="$1"
  run_app "$image" python manage.py shell -c \
    "import json; from django.contrib.auth import get_user_model; from django.contrib.auth.models import Group; User=get_user_model(); u=User.objects.get(username='synthetic-admin'); print(json.dumps({'username':u.username,'first_name':u.first_name,'last_name':u.last_name,'email':u.email,'is_staff':u.is_staff,'is_superuser':u.is_superuser,'groups':sorted(u.groups.values_list('name',flat=True)),'candidate_only_exists':User.objects.filter(username='candidate-only').exists(),'reviewer_group_count':Group.objects.filter(name='Synthetic Upgrade Reviewers').count()}, sort_keys=True))"
}

wait_live_health() {
  local container="$1"
  for _ in $(seq 1 30); do
    if docker exec "$container" python -c \
      "import urllib.request; r=urllib.request.Request('http://127.0.0.1:8000/healthz/', headers={'Host':'manager.goreecloud.com','X-Forwarded-Proto':'https'}); assert urllib.request.urlopen(r, timeout=3).read() == b'{\"status\": \"ok\", \"service\": \"goreecloud-manager\"}'" \
      >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  docker logs "$container" >&2 || true
  fail "container $container did not become healthy"
}

start_live() {
  local image="$1"
  local container="$2"
  docker run -d --name "$container" \
    "${common_run_args[@]}" \
    -v "$DATA_VOLUME:/app/data" \
    "$image" \
    gunicorn goreecloud_manager.wsgi:application --bind 0.0.0.0:8000 --workers 2 --access-logfile - --error-logfile - \
    >/dev/null
  wait_live_health "$container"
}

printf '%s\n' 'Creating baseline Manager state on the previous accepted revision...'
run_app "$BASELINE_IMAGE" python manage.py migrate --noinput >/dev/null
run_app "$BASELINE_IMAGE" python manage.py check >/dev/null
run_app "$BASELINE_IMAGE" python manage.py migrate --check >/dev/null
run_app "$BASELINE_IMAGE" python manage.py shell -c \
  "from pathlib import Path; from django.contrib.auth import get_user_model; from django.contrib.auth.models import Group; User=get_user_model(); password=Path('/run/secrets/admin_password').read_text(encoding='utf-8').strip(); group,_=Group.objects.get_or_create(name='Synthetic Upgrade Reviewers'); user,_=User.objects.get_or_create(username='synthetic-admin'); user.first_name='Accepted Baseline'; user.last_name='Rollback'; user.email='synthetic-upgrade@example.invalid'; user.is_staff=True; user.is_superuser=True; user.set_password(password); user.save(); user.groups.set([group]); assert user.check_password(password)" >/dev/null
snapshot_state "$BASELINE_IMAGE" > "$WORK_DIR/baseline-state.json"

printf '%s\n' 'Starting the previous accepted image and validating live health...'
start_live "$BASELINE_IMAGE" "$BASELINE_CONTAINER"
docker rm -f "$BASELINE_CONTAINER" >/dev/null

printf '%s\n' 'Creating a verified pre-upgrade rollback point...'
docker run --rm --network none --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,noexec,size=32m \
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 \
  -v "$DATA_VOLUME:/app/source:ro" \
  -v "$BACKUP_VOLUME:/app/backups" \
  "$BASELINE_IMAGE" \
  python /app/ops/sqlite-backup.py backup /app/source/db.sqlite3 /app/backups/pre-upgrade.sqlite3 \
  > "$WORK_DIR/pre-upgrade.json"
docker run --rm --network none --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,noexec,size=32m \
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 \
  -v "$BACKUP_VOLUME:/app/backups:ro" \
  "$BASELINE_IMAGE" \
  python /app/ops/sqlite-backup.py verify /app/backups/pre-upgrade.sqlite3 \
  > "$WORK_DIR/pre-upgrade-verify.json"
PRE_UPGRADE_SHA="$(python - "$WORK_DIR/pre-upgrade.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding='utf-8'))['sha256'])
PY
)"
VERIFY_SHA="$(python - "$WORK_DIR/pre-upgrade-verify.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding='utf-8'))['sha256'])
PY
)"
[[ "$PRE_UPGRADE_SHA" == "$VERIFY_SHA" ]] || fail "pre-upgrade rollback-point checksum changed during verification"

printf '%s\n' 'Applying candidate migrations and checks to the previous accepted database...'
run_app "$CANDIDATE_IMAGE" python manage.py migrate --noinput >/dev/null
run_app "$CANDIDATE_IMAGE" python manage.py check >/dev/null
run_app "$CANDIDATE_IMAGE" python manage.py migrate --check >/dev/null
snapshot_state "$CANDIDATE_IMAGE" > "$WORK_DIR/upgraded-state.json"
cmp --silent "$WORK_DIR/baseline-state.json" "$WORK_DIR/upgraded-state.json" || fail "accepted baseline state changed unexpectedly during candidate upgrade"

printf '%s\n' 'Validating candidate authentication, Overview, and health against upgraded state...'
run_app "$CANDIDATE_IMAGE" python manage.py shell -c \
  "from pathlib import Path; from django.test import Client; password=Path('/run/secrets/admin_password').read_text(encoding='utf-8').strip(); client=Client(); assert client.login(username='synthetic-admin', password=password); response=client.get('/', secure=True, HTTP_HOST='manager.goreecloud.com'); assert response.status_code==200; assert b'GoreeCloud Manager' in response.content; health=client.get('/healthz/', secure=True, HTTP_HOST='manager.goreecloud.com'); assert health.status_code==200; assert health.json()=={'status':'ok','service':'goreecloud-manager'}" >/dev/null
start_live "$CANDIDATE_IMAGE" "$CANDIDATE_CONTAINER"

printf '%s\n' 'Adding candidate-era state that must disappear after rollback...'
docker exec "$CANDIDATE_CONTAINER" python manage.py shell -c \
  "from django.contrib.auth import get_user_model; User=get_user_model(); u=User.objects.get(username='synthetic-admin'); u.first_name='Candidate Era'; u.save(update_fields=['first_name']); User.objects.create_user(username='candidate-only', password=None); assert User.objects.filter(username='candidate-only').exists()" >/dev/null
docker logs "$CANDIDATE_CONTAINER" > "$WORK_DIR/candidate.log" 2>&1 || true
docker rm -f "$CANDIDATE_CONTAINER" >/dev/null

CURRENT_BACKUP_SHA="$(docker run --rm --network none -v "$BACKUP_VOLUME:/app/backups:ro" "$BASELINE_IMAGE" python -c "import hashlib; from pathlib import Path; p=Path('/app/backups/pre-upgrade.sqlite3'); print(hashlib.sha256(p.read_bytes()).hexdigest())")"
[[ "$CURRENT_BACKUP_SHA" == "$PRE_UPGRADE_SHA" ]] || fail "pre-upgrade rollback point changed during candidate validation"

printf '%s\n' 'Executing destructive rollback: remove upgraded data volume and restore the verified pre-upgrade point...'
docker volume rm "$DATA_VOLUME" >/dev/null
docker volume create "$DATA_VOLUME" >/dev/null
docker run --rm --network none --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,noexec,size=32m \
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 \
  -v "$BACKUP_VOLUME:/app/backups:ro" \
  -v "$DATA_VOLUME:/app/data" \
  "$BASELINE_IMAGE" \
  python /app/ops/sqlite-backup.py restore /app/backups/pre-upgrade.sqlite3 /app/data/db.sqlite3 \
  > "$WORK_DIR/rollback-restore.json"

printf '%s\n' 'Validating the previous accepted image against the restored pre-upgrade database...'
run_app "$BASELINE_IMAGE" python manage.py check >/dev/null
run_app "$BASELINE_IMAGE" python manage.py migrate --check >/dev/null
snapshot_state "$BASELINE_IMAGE" > "$WORK_DIR/rolled-back-state.json"
cmp --silent "$WORK_DIR/baseline-state.json" "$WORK_DIR/rolled-back-state.json" || fail "rollback did not restore exact selected baseline state"
run_app "$BASELINE_IMAGE" python manage.py shell -c \
  "from pathlib import Path; from django.contrib.auth import get_user_model; from django.test import Client; User=get_user_model(); password=Path('/run/secrets/admin_password').read_text(encoding='utf-8').strip(); u=User.objects.get(username='synthetic-admin'); assert u.first_name=='Accepted Baseline'; assert not User.objects.filter(username='candidate-only').exists(); assert u.check_password(password); client=Client(); assert client.login(username='synthetic-admin', password=password); response=client.get('/', secure=True, HTTP_HOST='manager.goreecloud.com'); assert response.status_code==200; health=client.get('/healthz/', secure=True, HTTP_HOST='manager.goreecloud.com'); assert health.status_code==200" >/dev/null
start_live "$BASELINE_IMAGE" "$ROLLBACK_CONTAINER"
docker logs "$ROLLBACK_CONTAINER" > "$WORK_DIR/rollback.log" 2>&1 || true

printf '%s\n' 'Inspecting rolled-back runtime security and secret minimization...'
docker inspect "$ROLLBACK_CONTAINER" > "$WORK_DIR/rollback-inspect.json"
python - "$WORK_DIR/rollback-inspect.json" <<'PY'
import json, sys
inspect = json.load(open(sys.argv[1], encoding='utf-8'))[0]
if inspect['Config'].get('User') != 'manager':
    raise SystemExit('rolled-back Manager did not use non-root manager user')
if inspect['HostConfig'].get('ReadonlyRootfs') is not True:
    raise SystemExit('rolled-back Manager root filesystem is not read-only')
if inspect['HostConfig'].get('PortBindings'):
    raise SystemExit('rolled-back Manager unexpectedly published a host port')
if 'ALL' not in (inspect['HostConfig'].get('CapDrop') or []):
    raise SystemExit('rolled-back Manager did not drop all Linux capabilities')
if not any(str(item).startswith('no-new-privileges') for item in (inspect['HostConfig'].get('SecurityOpt') or [])):
    raise SystemExit('rolled-back Manager lost no-new-privileges')
if any(mount.get('Destination') == '/var/run/docker.sock' for mount in inspect['Mounts']):
    raise SystemExit('rolled-back Manager unexpectedly received Docker socket')
print('Rolled-back runtime security assertions passed.')
PY

for sensitive_value in "$DJANGO_SECRET_VALUE" "$ADMIN_PASSWORD_VALUE"; do
  if grep -Fq "$sensitive_value" "$WORK_DIR/candidate.log" "$WORK_DIR/rollback.log" "$WORK_DIR/rollback-inspect.json"; then
    fail "synthetic secret value leaked into upgrade/rollback logs or inspection output"
  fi
done

docker run --rm --network none --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,noexec,size=32m \
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 \
  -v "$BACKUP_VOLUME:/app/backups:ro" \
  -v "$SECRET_DIR/django-secret-key:/run/secrets/django_secret_key:ro" \
  -v "$SECRET_DIR/admin-password:/run/secrets/admin_password:ro" \
  "$BASELINE_IMAGE" python -c \
  "from pathlib import Path; backup=Path('/app/backups/pre-upgrade.sqlite3').read_bytes(); values=[Path('/run/secrets/django_secret_key').read_bytes().strip(),Path('/run/secrets/admin_password').read_bytes().strip()]; assert all(value not in backup for value in values); assert (Path('/app/backups/pre-upgrade.sqlite3').stat().st_mode & 0o777) == 0o600; print('Rollback artifact secret and mode assertions passed.')"

printf 'Upgrade and rollback readiness validation passed. Baseline=%s Target=%s RollbackSHA256=%s\n' "$BASE_SHA" "$TARGET_SHA" "$PRE_UPGRADE_SHA"
