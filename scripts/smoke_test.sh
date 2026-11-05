#!/usr/bin/env bash
# End-to-end check against a real Docker daemon: starts app.py, deploys a sample
# repo, verifies the duplicate guard, the running app, the logs API and cleanup.
set -euo pipefail
cd "$(dirname "$0")/.."

REPO_URL="${REPO_URL:-https://github.com/Danial-Umer710/docker-nginx-website.git}"
NAME="$(basename "$REPO_URL" .git | tr '[:upper:]' '[:lower:]')-container"
API=http://127.0.0.1:5000

python app.py > /tmp/mini-devops-smoke.log 2>&1 &
APP_PID=$!
cleanup() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  kill "$APP_PID" 2>/dev/null || true
}
trap cleanup EXIT

for _ in $(seq 1 30); do curl -sf "$API/deploy" >/dev/null && break; sleep 1; done

URL=$(curl -s -X POST -d "repo=$REPO_URL" "$API/deploy" | grep -o 'http://localhost:[0-9]*' | head -1)
[ -n "$URL" ] || { echo "FAIL: first deploy"; cat /tmp/mini-devops-smoke.log; exit 1; }
echo "PASS  first deploy           -> $URL"

curl -s -X POST -d "repo=$REPO_URL" "$API/deploy" | grep -q "already deployed"
echo "PASS  second deploy skipped  -> already deployed"

code=000
for _ in $(seq 1 15); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$URL" || true)
  [ "$code" = 200 ] && break
  sleep 1
done
[ "$code" = 200 ] || { echo "FAIL: app returned $code"; exit 1; }
echo "PASS  deployed app           -> HTTP $code"

curl -sf "$API/logs/$NAME" | grep -q '"logs"'
echo "PASS  logs API               -> /logs/$NAME"

curl -s -o /dev/null "$API/delete/$NAME"
if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then echo "FAIL: container still exists"; exit 1; fi
echo "PASS  delete                 -> container removed"

echo "SMOKE TEST PASSED"
