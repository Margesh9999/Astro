"""
Options Strategy Engine (institutional-grade, educational)
==========================================================
Builds multi-leg option strategies from a live or synthetic chain with
delta-targeted strike selection (the professional convention: e.g. an iron
condor is quoted as "short 16-delta put / call with wings at half the delta"),
then produces the full institutional analysis pack:

  - per-leg entry (mid), IV, greeks
  - net credit/debit, capital at risk, Reg-T style margin estimate
  - expiry payoff curve + max profit/loss + interpolated breakevens
  - probability of profit and expected P/L under the risk-neutral
    lognormal terminal distribution
  - aggregated net greeks (delta / gamma / theta-per-day / vega-per-point)
  - a spot x IV scenario matrix marked-to-model at an exit horizon
  - annualised return-on-risk and premium-capture-per-week metrics

Strategy catalogue spans income, defined-risk spreads and volatility plays:
covered call, cash-secured put / wheel, bull & bear verticals (debit and
credit), iron condor, iron butterfly, long straddle/strangle, calendar,
poor-man's covered call (diagonal), collar and jade lizard.

Educational exploration only - not investment advice.
"""
import logging
import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.services import quant_models as qm

logger = logging.getLogger(__name__)

MULT = 100  # US-style contract multiplier


# =============================================================================
# Catalogue
# =============================================================================
STRATEGY_CATALOG: List[Dict] = [
    {"key": "iron_condor", "name": "Iron Condor", "view": "neutral", "risk": "defined",
     "complexity": "advanced", "income": True,
     "desc": "Short 16Δ put + call spread with wider wings. Collects theta in "
             "range-bound markets; max loss limited to wing width minus credit.",
     "defaults": {"put_delta": 0.16, "call_delta": 0.16, "wing_factor": 0.5}},
    {"key": "iron_butterfly", "name": "Iron Butterfly", "view": "neutral", "risk": "defined",
     "complexity": "advanced", "income": True,
     "desc": "Short ATM straddle + protective wings. Bigger credit and higher POP "
             "than a condor; profits peak if price pins the short strikes.",
     "defaults": {"put_delta": 0.5, "call_delta": 0.5, "wing_pct": 0.05}},
    {"key": "bull_put_spread", "name": "Bull Put Spread (credit)", "view": "bullish", "risk": "defined",
     "complexity": "intermediate", "income": True,
     "desc": "Sell higher-short-put, buy lower long put. Weekly-income staple: "
             "short 30Δ, long roughly half the delta.",
     "defaults": {"put_delta": 0.30, "wing_factor": 0.5}},
    {"key": "bear_call_spread", "name": "Bear Call Spread (credit)", "view": "bearish", "risk": "defined",
     "complexity": "intermediate", "income": True,
     "desc": "Sell call spread above spot. Neutral-to-bearish income; pairs well "
             "with put spreads to synth a condor.",
     "defaults": {"call_delta": 0.30, "wing_factor": 0.5}},
    {"key": "bull_call_spread", "name": "Bull Call Spread (debit)", "view": "bullish", "risk": "defined",
     "complexity": "beginner",
     "desc": "Buy ATM call, sell higher call. Defined-risk directional debit; "
             "cheaper than naked calls, capped upside.",
     "defaults": {"call_delta": 0.50, "wing_pct": 0.05}},
    {"key": "bear_put_spread", "name": "Bear Put Spread (debit)", "view": "bearish", "risk": "defined",
     "complexity": "beginner",
     "desc": "Buy ATM put, sell lower put. Defined-risk downside expression.",
     "defaults": {"put_delta": 0.50, "wing_pct": 0.05}},
    {"key": "cash_secured_put", "name": "Cash-Secured Put / Wheel", "view": "bullish", "risk": "defined",
     "complexity": "beginner", "income": True,
     "desc": "Sell a put fully backed by cash at the strike. If assigned, run the "
             "covered call (the Wheel). The classic income engine.",
     "defaults": {"put_delta": 0.30}},
    {"key": "covered_call", "name": "Covered Call", "view": "bullish", "risk": "undefined",
     "complexity": "beginner", "income": True,
     "desc": "Own 100 shares, sell a 30Δ call against them. Yield overlay on "
             "core holdings; upside capped at short strike.",
     "defaults": {"call_delta": 0.30}},
    {"key": "long_straddle", "name": "Long Straddle", "view": "volatile", "risk": "defined",
     "complexity": "intermediate",
     "desc": "Buy ATM call + put. Pure long-volatility: profits from a big move "
             "either way; bleeds theta daily.",
     "defaults": {}},
    {"key": "long_strangle", "name": "Long Strangle", "view": "volatile", "risk": "defined",
     "complexity": "intermediate",
     "desc": "Buy OTM 25Δ call + put. Cheaper than a straddle, needs a larger move.",
     "defaults": {"put_delta": 0.25, "call_delta": 0.25}},
    {"key": "calendar_spread", "name": "Calendar Spread", "view": "neutral", "risk": "defined",
     "complexity": "advanced", "two_expiries": True,
     "desc": "Sell near-dated ATM option, buy the same strike further out. Harvests "
             "accelerating near-term theta; long vega.",
     "defaults": {}},
    {"key": "pmcc", "name": "Poor Man's Covered Call (diagonal)", "view": "bullish", "risk": "defined",
     "complexity": "advanced", "income": True, "two_expiries": True,
     "desc": "Deep-ITM long call (60Δ, far expiry) financed by short 30Δ calls "
             "near expiry. Leveraged covered-call income at a fraction of the capital.",
     "defaults": {"call_delta_far": 0.60, "call_delta_near": 0.30}},
    {"key": "collar", "name": "Collar (protective)", "view": "bearish_hedge", "risk": "defined",
     "complexity": "intermediate",
     "desc": "Long stock + protective 20Δ put financed by a 20Δ short call. "
             "Institutional downside insurance at low net cost.",
     "defaults": {"put_delta": 0.20, "call_delta": 0.20}},
    {"key": "jade_lizard", "name": "Jade Lizard", "view": "neutral", "risk": "mostly_defined",
     "complexity": "expert", "income": True,
     "desc": "Short 30Δ put + short call spread. Credit collected exceeds the "
             "call-spread width, eliminating upside risk below the wing.",
     "defaults": {"put_delta": 0.30, "call_delta": 0.20, "wing_factor": 0.5}},
]
CATALOG_BY_KEY = {s["key"]: s for s in STRATEGY_CATALOG}


