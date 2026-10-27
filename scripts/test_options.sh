#!/usr/bin/env bash
# Options Lab + universe + income planner sweep (through the Caddy gateway :81,
# same path the preview URL uses). Complements test_gateway.sh.
# Usage: test_options.sh [round]
GW="http://localhost:81"
ROUND="${1:-1}"
PASS=0; FAIL=0
declare -a RESULTS

check() {
  local name="$1" method="$2" url="$3" body="$4" expect="${5:-200}"
  local args=(-s -o /tmp/resp_opt.json -w "%{http_code}" -X "$method" --max-time 180)
  [ -n "$body" ] && args+=(-H 'Content-Type: application/json' -d "$body")
  local code
  code=$(curl "${args[@]}" "$url" 2>/dev/null)
  local snippet
  snippet=$(head -c 110 /tmp/resp_opt.json 2>/dev/null | tr -d '\n')
  if [ "$code" = "$expect" ]; then
    RESULTS+=("PASS [$name] $method $url -> $code :: $snippet")
    PASS=$((PASS+1))
  else
    RESULTS+=("FAIL [$name] $method $url -> $code (want $expect) :: $snippet")
    FAIL=$((FAIL+1))
  fi
}

# JSON assertion helper: check "name" "py_expr_on_d" "expected"
assert() {
  local name="$1" expr="$2" want="$3"
  local got
  got=$(python3 /home/z/my-project/scripts/assert_eval.py "$expr" 2>/dev/null)
  if [ "$got" = "$want" ]; then
    RESULTS+=("PASS [$name] $expr == $want")
    PASS=$((PASS+1))
  else
    RESULTS+=("FAIL [$name] $expr == $want (got: $got)")
    FAIL=$((FAIL+1))
  fi
}

echo "=== Round $ROUND — options/universe/income sweep $(date '+%H:%M:%S') ==="

# ---- universe ------------------------------------------------------------
check "universe-search" GET "$GW/api/astro/universe?q=nvda&limit=5" "" 200
assert "universe-nvda-first" "['results'][0]['symbol']" "NVDA"
check "universe-meta" GET "$GW/api/astro/universe/meta" "" 200
assert "universe-total-gt-300" "['meta']['total']>300" "True"
check "universe-india-etf" GET "$GW/api/astro/universe?market=India&type=etf&limit=10" "" 200
assert "universe-bees" "sum(1 for r in ['results'] if 'BEES' in r['symbol'])>=3" "True"
check "universe-options-only-uk" GET "$GW/api/astro/universe?market=UK&options_only=true" "" 200
assert "universe-uk-no-options" "['count']" "0"

# ---- options chain ---------------------------------------------------------
check "expirations-spy" GET "$GW/api/astro/options/expirations/SPY" "" 200
assert "spy-has-expiries" "len(['expirations'])>0" "True"
EXP=$(python3 -c "
import json
d=json.load(open('/tmp/resp_opt.json'))
# pick ~35-50 DTE monthly-ish expiry
best=min(range(len(d['expirations'])), key=lambda i: abs((d['dte'][i] or 35)-42))
print(d['expirations'][best])
")
echo "  (chosen SPY expiry: $EXP)"
check "chain-spy" GET "$GW/api/astro/options/chain/SPY?expiry=$EXP" "" 200
assert "chain-spy-source" "['source'] in ('live','synthetic')" "True"
assert "chain-spy-strikes" "len(['rows'])>20" "True"
check "chain-synthetic-nsei" GET "$GW/api/astro/options/chain/^NSEI?expiry=$(date -d '+30 days' +%Y-%m-%d)" "" 200
assert "nsei-dte-positive" "['dte']>25" "True"

# ---- strategy engine -------------------------------------------------------
check "strategies-catalog" GET "$GW/api/astro/options/strategies" "" 200
assert "catalog-14" "len(['strategies'])" "14"
check "iron-condor" POST "$GW/api/astro/options/strategy" '{"symbol":"SPY","strategy":"iron_condor","expiry":"'"$EXP"'","qty":1}' 200
assert "condor-pop" "0<['pop']<1" "True"
assert "condor-defined-risk" "['max_loss_unlimited']" "False"
assert "condor-capital" "['capital_required']>0" "True"
check "jade-lizard" POST "$GW/api/astro/options/strategy" '{"symbol":"SPY","strategy":"jade_lizard","expiry":"'"$EXP"'"}' 200
assert "lizard-credit" "['net_credit']>0" "True"
check "calendar-two-expiry" POST "$GW/api/astro/options/strategy" '{"symbol":"SPY","strategy":"calendar_spread","expiry":"'"$EXP"'"}' 200
assert "calendar-vega-positive" "['net_greeks']['vega']>0" "True"
check "covered-call" POST "$GW/api/astro/options/strategy" '{"symbol":"AAPL","strategy":"covered_call","qty":2}' 200
assert "cc-stock-leg" "any(l['cp']=='stock' for l in ['legs'])" "True"
check "unknown-strategy-404" POST "$GW/api/astro/options/strategy" '{"symbol":"SPY","strategy":"nope"}' 404

# ---- income planner --------------------------------------------------------
check "income-plan-100k" POST "$GW/api/astro/income/plan" '{"capital":100000,"target_weekly":500,"focus":"uk"}' 200
assert "plan-verdict-valid" "['verdict'] in ('achievable','stretch','below_base_regime')" "True"
assert "plan-ladder-4" "len(['ladder'])" "4"
assert "plan-capital-table-5" "len(['capital_table'])" "5"
assert "plan-has-ticket" "sum(1 for b in ['ladder'] if b['ticket'])>=2" "True"
check "income-plan-small" POST "$GW/api/astro/income/plan" '{"capital":5000,"target_weekly":500}' 200
assert "plan-small-honest" "['max_sustainable_weekly']<['inputs']['target_weekly']" "True"

echo
for r in "${RESULTS[@]}"; do echo "$r"; done
echo "-------------------------------------------"
echo "Round $ROUND: $PASS PASS / $FAIL FAIL"
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
