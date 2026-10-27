"""
Weekly Income Planner
=====================
Answers the practical question: "what capital, in which strategies, does it
realistically take to generate about GBP 500 per week of option premium?"

Method (deliberately honest, no get-rich-quick math):
  1. Archetypes: the five mainstream premium-selling programs with annualised
     yield-on-capital RANGES (conservative / base / aggressive) that are
     achievable with disciplined management (45 DTE entries, 50% profit
     takers, 2x-loss stops) in normal-to-elevated IV regimes. The raw
     "max-loss ratio" of credit spreads is NOT used as yield - that is the
     classic retail trap.
  2. Required capital = annual target / yield, shown for all three regimes.
  3. Ladder: a balanced allocation across the archetypes with example tickets
     priced from the LIVE option chain where available (else BSM model
     tickets on the synthetic chain, clearly labelled).
  4. If capital falls short, the planner reports the maximum SUSTAINABLE
     weekly income instead of promising the target.

Educational use only - not investment advice. Options selling involves
substantial risk of loss.
"""
import logging
import math
from typing import Dict, List, Optional

from app.services import quant_models as qm
from app.services.option_data import OptionDataService
from app.services.universe import currency_of

logger = logging.getLogger(__name__)

# yield-on-capital ranges (annualised, managed) per archetype
ARCHETYPES = [
    {"key": "csp_wheel", "label": "Cash-Secured Puts / Wheel",
     "basis": "cash_secured", "yield": (0.08, 0.15, 0.22),
     "dte": "30-45", "risk": "Assignment risk; stock drawdown",
     "underlyings": ["AAPL", "MSFT", "SPY", "COST"]},
    {"key": "put_credit_spread", "label": "Put Credit Spreads (30-45 DTE)",
     "basis": "max_loss", "yield": (0.15, 0.28, 0.40),
     "dte": "30-45", "risk": "Gap risk through the long strike",
     "underlyings": ["SPY", "QQQ", "IWM"]},
    {"key": "iron_condor", "label": "Iron Condors (45 DTE, 16-delta)",
     "basis": "max_loss", "yield": (0.12, 0.22, 0.32),
     "dte": "30-45", "risk": "Vol expansion; pin risk at wings",
     "underlyings": ["SPY", "QQQ", "IWM"]},
    {"key": "covered_call", "label": "Covered Calls on Core Holdings",
     "basis": "stock_notional", "yield": (0.06, 0.11, 0.16),
     "dte": "30-45", "risk": "Full stock ownership + capped upside",
     "underlyings": ["AAPL", "MSFT", "TSLA"]},
    {"key": "nifty_weekly", "label": "Nifty Weekly Premium Selling (India)",
     "basis": "margin_span", "yield": (0.18, 0.32, 0.48),
     "dte": "5-9", "risk": "Weekly expiry gamma; SEBI lot margins; event gaps",
     "underlyings": ["^NSEI", "BANKBEES.NS"], "markets": ["India"]},
]

LADDER = [  # balanced income programme
    {"key": "csp_wheel", "weight": 0.40},
    {"key": "put_credit_spread", "weight": 0.35},
    {"key": "iron_condor", "weight": 0.15},
    {"key": "covered_call", "weight": 0.10},
]

FALLBACK_GBPUSD = 1.27