# =============================================================================
# Helpers
# =============================================================================
def _pick(rows: List[dict], cp: str, target_delta: float, spot: float,
          above: Optional[bool] = None) -> dict:
    """Strike whose |delta| is closest to target (from priced rows).

    above=True  -> only strikes > spot; above=False -> only < spot; None -> all.
    """
    cands = [r for r in rows if r[cp]["tradable"] or r[cp]["mid"] > 0]
    if not cands:
        cands = rows
    if above is True:
        c = [r for r in cands if r["strike"] > spot] or cands
    elif above is False:
        c = [r for r in cands if r["strike"] < spot] or cands
    else:
        c = cands
    return min(c, key=lambda r: abs(abs(r[cp]["delta"]) - target_delta))


def _atm(rows: List[dict], spot: float) -> dict:
    return min(rows, key=lambda r: abs(r["strike"] - spot))


def _row(rows: List[dict], cp: str, strike: float) -> dict:
    for r in rows:
        if abs(r["strike"] - strike) < 1e-9:
            return r
    # nearest available strike as fallback
    return min(rows, key=lambda r: abs(r["strike"] - strike))


def _leg(rows: List[dict], action: str, cp: str, strike: float, expiry: str,
         qty: int) -> dict:
    r = _row(rows, cp, strike)
    node = r[cp]
    sign = -1.0 if action == "sell" else 1.0
    return {
        "action": action, "cp": cp, "strike": float(strike), "expiry": expiry,
        "qty": qty, "entry": node["mid"], "bid": node["bid"], "ask": node["ask"],
        "iv": node["iv"], "delta": node["delta"], "gamma": node["gamma"],
        "theta": node["theta"], "vega": node["vega"],
        "signed": sign, "dte": r.get("_dte"),
    }


