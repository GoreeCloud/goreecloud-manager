#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="scripts/monitoring_alert.compose.yml"
CADDYFILE="scripts/monitoring_alert.Caddyfile"
MONITOR_CONTRACT="scripts/manager_uptime_kuma_monitor.json"
PROJECT_NAME="goreecloud-manager-monitoring-alert-${GITHUB_RUN_ID:-local}-$$"
WORK_DIR="$(mktemp -d)"
export MANAGER_MONITORING_WORK_DIR="$WORK_DIR"
compose=(docker compose --project-name "$PROJECT_NAME" --file "$COMPOSE_FILE")

cleanup() {
  set +e
  "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

chmod 700 "$WORK_DIR"
DJANGO_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
random_token() {
  python3 - <<'PY'
import secrets
import string
alphabet = string.ascii_lowercase + string.digits
print("tk_" + "".join(secrets.choice(alphabet) for _ in range(29)))
PY
}
PUBLISHER_TOKEN="$(random_token)"
SUBSCRIBER_TOKEN="$(random_token)"
printf '%s\n' "$DJANGO_SECRET" > "$WORK_DIR/django-secret-key"
printf '%s\n' "$PUBLISHER_TOKEN" > "$WORK_DIR/ntfy-publisher-token"
printf '%s\n' "$SUBSCRIBER_TOKEN" > "$WORK_DIR/ntfy-subscriber-token"
chmod 0444 "$WORK_DIR/django-secret-key" "$WORK_DIR/ntfy-publisher-token" "$WORK_DIR/ntfy-subscriber-token"

TEST_PASSWORD_HASH='$2a$10$YLiO8U21sX1uhZamTLJXHuxgVC0Z/GKISibrKCLohPgtG7yIxSk4C'
cat > "$WORK_DIR/ntfy-server.yml" <<EOF_NTFY
listen-http: ":80"
cache-file: "/var/lib/ntfy/cache.db"
cache-duration: "1h"
auth-file: "/var/lib/ntfy/auth.db"
auth-default-access: "deny-all"
enable-login: true
require-login: true
enable-signup: false
auth-users:
  - "uptime-kuma-ci:${TEST_PASSWORD_HASH}:user"
  - "uptime-subscriber-ci:${TEST_PASSWORD_HASH}:user"
auth-access:
  - "uptime-kuma-ci:goreecloud-uptime:write-only"
  - "uptime-subscriber-ci:goreecloud-uptime:read-only"
auth-tokens:
  - "uptime-kuma-ci:${PUBLISHER_TOKEN}:Disposable Uptime Kuma publisher"
  - "uptime-subscriber-ci:${SUBSCRIBER_TOKEN}:Disposable Uptime subscriber"
EOF_NTFY
chmod 0444 "$WORK_DIR/ntfy-server.yml"

echo "Validating source-controlled Manager monitoring contract..."
python3 - "$MONITOR_CONTRACT" <<'PY'
import json, sys
contract=json.load(open(sys.argv[1], encoding="utf-8"))
if contract.get("state") != "proposed-not-provisioned": raise SystemExit("contract must not claim provisioning")
monitor=contract["monitor"]
expected={"name":"GoreeCloud Manager","url":"https://manager.goreecloud.com/healthz/","interval_seconds":60,"accepted_status_codes":[200],"tls_verification_required":True,"private_caddy_path_required":True}
for key,value in expected.items():
    if monitor.get(key) != value: raise SystemExit(f"monitor contract drift for {key}: {monitor.get(key)!r}")
source=contract["source_identity"]
if source.get("container") != "uptime-kuma" or source.get("docker_network") != "proxy" or source.get("ipv4") != "172.19.0.50" or source.get("caddy_allowlist_required") is not True:
    raise SystemExit("Uptime Kuma source identity drifted")
notification=contract["notification"]
expected_notification={"service_identity":"uptime-kuma","permission":"write-only","internal_server_url":"http://ntfy:80","topic":"goreecloud-uptime","down_title":"GoreeCloud Manager DOWN","up_title":"GoreeCloud Manager RECOVERED"}
for key,value in expected_notification.items():
    if notification.get(key) != value: raise SystemExit(f"notification contract drift for {key}")
limitations=contract["limitations"]
if any(limitations.get(key) is not False for key in ("production_monitor_registered","production_notification_route_changed","independent_out_of_band_alerting_proven")):
    raise SystemExit("contract must not claim production monitoring/alerting evidence")
print("Manager monitoring contract preserves private health, fixed monitor source, and least-privilege notification boundary.")
PY

grep -Fq 'manager.goreecloud.com {' "$CADDYFILE"
grep -Fq '@approved_client remote_ip 100.64.0.0/10 172.19.0.50' "$CADDYFILE"
grep -Fq 'reverse_proxy goreecloud-manager:8000' "$CADDYFILE"
grep -Fq 'respond "Forbidden" 403' "$CADDYFILE"
grep -Fq 'tls internal' "$CADDYFILE"

"${compose[@]}" config --format json > "$WORK_DIR/compose.json"
python3 - "$WORK_DIR/compose.json" <<'PY'
import json, sys
config=json.load(open(sys.argv[1], encoding="utf-8")); services=config["services"]
for name,service in services.items():
    if service.get("ports"): raise SystemExit(f"{name} unexpectedly publishes host ports")
expected={name:{"proxy"} for name in ("manager","caddy","ntfy","monitor","subscriber")}
for name,wanted in expected.items():
    networks=services[name].get("networks",{}); actual=set(networks if isinstance(networks,list) else networks.keys())
    if actual != wanted: raise SystemExit(f"{name} network drift: {actual!r}")
if services["monitor"]["networks"]["proxy"].get("ipv4_address") != "172.19.0.50": raise SystemExit("monitor fixed IP drift")
manager=services["manager"]
if manager.get("read_only") is not True: raise SystemExit("Manager root filesystem must be read-only")
if "ALL" not in manager.get("cap_drop",[]): raise SystemExit("Manager must drop all capabilities")
if not any(str(item).startswith("no-new-privileges") for item in manager.get("security_opt",[])): raise SystemExit("Manager must use no-new-privileges")
if manager.get("environment",{}).get("DJANGO_SECRET_KEY_FILE") != "/run/secrets/django_secret_key": raise SystemExit("Manager must use file-backed Django secret")
print("Rendered monitoring topology has zero host ports, exact network scope, fixed monitor identity, and hardened Manager runtime.")
PY

echo "Building Manager and starting private monitoring topology..."
"${compose[@]}" build manager
"${compose[@]}" up --detach --wait manager caddy
"${compose[@]}" up --detach ntfy monitor subscriber
"${compose[@]}" exec -T caddy caddy validate --config /etc/caddy/Caddyfile

for attempt in $(seq 1 30); do
  if "${compose[@]}" exec -T monitor python - <<'PY' >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("http://ntfy/v1/health", timeout=3)
PY
  then break; fi
  if [[ "$attempt" -eq 30 ]]; then "${compose[@]}" logs --no-color ntfy || true; echo "Disposable ntfy did not become healthy." >&2; exit 1; fi
  sleep 1
done

echo "Verifying healthy private HTTPS monitoring path and no false-positive alert..."
"${compose[@]}" exec -T monitor python /client.py probe-up
"${compose[@]}" exec -T subscriber python /client.py assert-empty

echo "Verifying least-privilege ntfy permissions..."
"${compose[@]}" exec -T monitor python /client.py publisher-cannot-read
"${compose[@]}" exec -T subscriber python /client.py subscriber-cannot-publish
"${compose[@]}" exec -T subscriber python /client.py anonymous-cannot-read

echo "Simulating Manager outage and requiring a DOWN alert..."
"${compose[@]}" stop manager
"${compose[@]}" exec -T monitor python /client.py evaluate down
"${compose[@]}" exec -T subscriber python /client.py assert-sequence down

echo "Restoring Manager and requiring a RECOVERED alert..."
"${compose[@]}" up --detach --wait manager
"${compose[@]}" exec -T monitor python /client.py evaluate up
"${compose[@]}" exec -T subscriber python /client.py assert-sequence down up

echo "Inspecting runtime source identity, exposure, and Manager hardening..."
python3 - "$PROJECT_NAME" "$COMPOSE_FILE" <<'PY'
import json, subprocess, sys
project, compose_file=sys.argv[1:]
base=["docker","compose","--project-name",project,"--file",compose_file]
expected={name:{f"{project}_proxy"} for name in ("manager","caddy","ntfy","monitor","subscriber")}
inspections={}
for name,wanted in expected.items():
    cid=subprocess.check_output(base+["ps","-q",name],text=True).strip()
    if not cid: raise SystemExit(f"missing running container for {name}")
    inspect=json.loads(subprocess.check_output(["docker","inspect",cid],text=True))[0]; inspections[name]=inspect
    if inspect["HostConfig"].get("PortBindings") not in ({},None): raise SystemExit(f"{name} has host port bindings")
    actual=set(inspect["NetworkSettings"]["Networks"])
    if actual != wanted: raise SystemExit(f"{name} runtime network drift: {actual!r}")
monitor_ip=inspections["monitor"]["NetworkSettings"]["Networks"][f"{project}_proxy"]["IPAddress"]
if monitor_ip != "172.19.0.50": raise SystemExit(f"runtime monitor IP drift: {monitor_ip}")
manager=inspections["manager"]
if manager["Config"].get("User") != "manager": raise SystemExit("Manager runtime is not non-root manager user")
if manager["HostConfig"].get("ReadonlyRootfs") is not True: raise SystemExit("Manager runtime rootfs is not read-only")
if "ALL" not in (manager["HostConfig"].get("CapDrop") or []): raise SystemExit("Manager did not drop all capabilities")
if any(m.get("Destination") == "/var/run/docker.sock" for m in manager["Mounts"]): raise SystemExit("Manager unexpectedly has Docker socket")
print("Runtime monitor source, zero-host-port boundary, network scope, and Manager hardening are correct.")
PY

"${compose[@]}" logs --no-color > "$WORK_DIR/stack.log"
for container_id in $("${compose[@]}" ps -q); do docker inspect "$container_id"; done > "$WORK_DIR/inspect.json"
for artifact in "$WORK_DIR/stack.log" "$WORK_DIR/inspect.json" "$WORK_DIR/compose.json"; do
  for secret in "$DJANGO_SECRET" "$PUBLISHER_TOKEN" "$SUBSCRIBER_TOKEN"; do
    if grep -Fq "$secret" "$artifact"; then echo "Disposable secret leaked into $(basename "$artifact")." >&2; exit 1; fi
  done
done
if grep -Eq 'DisallowedHost|Invalid HTTP_HOST|CSRF verification failed' "$WORK_DIR/stack.log"; then echo "Manager logs contain monitoring-path host/CSRF errors." >&2; exit 1; fi

echo "Manager monitoring and alert-delivery readiness validation passed."
echo "Validated: proposed Uptime Kuma contract, exact private HTTPS /healthz/ path, 172.19.0.50 source identity, Caddy allowlist, disposable ntfy write-only publisher/read-only subscriber ACLs, healthy no-alert, outage -> DOWN, recovery -> RECOVERED, zero host ports, runtime scope, Manager hardening, and secret/log minimization."
echo "Not validated: real Uptime Kuma registration, production Caddy change, live target source observation, real token installation, real administrative subscriber receipt, independent out-of-band alerting, or production activation."
