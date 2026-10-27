#!/usr/bin/env bash
# Public preview URL sweep — hits the real external endpoint (round N).
BASE="https://preview-chat-7d20734d-f410-445e-bd86-366a66328d4b.space-z.ai"
ROUND="${1:-1}"
PASS=0; FAIL=0
declare -a RESULTS

check() {
  local name="$1" method="$2" url="$3" body="$4" expect="${5:-200}"
  local args=(-s -o /tmp/resp2.json -w "%{http_code}" -X "$method" --max-time 120)
  [ -n "$body" ] && args+=(-H 'Content-Type: application/json' -d "$body")
  local code
  code=$(curl "${args[@]}" "$url" 2>/dev/null)
  local snippet
  snippet=$(head -c 100 /tmp/resp2.json 2>/dev/null | tr -d '\n')
  if [ "$code" = "$expect" ]; then
    RESULTS+=("PASS [$name] $method ${url#$BASE} -> $code :: $snippet")
    PASS=$((PASS+1))
  else
    RESULTS+=("FAIL [$name] $method ${url#$BASE} -> $code (want $expect) :: $snippet")
    FAIL=$((FAIL+1))
  fi
}

echo "=== Round $ROUND — PUBLIC preview sweep $(date '+%H:%M:%S') ==="
check "root"      GET  "$BASE/"
check "health"    GET  "$BASE/api/astro/health"
check "symbols"   GET  "$BASE/api/astro/symbols"
check "planetary" GET  "$BASE/api/astro/planetary/2026-08-28?vedic=true"
check "market"    GET  "$BASE/api/astro/market/%5EGSPC"
check "events"    GET  "$BASE/api/astro/events?days=45"
check "natal"     GET  "$BASE/api/astro/natal"
check "predict"   POST "$BASE/api/astro/predict" '{"symbol":"^GSPC","days_ahead":5,"use_vedic":false}'

for r in "${RESULTS[@]}"; do echo "$r"; done
echo "=== Round $ROUND result: PASS=$PASS FAIL=$FAIL ==="
[ "$FAIL" -eq 0 ]