def _stock_leg(action: str, spot: float, shares: int) -> dict:
    sign = -1.0 if action == "sell" else 1.0
    return {"action": action, "cp": "stock", "strike": float(spot), "expiry": "",
            "qty": shares, "entry": float(spot), "bid": spot, "ask": spot,
            "iv": 0.0, "delta": sign, "gamma": 0.0, "theta": 0.0, "vega": 0.0,
            "signed": sign, "dte": None}


def _intrinsic(cp: str, S: float, K: float) -> float:
    if cp == "call":
        return max(S - K, 0.0)
    if cp == "put":
        return max(K - S, 0.0)
    return S - K  # stock vs entry


def _payoff_limits(legs: List[dict], spot0: float, value_fn) -> Tuple[float, bool, bool]:
    """(P/L at S->0, profit_unbounded_up, loss_unbounded_up).

    Exact boundary analysis. At S->0 every payoff is finite (puts capped at
    their strike). On the upside, the NET signed size of all call legs +
    stock legs decides: positive -> open-ended profit (e.g. long straddle),
    negative -> open-ended loss (e.g. a naked short call), zero -> bounded
    both ways (spreads, covered calls, jade lizards).
    """
    net_up_shares = 0.0
    for lg in legs:
        qty = lg["qty"] if lg["cp"] == "stock" else lg["qty"] * MULT
        if lg["cp"] in ("call", "stock"):
            net_up_shares += lg["signed"] * qty
    pl_zero = value_fn(0.0)
    return pl_zero, net_up_shares > 0, net_up_shares < 0