class IncomePlanner:
    def __init__(self, option_service: OptionDataService, market_service):
        self.opts = option_service
        self.market = market_service

    # ------------------------------------------------------------------
    def gbpusd(self) -> float:
        try:
            px = self.market.get_real_time_price("GBPUSD=X")
            if px and 0.8 < px < 1.8:
                return float(px)
        except Exception:
            pass
        return FALLBACK_GBPUSD

    # ------------------------------------------------------------------
    def _capital_for(self, annual_target: float, arch: dict) -> Dict[str, float]:
        """Conservative plan = LOW yield assumption -> MORE capital needed."""
        lo, base, hi = arch["yield"]
        inv = lambda y: round(annual_target / y) if y > 0 else None
        return {"conservative": inv(lo), "base": inv(base), "aggressive": inv(hi)}

    # ------------------------------------------------------------------
    def _ticket(self, arch: dict, allocation_gbp: float, fx: float) -> Optional[dict]:
        """One concrete example ticket for a ladder bucket (live if possible).

        The ticket is a SIZING/RISK illustration: it shows the real strikes,
        credit, margin, POP and how many units fit the bucket allocation.
        It is NOT an income promise - premium capture != expected profit.
        """
        unds = arch["underlyings"]
        for und in unds:
            try:
                tccy = currency_of(und)
                if tccy == "USD":
                    alloc_ccy = allocation_gbp * fx
                elif tccy == "INR":
                    alloc_ccy = allocation_gbp * fx * 86.0
                else:
                    alloc_ccy = allocation_gbp
                exps = self.opts.expirations(und)
                spot = exps.get("spot")
                if not spot:
                    continue
                # pick expiry closest to archetype DTE window
                want = {"csp_wheel": 38, "put_credit_spread": 38, "iron_condor": 42,
                        "covered_call": 38, "nifty_weekly": 7}[arch["key"]]
                dates = exps["expirations"]
                dtes = exps.get("dte") or [None] * len(dates)
                best = min(range(len(dates)),
                           key=lambda i: abs((dtes[i] or want) - want))
                expiry, dte = dates[best], (dtes[best] or want)
                chain = self.opts.chain(und, expiry)
                spot = chain["spot"]

                from app.services import option_strategies as strat
                if arch["key"] in ("csp_wheel", "covered_call", "nifty_weekly"):
                    key = {"csp_wheel": "cash_secured_put",
                           "covered_call": "covered_call",
                           "nifty_weekly": "bull_put_spread"}[arch["key"]]
                    if arch["key"] == "nifty_weekly":
                        params = {"put_delta": 0.20, "wing_factor": 0.5}
                    else:
                        params = {"put_delta": 0.30}
                elif arch["key"] == "put_credit_spread":
                    key, params = "bull_put_spread", {"put_delta": 0.30, "wing_factor": 0.5}
                else:
                    key, params = "iron_condor", {}

                qty = 1
                res = strat.analyze_strategy(key, und, spot, chain, None,
                                             params=params, qty=qty,
                                             exit_dte=max(1, int(dte * 0.5)))
                margin_unit = res["capital_required"]
                if margin_unit <= 0:
                    continue
                n = int(alloc_ccy // margin_unit)
                fits = n >= 1
                n = max(1, n)   # always show a 1-unit ticket for small accounts
                res_n = strat.analyze_strategy(key, und, spot, chain, None,
                                               params=params, qty=n,
                                               exit_dte=max(1, int(dte * 0.5)))
                weeks = max(dte / 7.0, 0.15)
                capture = 0.5  # classic 50%-of-max-profit management
                return {
                    "underlying": und,
                    "strategy": key,
                    "strategy_name": res_n["strategy_name"],
                    "expiry": expiry,
                    "dte": dte,
                    "qty": n,
                    "fits_allocation": fits,
                    "legs": [
                        {"action": l["action"], "cp": l["cp"],
                         "strike": l["strike"], "entry": l["entry"]}
                        for l in res_n["legs"] if l["cp"] != "stock"
                    ][:4] + ([{"action": "buy", "cp": "stock",
                              "strike": res_n["legs"][0]["entry"],
                              "entry": res_n["legs"][0]["entry"]}]
                             if any(l["cp"] == "stock" for l in res_n["legs"]) else []),
                    "net_credit": res_n["net_credit"],
                    "credit_per_unit": round(res["net_credit"], 2),
                    "margin_per_unit": round(margin_unit, 2),
                    "capital_required": res_n["capital_required"],
                    "gross_premium_capture_weekly": round(
                        res_n["net_credit"] * capture / weeks, 2),
                    "weekly_premium": round(res_n["premium_per_week"], 2),
                    "pop": res_n["pop"],
                    "max_loss": res_n["max_loss"],
                    "currency": chain["currency"],
                    "chain_source": chain["source"],
                    "note": ("Gross premium rate at 50% management - NOT expected "
                             "profit. Max loss is per full cycle; sustainable "
                             "yield comes from the archetype table."),
                }
            except Exception as exc:
                logger.warning("income ticket %s/%s failed: %s", arch["key"], und, exc)
                continue
        return None

    # ------------------------------------------------------------------
    def plan(self, capital: float, target_weekly: float = 500.0,
             focus: str = "global", qty_hint: int = 1) -> dict:
        capital = max(float(capital or 0), 0)
        target_weekly = max(float(target_weekly or 0), 0)
        annual_target = target_weekly * 52
        fx = self.gbpusd()

        archs = [a for a in ARCHETYPES
                 if focus != "India" or a.get("markets") == ["India"]]
        if focus == "India" and not archs:
            archs = ARCHETYPES

        # 1. required capital table
        table = []
        for a in archs:
            table.append({
                "key": a["key"], "label": a["label"], "basis": a["basis"],
                "dte": a["dte"], "risk": a["risk"],
                "yield_range": {"conservative": a["yield"][0],
                                "base": a["yield"][1],
                                "aggressive": a["yield"][2]},
                "capital_required": self._capital_for(annual_target, a),
            })

        # 2. ladder with live/model tickets
        ladder = []
        est_weekly_total = 0.0
        capital_used = 0.0
        for b in LADDER:
            a = next((x for x in ARCHETYPES if x["key"] == b["key"]), None)
            if not a or (focus == "India" and a.get("markets") != ["India"]):
                continue
            allocation = capital * b["weight"]
            # expected weekly income for this bucket at BASE yield
            wk = allocation * a["yield"][1] / 52.0
            est_weekly_total += wk
            capital_used += allocation
            ticket = self._ticket(a, allocation, fx)
            ladder.append({
                "key": a["key"], "label": a["label"], "weight": b["weight"],
                "allocation": round(allocation, 0),
                "target_weekly": round(wk, 2),
                "yield_base": a["yield"][1],
                "ticket": ticket,
            })

        # 3. verdicts
        base_req_by_key = {t["key"]: t["capital_required"]["base"] for t in table}
        total_base_required = round(sum(
            base_req_by_key[b["key"]] * b["weight"] for b in LADDER
            if b["key"] in base_req_by_key))
        achievable = capital >= total_base_required * 0.95
        blended = sum(
            b["weight"] * a["yield"][1] for b in LADDER
            for a in ARCHETYPES if a["key"] == b["key"])
        max_sustainable_weekly = round(capital * blended / 52.0, 2)

        # estimated gross premium capture from the actual ladder tickets (live
        # data, 50% managed) - ILLUSTRATIVE, not expected profit
        capture_weekly = sum(
            (b["ticket"].get("gross_premium_capture_weekly") or 0) *
            _to_gbp(b["ticket"]["currency"], fx)
            for b in ladder if b.get("ticket"))

        notes = [
            "Yield ranges assume disciplined management: 30-45 DTE entries, "
            "close at 50% max profit, stop at 2x credit, size each position "
            "<= 5% of capital.",
            "Credit-spread 'return on margin' is NOT annual yield - the margin "
            "IS the max loss; expected value turns negative without management.",
            "Weekly income is a statistical average: some weeks will be "
            "negative when stops are hit. Sequence risk matters.",
            "US-listed options are the most capital-efficient; UK single-stock "
            "options are illiquid - UK traders typically use US ETFs (SPY/QQQ) "
            "or LSE ETFs without options for the wheel.",
            "India: SEBI's physical delivery + lot-size rules mean Nifty "
            "weekly selling needs roughly INR 1.5-2L margin per lot even for "
            "spreads.",
            "Not investment advice. Selling options carries substantial risk "
            "of loss; past yield ranges are not guarantees.",
        ]

        return {
            "success": True,
            "inputs": {"capital": capital, "currency": "GBP",
                       "target_weekly": target_weekly, "focus": focus,
                       "gbpusd": round(fx, 4)},
            "annual_target": round(annual_target, 0),
            "verdict": ("achievable" if achievable else
                        "stretch" if capital >= total_base_required * 0.6 else
                        "below_base_regime"),
            "required_capital_total_base": total_base_required,
            "capital_table": table,
            "ladder": ladder,
            "est_weekly_from_ladder_yields": round(est_weekly_total, 2),
            "gross_premium_capture_weekly_gbp": round(capture_weekly, 2),
            "gross_premium_capture_note": ("Live-ticket premium at 50% management - "
                                           "illustrative gross rate, NOT expected profit "
                                           "(losers, gaps and IV regimes reduce it to "
                                           "the archetype yields above)."),
            "max_sustainable_weekly": max_sustainable_weekly,
            "notes": notes,
            "disclaimer": "Educational planning tool only - not investment advice.",
        }


def _to_gbp(currency: str, gbpusd: float) -> float:
    if currency == "GBP":
        return 1.0
    if currency == "USD":
        return 1.0 / gbpusd
    if currency == "INR":
        return 1.0 / (gbpusd * 86.0)
    return 1.0
