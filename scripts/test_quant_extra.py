"""Smoke test: round-3 quant analytics extensions (indicators, memory, MC, analogs)."""
import sys, json
sys.path.insert(0, "/home/z/my-project/mini-services/astro-backend")

from app.services.market_data import MarketDataService
from app.services.quant_analytics import build_analytics

svc = MarketDataService()
df = svc.fetch_historical_data("^GSPC", period="max", interval="1d")
print(f"^GSPC rows: {len(df)}")

closes = {}
for b in ("SPY", "GC=F", "^FTSE"):
    try:
        bdf = svc.fetch_historical_data(b, period="1y", interval="1d")
        if not bdf.empty and len(bdf) > 60:
            closes[b] = bdf["Close"]
    except Exception as e:
        print("bench fail", b, e)

pack = build_analytics(df, "^GSPC", benchmark_closes=closes,
                       benchmark_names={"SPY": "S&P 500 ETF", "GC=F": "Gold", "^FTSE": "FTSE 100"})
assert pack["success"]

required = ["macd", "bollinger", "stochastic", "atr", "obv", "rolling_sharpe",
            "distribution", "memory", "forecast"]
missing = [k for k in required if k not in pack]
assert not missing, f"MISSING BLOCKS: {missing}"
print("all blocks present:", required)

fc = pack["forecast"]
syn = fc["signal"]
assert -100 <= syn["score"] <= 100, syn["score"]
print(f"signal: {syn['score']:+d} {syn['label']} | pillars={len(syn['pillars'])} "
      f"bull={syn['n_bull']} bear={syn['n_bear']}")
assert len(syn["pillars"]) == 8
vol_p = next(p for p in syn["pillars"] if p["name"] == "Volatility")
ratio_val = float(vol_p["reading"].split("×")[0])
assert ratio_val < 5, f"vol_ratio units bug: {vol_p['reading']}"
print("volatility pillar sanity:", vol_p["reading"])

mc = fc["mc"]
if mc:
    for i in range(len(mc["dates"])):
        q = [mc["p5"][i], mc["p25"][i], mc["p50"][i], mc["p75"][i], mc["p95"][i]]
        assert q == sorted(q), f"quantile crossing at {i}: {q}"
    print(f"MC: last={mc['last']} 1w up={mc['prob_up_1w']}% 1m up={mc['prob_up_1m']}% "
          f"range1m=[{mc['range_low_1m']}, {mc['range_high_1m']}]")

an = fc["analogs"]
print(f"analogs: count={an['count']} code={an['code']} desc={an['description'][:80]}...")
if an.get("21d"):
    e = an["21d"]
    print(f"  21d fwd: n={e['count']} hit={e['hit_rate']}% mean={e['mean_pct']:+.2f}% "
          f"worst={e['worst_pct']:+.1f}% best={e['best_pct']:+.1f}%")
    assert 0 <= e["hit_rate"] <= 100
    assert e["worst_pct"] <= e["median_pct"] <= e["best_pct"]

mem = pack["memory"]
print(f"memory: hurst={mem['hurst']} regime={mem['regime']} acf1={mem['acf1']}")

if "correlations" in pack:
    pairs = pack["correlations"]["pairs"]
    print(f"correlations ({pack['correlations']['observation_days']}d):",
          {p['name']: p['corr'] for p in pairs})
    m = pack["correlations"]["matrix"]
    n = len(m["symbols"])
    assert all(len(row) == n for row in m["values"])
    for i in range(n):
        assert m["values"][i][i] == 1.0, "diagonal must be 1.0"

dist = pack["distribution"]
print(f"distribution: sigma={dist['sigma_pct']}% var95={dist['var95_daily_pct']}% "
      f"best={dist['best_day_pct']}% worst={dist['worst_day_pct']}% bins={len(dist['bins'])}")

for k in ("macd", "bollinger", "stochastic", "atr", "obv", "rolling_sharpe"):
    s = pack[k]["series"]
    n = len(s["dates"])
    assert all(len(v) == n for v in s.values()), f"{k} series length mismatch"
print("series length consistency OK; dates:", len(pack["macd"]["series"]["dates"]))

json.dumps(pack, allow_nan=False)  # must be strict-JSON serialisable
print("strict JSON OK, pack size:", len(json.dumps(pack)) // 1024, "KB")

# short-history edge case (60-90 rows): must not crash, extras degrade gracefully
small = df.tail(80)
p2 = build_analytics(small, "^GSPC")
assert p2["success"]
print("short-history OK — has forecast:", "forecast" in p2, "| has correlations:", "correlations" in p2)
print("ALL QUANT-EXTRA SMOKE CHECKS PASS")