# =============================================================================
# Leg builders
# =============================================================================
def build_legs(key: str, spot: float, rows: List[dict], expiry: str,
               rows_far: Optional[List[dict]], expiry_far: Optional[str],
               params: Dict, qty: int) -> List[dict]:
    """Delta-targeted leg construction. Returns legs incl. stock legs."""
    p = dict(CATALOG_BY_KEY[key]["defaults"])
    p.update(params or {})
    legs: List[dict] = []

    if key == "iron_condor":
        put = _pick(rows, "put", p["put_delta"], spot, above=False)
        call = _pick(rows, "call", p["call_delta"], spot, above=True)
        wing_p = _pick(rows, "put", p["put_delta"] * p["wing_factor"], spot, above=False)
        wing_c = _pick(rows, "call", p["call_delta"] * p["wing_factor"], spot, above=True)
        # wings strictly beyond the shorts, honouring the half-delta target
        legs += [_leg(rows, "sell", "put", put["strike"], expiry, qty),
                 _leg(rows, "buy", "put", _force_below(rows, "put", put["strike"], wing_p["strike"]), expiry, qty),
                 _leg(rows, "sell", "call", call["strike"], expiry, qty),
                 _leg(rows, "buy", "call", _force_above(rows, "call", call["strike"], wing_c["strike"]), expiry, qty)]

    elif key == "iron_butterfly":
        atmr = _atm(rows, spot)
        k = atmr["strike"]
        wing_p = _pick(rows, "put", 0.10, spot, above=False)
        wing_c = _pick(rows, "call", 0.10, spot, above=True)
        legs += [_leg(rows, "sell", "put", k, expiry, qty),
                 _leg(rows, "sell", "call", k, expiry, qty),
                 _leg(rows, "buy", "put", _force_below(rows, "put", k, wing_p["strike"]), expiry, qty),
                 _leg(rows, "buy", "call", _force_above(rows, "call", k, wing_c["strike"]), expiry, qty)]

    elif key == "bull_put_spread":
        put = _pick(rows, "put", p["put_delta"], spot, above=False)
        wing = _pick(rows, "put", p["put_delta"] * p["wing_factor"], spot, above=False)
        legs += [_leg(rows, "sell", "put", put["strike"], expiry, qty),
                 _leg(rows, "buy", "put", _force_below(rows, "put", put["strike"], wing["strike"]), expiry, qty)]

    elif key == "bear_call_spread":
        call = _pick(rows, "call", p["call_delta"], spot, above=True)
        wing = _pick(rows, "call", p["call_delta"] * p["wing_factor"], spot, above=True)
        legs += [_leg(rows, "sell", "call", call["strike"], expiry, qty),
                 _leg(rows, "buy", "call", _force_above(rows, "call", call["strike"], wing["strike"]), expiry, qty)]

    elif key == "bull_call_spread":
        atm = _atm(rows, spot)
        wing = _pick(rows, "call", 0.15, spot, above=True)
        legs += [_leg(rows, "buy", "call", atm["strike"], expiry, qty),
                 _leg(rows, "sell", "call", _force_above(rows, "call", atm["strike"], wing["strike"]), expiry, qty)]

    elif key == "bear_put_spread":
        atm = _atm(rows, spot)
        wing = _pick(rows, "put", 0.15, spot, above=False)
        legs += [_leg(rows, "buy", "put", atm["strike"], expiry, qty),
                 _leg(rows, "sell", "put", _force_below(rows, "put", atm["strike"], wing["strike"]), expiry, qty)]

    elif key == "cash_secured_put":
        put = _pick(rows, "put", p["put_delta"], spot, above=False)
        legs += [_leg(rows, "sell", "put", put["strike"], expiry, qty)]

    elif key == "covered_call":
        legs += [_stock_leg("buy", spot, MULT * qty),
                 _leg(rows, "sell", "call", _pick(rows, "call", p["call_delta"], spot, above=True)["strike"], expiry, qty)]

    elif key == "long_straddle":
        k = _atm(rows, spot)["strike"]
        legs += [_leg(rows, "buy", "call", k, expiry, qty),
                 _leg(rows, "buy", "put", k, expiry, qty)]

    elif key == "long_strangle":
        legs += [_leg(rows, "buy", "put", _pick(rows, "put", p["put_delta"], spot, above=False)["strike"], expiry, qty),
                 _leg(rows, "buy", "call", _pick(rows, "call", p["call_delta"], spot, above=True)["strike"], expiry, qty)]

    elif key == "calendar_spread":
        k = _atm(rows, spot)["strike"]
        k_far = _atm(rows_far, spot)["strike"]
        legs += [_leg(rows, "sell", "call", k, expiry, qty),
                 _leg(rows_far, "buy", "call", k_far, expiry_far or expiry, qty),
                 _leg(rows, "sell", "put", k, expiry, qty),
                 _leg(rows_far, "buy", "put", k_far, expiry_far or expiry, qty)]

    elif key == "pmcc":
        far = rows_far or rows
        k_long = _pick(far, "call", p["call_delta_far"], spot, above=True)["strike"]
        k_short = _pick(rows, "call", p["call_delta_near"], spot, above=True)["strike"]
        legs += [_leg(far, "buy", "call", k_long, expiry_far or expiry, qty),
                 _leg(rows, "sell", "call", max(k_short, k_long + 1e-9), expiry, qty)]
        legs[1]["strike"] = _force_above(rows, "call", legs[0]["strike"])

    elif key == "collar":
        legs += [_stock_leg("buy", spot, MULT * qty),
                 _leg(rows, "buy", "put", _pick(rows, "put", p["put_delta"], spot, above=False)["strike"], expiry, qty),
                 _leg(rows, "sell", "call", _pick(rows, "call", p["call_delta"], spot, above=True)["strike"], expiry, qty)]

    elif key == "jade_lizard":
        put = _pick(rows, "put", p["put_delta"], spot, above=False)
        call = _pick(rows, "call", p["call_delta"], spot, above=True)
        wing = _pick(rows, "call", p["call_delta"] * p["wing_factor"], spot, above=True)
        legs += [_leg(rows, "sell", "put", put["strike"], expiry, qty),
                 _leg(rows, "sell", "call", call["strike"], expiry, qty),
                 _leg(rows, "buy", "call", _force_above(rows, "call", call["strike"], wing["strike"]), expiry, qty)]
    else:
        raise ValueError(f"Unknown strategy '{key}'")

    # NOTE: per-leg qty already set correctly in _leg / _stock_leg
    # (stock legs carry SHARES, option legs carry CONTRACTS). Never overwrite.
    return legs


