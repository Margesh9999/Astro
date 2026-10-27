#!/usr/bin/env bash
# End-to-end sweep through the Caddy gateway (:81) — simulates the preview URL path.
# Usage: test_gateway.sh [round]
GW="http://localhost:81"
ROUND="${1:-1}"
PASS=0; FAIL=0
declare -a RESULTS

check() {
  local name="$1" method="$2" url="$3" body="$4" expect="${5:-200}"
  local args=(-s -o /tmp/resp.json -w "%{http_code}" -X "$method" --max-time 120)
  [ -n "$body" ] && args+=(-H 'Content-Type: application/json' -d "$body")
  local code
  code=$(curl "${args[@]}" "$url" 2>/dev/null)
  local snippet
  snippet=$(head -c 120 /tmp/resp.json 2>/dev/null | tr -d '\n')
  if [ "$code" = "$expect" ]; then
    RESULTS+=("PASS [$name] $method $url -> $code :: $snippet")
    PASS=$((PASS+1))
  else
    RESULTS+=("FAIL [$name] $method $url -> $code (want $expect) :: $snippet")
    FAIL=$((FAIL+1))
  fi
}

echo "=== Round $ROUND — gateway sweep $(date '+%H:%M:%S') ==="

# 1. Root page through gateway (no transform)
check "root-page" GET "$GW/" "" 200

# 2. Backend health via Next proxy
check "health" GET "$GW/api/astro/health"

# 3. Symbols list
check "symbols" GET "$GW/api/astro/symbols"

# 4. Planetary positions (tropical + vedic)
check "planetary-tropical" GET "$GW/api/astro/planetary/2026-08-28?vedic=false"
check "planetary-vedic" GET "$GW/api/astro/planetary/2026-08-28?vedic=true"

# 5. Market quote (URL-encoded symbol as the browser sends it)
check "market" GET "$GW/api/astro/market/%5EGSPC"

# 6. Upcoming astro events
check "events" GET "$GW/api/astro/events?days=45"

# 7. Natal chart (Margesh)
check "natal" GET "$GW/api/astro/natal"

# 8. Heavy POST endpoints (train can take ~10s)
check "train" POST "$GW/api/astro/train" '{"symbol":"^GSPC","lookback_years":5,"use_vedic":false}'
check "predict" POST "$GW/api/astro/predict" '{"symbol":"^GSPC","days_ahead":5,"use_vedic":false}'
check "backtest" POST "$GW/api/astro/backtest" '{"symbol":"^GSPC","lookback_years":5,"use_vedic":false}'

# 9. Institutional desk — Suri astro-signal engine
check "astro-signal" GET "$GW/api/astro/astro-signal/%5EGSPC"

# 10. Institutional desk — ffn-style quant analytics + gs-quant risk
check "quant-stats" GET "$GW/api/astro/quant/stats/%5EGSPC?years=3"
check "quant-risk" GET "$GW/api/astro/quant/risk/%5EGSPC?years=3&conf=0.95&position=1000000"

# 11. Institutional desk — options lab (vollib/optlib/pysabr/TFF models)
check "opt-bs" POST "$GW/api/astro/options/price" '{"model":"bs","cp":"call","S":7700,"K":7800,"T":0.1,"r":0.04,"sigma":0.15}'
check "opt-crr" POST "$GW/api/astro/options/price" '{"model":"crr","cp":"put","S":7700,"K":7800,"T":0.1,"r":0.04,"sigma":0.15,"american":true}'
check "opt-heston" POST "$GW/api/astro/options/price" '{"model":"heston","cp":"call","S":7700,"K":7800,"T":0.25,"r":0.04,"kappa":2.0,"theta":0.06,"sigma_v":0.3,"rho":-0.7,"v0":0.04}'
check "opt-mc" POST "$GW/api/astro/options/price" '{"model":"mc","cp":"call","S":7700,"K":7800,"T":0.1,"r":0.04,"sigma":0.15,"n_paths":50000}'
check "opt-iv" POST "$GW/api/astro/options/iv" '{"price":105.5,"S":7700,"K":7800,"T":0.1,"r":0.04,"cp":"call"}'
check "opt-sabr" POST "$GW/api/astro/options/sabr" '{"forward":7700,"T":0.25,"atm_vol":0.15,"beta":1.0,"rho":-0.3,"nu":0.8}'

# 12. Bond analytics (pyql/FinancePy style)
check "bond" GET "$GW/api/astro/bond?face=1000&coupon=0.05&ytm=0.045&years=10&freq=2"

for r in "${RESULTS[@]}"; do echo "$r"; done
echo "=== Round $ROUND result: PASS=$PASS FAIL=$FAIL ==="
[ "$FAIL" -eq 0 ]
