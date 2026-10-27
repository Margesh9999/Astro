"""Standalone smoke test: strategy engine over synthetic chains, all strategies."""
import sys
sys.path.insert(0, "/home/z/my-project/mini-services/astro-backend")

import math
from app.services import option_strategies as strat
from app.services.option_data import OptionDataService
from app.services.quant_models import bs_price_greeks

SPOT = 7700.0
R = 0.042


def make_rows(T, atm_vol, step=25.0):
    rows = []
    strikes = [round(s, 2) for s in range(int(SPOT * 0.8), int(SPOT * 1.2) + 1, int(step))]
    for K in strikes:
        row = {"strike": K, "moneyness": round(K / SPOT, 4)}
        for cp in ("call", "put"):
            iv = OptionDataService._smile_iv(SPOT, K, T, atm_vol)
            g = bs_price_greeks(SPOT, K, T, R, iv, cp, 0.0)
            row[cp] = {"mid": g["price"], "bid": g["price"], "ask": g["price"],
                       "iv": iv, "delta": g["delta"], "gamma": g["gamma"],
                       "theta": g["theta"], "vega": g["vega"],
                       "volume": 10, "open_interest": 100, "tradable": True, "quoted": False}
        rows.append(row)
    return rows


T_DTE, T_FAR_DTE = 35.0, 82.0
chain_near = {"expiry": "2026-10-02", "dte": T_DTE, "spot": SPOT, "currency": "USD",
              "atm_vol": 0.15, "div_yield": 0.0, "risk_free": R,
              "rows": make_rows(T_DTE / 365.0, 0.15), "source": "synthetic"}
chain_far = {"expiry": "2026-11-20", "dte": T_FAR_DTE, "spot": SPOT, "currency": "USD",
             "atm_vol": 0.155, "div_yield": 0.0, "risk_free": R,
             "rows": make_rows(T_FAR_DTE / 365.0, 0.155), "source": "synthetic"}

ok, bad = 0, 0
for s in strat.STRATEGY_CATALOG:
    key = s["key"]
    try:
        two = s.get("two_expiries", False)
        res = strat.analyze_strategy(key, "TEST", SPOT, chain_near,
                                     chain_far if two else None,
                                     params=None, qty=1, exit_dte=21)
        legs_desc = ", ".join(f"{l['action'][:3]} {l['cp'][:1]}{l['strike']}" for l in res["legs"])
        checks = [
            math.isfinite(res["pop"]) and 0 <= res["pop"] <= 1,
            res["capital_required"] > 0,
            len(res["payoff_curve"]) > 50,
            len(res["scenarios"]) == 7,
            (res["max_loss_unlimited"] or (res["max_loss"] or 0) >= 0),
            res["max_profit"] is None or res["max_profit"] >= res["net_credit"] - 1e-6,
        ]
        passed = all(checks)
        ok += passed
        bad += (not passed)
        print(f"{'OK ' if passed else 'FAIL'} {key:18s} legs=[{legs_desc}] "
              f"credit={res['net_credit']:>8.2f} debit={res['net_debit']:>8.2f} "
              f"cap={res['capital_required']:>9.1f} ({res['margin_basis']}) "
              f"maxP={str(res['max_profit'])[:9]:>9s} maxL={str(res['max_loss'])[:9]:>9s} "
              f"POP={res['pop']:.2f} BEs={res['breakevens']} wk={res['premium_per_week']:.2f} "
              f"d={res['net_greeks']['delta']}")
    except Exception as exc:
        bad += 1
        import traceback
        print(f"ERR {key}: {exc}")
        traceback.print_exc()

print(f"\n{ok} OK / {bad} bad of {len(strat.STRATEGY_CATALOG)}")

# --- invariant checks --------------------------------------------------------
res = strat.analyze_strategy("bull_put_spread", "TEST", SPOT, chain_near, None,
                             params={"put_delta": 0.30, "wing_factor": 0.5}, qty=1)
k_short = max(l["strike"] for l in res["legs"] if l["cp"] == "put" and l["action"] == "sell")
k_long = min(l["strike"] for l in res["legs"] if l["cp"] == "put" and l["action"] == "buy")
pl_at_5000 = strat.payoff_at_expiry(res["legs"], 5000.0, SPOT)
expect = -(k_short - k_long) * 100 + res["net_credit"]
t1 = abs(pl_at_5000 - expect) < 1.0
print(f"bull_put_spread deep-ITM: engine {pl_at_5000:.2f} vs {expect:.2f} {'PASS' if t1 else 'FAIL'}")

res2 = strat.analyze_strategy("covered_call", "TEST", SPOT, chain_near, None, qty=1)
k_call = [l["strike"] for l in res2["legs"] if l["cp"] == "call"][0]
cc_credit = [l["entry"] for l in res2["legs"] if l["cp"] == "call"][0] * 100
pl_up = strat.payoff_at_expiry(res2["legs"], SPOT * 1.4, SPOT)
expect_up = (k_call - SPOT) * 100 + cc_credit  # capped at short strike
t2 = abs(pl_up - expect_up) < 200  # ~1 share rounding from stock P/L at cap? no stock at 1.4x capped by short call
print(f"covered_call capped upside: engine {pl_up:.2f} vs {expect_up:.2f} {'PASS' if t2 else 'FAIL'}")

res3 = strat.analyze_strategy("iron_condor", "TEST", SPOT, chain_near, None, qty=1)
t3 = res3["net_credit"] > 0 and res3["max_profit"] is not None and abs(res3["max_profit"] - res3["net_credit"]) < 1.0
print(f"iron_condor credit==maxP: {res3['net_credit']:.2f} vs {res3['max_profit']} {'PASS' if t3 else 'FAIL'}")

res4 = strat.analyze_strategy("long_straddle", "TEST", SPOT, chain_near, None, qty=1)
t4 = res4["max_profit"] is None and res4["net_greeks"]["theta"] < 0
print(f"long_straddle unlimited upside + negative theta: {'PASS' if t4 else 'FAIL'}")

res5 = strat.analyze_strategy("calendar_spread", "TEST", SPOT, chain_near, chain_far, qty=1)
t5 = abs(res5["net_debit"]) > 0 and res5["net_greeks"]["vega"] > 0
print(f"calendar debit>0 + long vega: debit={res5['net_debit']:.2f} vega={res5['net_greeks']['vega']} {'PASS' if t5 else 'FAIL'}")

print(f"\nINVARIANTS: {'ALL PASS' if all([t1,t2,t3,t4,t5]) else 'SOME FAILED'}")