def _force_below(rows: List[dict], cp: str, ref: float, candidate: Optional[float] = None) -> float:
    """Nearest strike strictly below ref."""
    below = sorted({r["strike"] for r in rows if r["strike"] < ref - 1e-9})
    if candidate is not None and candidate < ref - 1e-9:
        return float(candidate)
    return float(below[-1]) if below else float(ref - 1)


def _force_above(rows: List[dict], cp: str, ref: float, candidate: Optional[float] = None) -> float:
    above = sorted({r["strike"] for r in rows if r["strike"] > ref + 1e-9})
    if candidate is not None and candidate > ref + 1e-9:
        return float(candidate)
    return float(above[0]) if above else float(ref + 1)


# =============================================================================
# Valuation
# =============================================================================
def _leg_value(leg: dict, S: float, T: float, r: float, q: float,
               iv_shift: float = 0.0) -> float:
    """Model value of one leg at price S, time T (years) - used for scenarios."""
    if leg["cp"] == "stock":
        return S
    S = max(S, 1e-6)  # S->0 boundary: keep BSM's log() in its domain
    iv = max(leg["iv"] + iv_shift, 0.01)
    return qm.bs_price_greeks(S, leg["strike"], T, r, iv, leg["cp"], q)["price"]


def payoff_at_expiry(legs: List[dict], S: float, spot0: float) -> float:
    """P/L at expiry (or at the near-expiry valuation horizon) in account currency.

    Option legs: signed * qty * 100 * (intrinsic - entry premium)
    Stock legs : signed * shares * (S - entry price)
    """
    total = 0.0
    for lg in legs:
        if lg["cp"] == "stock":
            total += lg["signed"] * lg["qty"] * (S - lg["entry"])
        else:
            intr = _intrinsic(lg["cp"], S, lg["strike"])
            total += lg["signed"] * lg["qty"] * MULT * (intr - lg["entry"])
    return total


def mark_to_model(legs: List[dict], S: float, T_by_expiry: Dict[str, float],
                  r: float, q: float, iv_shift: float = 0.0) -> float:
    total = 0.0
    for lg in legs:
        if lg["cp"] == "stock":
            qty = lg["qty"]
            total += lg["signed"] * qty * (S - lg["entry"])
            continue
        T = T_by_expiry.get(lg["expiry"], 0.0)
        qty = lg["qty"] * MULT
        total += lg["signed"] * qty * (_leg_value(lg, S, max(T, 1 / 3650), r, q, iv_shift) - lg["entry"])
    return total


def net_greeks(legs: List[dict]) -> Dict[str, float]:
    agg = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    for lg in legs:
        qty = lg["qty"] if lg["cp"] == "stock" else lg["qty"] * MULT
        for g in agg:
            agg[g] += lg["signed"] * qty * lg[g]
    return {k: round(v, 4) for k, v in agg.items()}


def _lognormal_pdf(S: float, S0: float, T: float, sigma: float, r: float, q: float) -> float:
    if S <= 0 or sigma <= 0 or T <= 0:
        return 0.0
    m = (r - q - 0.5 * sigma * sigma) * T
    s = sigma * math.sqrt(T)
    x = (math.log(S / S0) - m) / s
    return math.exp(-0.5 * x * x) / (S * s * math.sqrt(2 * math.pi))


def pop_and_ev(curve_S: np.ndarray, curve_pl: np.ndarray, S0: float,
               T: float, sigma: float, r: float, q: float) -> Tuple[float, float, float]:
    """Probability of profit, expected P/L, prob of max loss (lognormal grid)."""
    dens = np.array([_lognormal_pdf(s, S0, T, sigma, r, q) for s in curve_S])
    w = dens / max(dens.sum(), 1e-12)
    pop = float(w[curve_pl > 0].sum())
    ev = float((curve_pl * w).sum())
    min_pl = float(curve_pl.min())
    p_max_loss = float(w[curve_pl <= min_pl + 1e-9].sum()) if min_pl < 0 else 0.0
    return pop, ev, p_max_loss


# =============================================================================
# Full analysis
# =============================================================================
def analyze_strategy(key: str, symbol: str, spot: float,
                     chain_near: dict, chain_far: Optional[dict],
                     params: Optional[Dict] = None, qty: int = 1,
                     exit_dte: int = 21) -> Dict:
    r = chain_near.get("risk_free", 0.042)
    q = chain_near.get("div_yield", 0.0)
    expiry = chain_near["expiry"]
    expiry_far = (chain_far or {}).get("expiry")
    rows, rows_far = chain_near["rows"], (chain_far or chain_near)["rows"]
    T_near, T_far = chain_near["dte"] / 365.0, ((chain_far or {}).get("dte", chain_near["dte"])) / 365.0
    atm_vol = chain_near.get("atm_vol", 0.2)

    legs = build_legs(key, spot, rows, expiry, rows_far, expiry_far, params, qty)
    catalog = CATALOG_BY_KEY[key]

    # ---- cash-flow convention: premium RECEIVED is positive ----------------
    opt_legs = [l for l in legs if l["cp"] != "stock"]
    stock_legs = [l for l in legs if l["cp"] == "stock"]
    net_premium_cash = sum(-l["signed"] * l["qty"] * l["entry"] * MULT for l in opt_legs)
    stock_cost = sum(l["qty"] * l["entry"] for l in stock_legs)
    net_credit = net_premium_cash if net_premium_cash > 0 else 0.0
    net_debit = -net_premium_cash if net_premium_cash < 0 else 0.0

    # ---- payoff curve --------------------------------------------------------
    # Single-expiry : intrinsic P/L at expiry.
    # Two expiries  : marked to the NEAR expiry date, long far-dated legs keep
    #                 their remaining time value (the standard calendar/diagonal
    #                 P/L-graph convention).
    lo, hi = spot * 0.60, spot * 1.40
    # inject exact leg strikes so pinned max-profits (butterflies) and
    # breakevens land ON the strike, not a grid step away
    leg_strikes = [lg["strike"] for lg in legs if lg["cp"] != "stock"]
    grid = np.unique(np.concatenate([
        np.linspace(lo, hi, 321),
        np.array([s for s in leg_strikes if lo <= s <= hi], dtype=float),
    ]))
    if expiry_far:
        T_by_exp_curve = {expiry: 0.5 / 3650, expiry_far: max(T_far - T_near, 0.5 / 3650)}
        value_fn = lambda s: mark_to_model(legs, s, T_by_exp_curve, r, q)
    else:
        value_fn = lambda s: payoff_at_expiry(legs, s, spot)
    curve = np.array([value_fn(s) for s in grid])

    pl_zero, up_open, down_open = _payoff_limits(legs, spot, value_fn)
    max_profit = float(curve.max())
    max_loss = float(min(curve.min(), pl_zero))
    if up_open:
        max_profit = float("inf")
    if down_open:
        max_loss = float("-inf")

    # breakevens (linear interpolation at sign changes)
    breakevens = []
    for i in range(len(grid) - 1):
        if (curve[i] <= 0 < curve[i + 1]) or (curve[i] >= 0 > curve[i + 1]):
            t = -curve[i] / (curve[i + 1] - curve[i] + 1e-12)
            breakevens.append(round(float(grid[i] + t * (grid[i + 1] - grid[i])), 2))
    # dedupe
    breakevens = sorted(set(breakevens))

    # ---- POP / EV under risk-neutral lognormal -----------------------------
    sigma_p = max(atm_vol, 0.03)
    T_pop = T_near
    pop, ev, p_max_loss = pop_and_ev(grid, curve, spot, T_pop, sigma_p, r, q)

    # ---- margin / capital ---------------------------------------------------
    if stock_legs and catalog["key"] in ("covered_call", "collar"):
        capital = stock_cost          # full stock notional; credit reduces basis
        margin_basis = "stock_notional"
    elif catalog["key"] == "cash_secured_put":
        capital = sum(l["strike"] * l["qty"] * MULT for l in opt_legs)
        margin_basis = "cash_secured"
    elif net_credit > 0 and catalog["risk"] in ("defined", "mostly_defined") and math.isfinite(max_loss):
        capital = abs(max_loss)
        margin_basis = "max_loss_of_spread"
    elif net_debit > 0:
        capital = net_debit
        margin_basis = "debit_paid"
    else:
        # undefined-risk Reg-T approximation (short options)
        margin = 0.0
        for l in opt_legs:
            if l["signed"] < 0:
                otm = max(l["strike"] - spot, 0) if l["cp"] == "call" else max(spot - l["strike"], 0)
                margin += max(0.20 * spot - otm, 0.10 * spot) * MULT * l["qty"]
        for l in opt_legs:
            if l["signed"] > 0:
                margin -= l["entry"] * MULT * l["qty"]  # long legs offset
        capital = max(margin, 0.10 * spot * MULT)
        margin_basis = "reg_t_approx"

    # ---- income metrics ------------------------------------------------------
    dte = chain_near["dte"]
    weeks = max(dte / 7.0, 0.15)
    premium_per_week = net_credit / weeks if net_credit else 0.0
    theta_per_day = net_greeks(legs)["theta"]   # legs already carry qty
    roc_cycle = (max_profit / capital) if (capital > 0 and math.isfinite(max_profit)) else None
    roc_annual = roc_cycle * (365.0 / dte) if roc_cycle else None

    # ---- scenario matrix at exit horizon ------------------------------------
    exit_dte = max(1, min(int(exit_dte), int(dte) - 1 if dte > 2 else 1))
    T_exit_near = max((dte - exit_dte), 0.5) / 365.0
    T_exit_far = max(((chain_far or {}).get("dte", dte) - exit_dte), 0.5) / 365.0
    T_by_exp = {}
    for lg in legs:
        T_by_exp[lg["expiry"]] = T_exit_far if (expiry_far and lg["expiry"] == expiry_far) else T_exit_near
    spot_shifts = [-10, -5, -2, 0, 2, 5, 10]
    iv_shifts = [-5, -2, 0, 2, 5]
    scenarios = []
    for ss in spot_shifts:
        row = {"spot_pct": ss}
        for ivs in iv_shifts:
            S = spot * (1 + ss / 100.0)
            row[f"iv{ivs:+d}"] = round(mark_to_model(legs, S, T_by_exp, r, q, ivs / 100.0), 2)
        scenarios.append(row)

    curve_pts = [
        {"spot": round(float(s), 2), "pl": round(float(v), 2)}
        for s, v in zip(grid[::4], curve[::4])
    ]

    return {
        "success": True,
        "symbol": symbol,
        "strategy": key,
        "strategy_name": catalog["name"],
        "view": catalog["view"],
        "risk_class": catalog["risk"],
        "complexity": catalog["complexity"],
        "spot": round(spot, 4),
        "currency": chain_near.get("currency", "USD"),
        "expiry": expiry,
        "expiry_far": expiry_far,
        "dte": round(dte, 1),
        "qty": qty,
        "legs": [
            {k: (round(v, 4) if isinstance(v, float) else v) for k, v in l.items() if k != "dte"}
            for l in legs
        ],
        "net_credit": round(net_credit, 2),          # legs carry qty - no re-scaling
        "net_debit": round(net_debit, 2),
        "stock_notional": round(stock_cost, 2),
        "capital_required": round(capital, 2),
        "margin_basis": margin_basis,
        "max_profit": (None if not math.isfinite(max_profit) else round(max_profit, 2)),
        "max_loss": (None if not math.isfinite(max_loss) else round(abs(max_loss), 2)),
        "max_profit_unlimited": bool(up_open),
        "max_loss_unlimited": bool(down_open),
        "breakevens": breakevens,
        "pop": round(pop, 4),
        "prob_max_loss": round(p_max_loss, 4),
        "expected_pl": round(ev, 2),
        "net_greeks": net_greeks(legs),
        "premium_per_week": round(premium_per_week, 2),
        "theta_per_day": round(theta_per_day, 2),
        "roc_cycle": (None if roc_cycle is None else round(roc_cycle, 4)),
        "roc_annualised": (None if roc_annual is None else round(roc_annual, 4)),
        "scenarios": scenarios,
        "payoff_curve": curve_pts,
        "atm_vol": round(atm_vol, 4),
        "chain_source": chain_near.get("source"),
        "exit_dte": exit_dte,
        "disclaimer": "Educational model - BSM marks, no fills/fees/early exercise. Not investment advice.",
    }
