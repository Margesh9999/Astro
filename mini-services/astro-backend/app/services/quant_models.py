"""
Institutional Quant Models (native numpy/scipy)
===============================================
Formula-level re-implementations of the canonical models popularised by the
open-source quant stack the product pays tribute to:

- ffn                -> performance & risk analytics (Sharpe/Sortino/Calmar...)
- gs-quant           -> VaR / expected-shortfall style risk reporting
- vollib / optlib /
  Q-Fin / FinancePy  -> Black-Scholes & Black-76 greeks, IV solver, CRR tree
- pysabr             -> Hagan's SABR smile expansion
- tf-quant-finance   -> Heston semi-analytic pricing (Lewis 2001, numpy FFT-free)
- Finance-Python     -> antithetic GBM Monte-Carlo engine

No heavyweight dependencies (no TensorFlow / QuantLib C++) - every model is
self-contained, deterministic, and unit-testable. Educational use only.
"""
import logging
import math
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

logger = logging.getLogger(__name__)

SQRT_2PI = math.sqrt(2.0 * math.pi)


def _n(x):
    return norm.cdf(x)


def _npdf(x):
    return math.exp(-0.5 * x * x) / SQRT_2PI


# =============================================================================
# 1. Performance analytics (ffn-inspired)
# =============================================================================
def performance_stats(returns: np.ndarray, periods: int = 252,
                      rf: float = 0.0) -> Dict:
    """ffn-style performance stats from a 1-D array of periodic returns."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 20:
        return {}

    equity = np.cumprod(1.0 + r)
    total_return = float(equity[-1] - 1.0)
    n_years = len(r) / periods
    cagr = float(equity[-1] ** (1.0 / n_years) - 1.0) if n_years > 0 and equity[-1] > 0 else float("nan")

    mu, sd = float(r.mean()), float(r.std(ddof=1))
    ann_vol = sd * math.sqrt(periods)
    ann_ret = mu * periods
    sharpe = (ann_ret - rf) / ann_vol if ann_vol > 0 else float("nan")

    downside = r[r < 0]
    dvol = float(downside.std(ddof=1)) * math.sqrt(periods) if len(downside) > 2 else float("nan")
    sortino = (ann_ret - rf) / dvol if dvol and dvol > 0 else float("nan")

    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    max_dd = float(dd.min())
    calmar = cagr / abs(max_dd) if max_dd < 0 and math.isfinite(cagr) else float("nan")

    # longest drawdown stretch (in periods)
    max_dd_len, cur = 0, 0
    for v in dd:
        cur = cur + 1 if v < 0 else 0
        max_dd_len = max(max_dd_len, cur)

    return {
        "total_return": _round(total_return),
        "cagr": _round(cagr),
        "ann_vol": _round(ann_vol),
        "sharpe": _round(sharpe),
        "sortino": _round(sortino),
        "calmar": _round(calmar),
        "max_drawdown": _round(max_dd),
        "max_dd_length_days": int(max_dd_len),
        "hit_rate": _round(float((r > 0).mean())),
        "best_day": _round(float(r.max())),
        "worst_day": _round(float(r.min())),
        "skew": _round(float(((r - mu) ** 3).mean() / sd ** 3)) if sd > 0 else None,
        "kurtosis": _round(float(((r - mu) ** 4).mean() / sd ** 4) - 3.0) if sd > 0 else None,
    }


def monthly_returns(dates: List[str], returns: np.ndarray) -> Dict:
    """Year x Month compounding matrix (ffn monthly-table style)."""
    r = np.asarray(returns, dtype=float)
    buckets: Dict[Tuple[int, int], float] = {}
    for d, ret in zip(dates, r):
        try:
            y, m = int(d[:4]), int(d[5:7])
        except Exception:
            continue
        buckets[(y, m)] = buckets.get((y, m), 0.0) * (1.0 + float(ret)) + float(ret) * 0  # seed
        buckets[(y, m)] = buckets.get((y, m), 0.0)
    # recompute cleanly (compound within month)
    buckets = {}
    for d, ret in zip(dates, r):
        y, m = int(d[:4]), int(d[5:7])
        prev = buckets.get((y, m), 0.0)
        buckets[(y, m)] = (1.0 + prev) * (1.0 + float(ret)) - 1.0
    years = sorted({k[0] for k in buckets})
    table = []
    for y in years:
        row = {"year": y}
        for m in range(1, 13):
            v = buckets.get((y, m))
            row[f"m{m}"] = _round(v) if v is not None else None
        table.append(row)
    return {"months": table}


def drawdown_series(dates: List[str], returns: np.ndarray, max_points: int = 250) -> List[Dict]:
    r = np.asarray(returns, dtype=float)
    equity = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(np.concatenate([[1.0], equity]))[1:]
    dd = (equity / peak - 1.0) * 100.0
    idx = np.linspace(0, len(dates) - 1, min(len(dates), max_points)).astype(int)
    return [{"date": dates[i], "dd_pct": _round(float(dd[i]))} for i in idx]


# =============================================================================
# 2. Risk analytics (gs-quant / Q-Fin inspired)
# =============================================================================
def var_cvar(returns: np.ndarray, conf: float = 0.95,
             position_value: float = 1_000_000.0) -> Dict:
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 30:
        return {}
    alpha = 1.0 - conf
    var_hist = -float(np.percentile(r, 100 * alpha))
    tail = r[r <= -var_hist]
    cvar_hist = -float(tail.mean()) if len(tail) else var_hist

    mu, sd = float(r.mean()), float(r.std(ddof=1))
    z = norm.ppf(alpha)
    var_par = -(mu + z * sd)  # z < 0 for the left tail
    es_z = _npdf(z) / alpha
    cvar_par = -(mu - sd * es_z)

    return {
        "confidence": conf,
        "var_hist_pct": _round(var_hist), "cvar_hist_pct": _round(cvar_hist),
        "var_param_pct": _round(var_par), "cvar_param_pct": _round(cvar_par),
        "var_hist_usd": _round(var_hist * position_value, 0),
        "cvar_hist_usd": _round(cvar_hist * position_value, 0),
        "position_value": position_value,
        "observations": int(len(r)),
    }


# =============================================================================
# 3. Options pricing (vollib / optlib / Q-Fin / FinancePy inspired)
# =============================================================================
def bs_price_greeks(S: float, K: float, T: float, r: float, sigma: float,
                    cp: str = "call", q: float = 0.0) -> Dict:
    """Black-Scholes-Merton price + first-order greeks (vollib parity)."""
    cp_flag = 1 if cp.lower().startswith("c") else -1
    if T <= 0 or sigma <= 0:
        intrinsic = max(cp_flag * (S - K), 0.0)
        return {"price": _round(intrinsic), "delta": float(cp_flag > 0) if S > K else 0.0,
                "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
    sq = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / sq
    d2 = d1 - sq
    disc_r, disc_q = math.exp(-r * T), math.exp(-q * T)
    if cp_flag == 1:
        price = S * disc_q * _n(d1) - K * disc_r * _n(d2)
        delta = disc_q * _n(d1)
        theta = (-(S * disc_q * _npdf(d1) * sigma) / (2 * math.sqrt(T))
                 - r * K * disc_r * _n(d2) + q * S * disc_q * _n(d1)) / 365.0
        rho = K * T * disc_r * _n(d2) / 100.0
    else:
        price = K * disc_r * _n(-d2) - S * disc_q * _n(-d1)
        delta = -disc_q * _n(-d1)
        theta = (-(S * disc_q * _npdf(d1) * sigma) / (2 * math.sqrt(T))
                 + r * K * disc_r * _n(-d2) - q * S * disc_q * _n(-d1)) / 365.0
        rho = -K * T * disc_r * _n(-d2) / 100.0
    gamma = disc_q * _npdf(d1) / (S * sq)
    vega = S * disc_q * _npdf(d1) * math.sqrt(T) / 100.0
    return {"price": _round(price), "delta": _round(delta), "gamma": _round(gamma, 6),
            "theta": _round(theta), "vega": _round(vega), "rho": _round(rho)}


def black76_price_greeks(F: float, K: float, T: float, r: float, sigma: float,
                         cp: str = "call") -> Dict:
    """Black-76 on futures/forward (index options parity)."""
    cp_flag = 1 if cp.lower().startswith("c") else -1
    sq = sigma * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sigma * sigma * T) / sq
    d2 = d1 - sq
    disc = math.exp(-r * T)
    if cp_flag == 1:
        price = disc * (F * _n(d1) - K * _n(d2))
        delta = disc * _n(d1)
        theta = (-(F * disc * _npdf(d1) * sigma) / (2 * math.sqrt(T))
                 - r * disc * (F * _n(d1) - K * _n(d2))) / 365.0
        rho = -T * disc * (F * _n(d1) - K * _n(d2)) / 100.0
    else:
        price = disc * (K * _n(-d2) - F * _n(-d1))
        delta = -disc * _n(-d1)
        theta = (-(F * disc * _npdf(d1) * sigma) / (2 * math.sqrt(T))
                 + r * disc * (K * _n(-d2) - F * _n(-d1))) / 365.0
        rho = -T * disc * (K * _n(-d2) - F * _n(-d1)) / 100.0
    gamma = disc * _npdf(d1) / (F * sq)
    vega = F * disc * _npdf(d1) * math.sqrt(T) / 100.0
    return {"price": _round(price), "delta": _round(delta), "gamma": _round(gamma, 6),
            "theta": _round(theta), "vega": _round(vega), "rho": _round(rho)}


def implied_vol(price: float, S: float, K: float, T: float, r: float,
                cp: str = "call", q: float = 0.0) -> Optional[float]:
    """Brent-solved BSM implied vol (Q-Fin style)."""
    if price <= 0 or T <= 0 or S <= 0 or K <= 0:
        return None
    f = lambda sig: bs_price_greeks(S, K, T, r, sig, cp, q)["price"] - price
    try:
        lo, hi = 1e-4, 5.0
        if f(lo) * f(hi) > 0:
            return None
        return _round(brentq(f, lo, hi, xtol=1e-6))
    except Exception as exc:
        logger.error("implied_vol: %s", exc)
        return None


def crr_binomial(S: float, K: float, T: float, r: float, sigma: float,
                 cp: str = "call", steps: int = 200, american: bool = True) -> float:
    """Cox-Ross-Rubinstein tree (optlib style) - European & American."""
    cp_flag = 1 if cp.lower().startswith("c") else -1
    dt = T / steps
    u = math.exp(sigma * math.sqrt(dt))
    d = 1.0 / u
    p = (math.exp(r * dt) - d) / (u - d)
    p = min(1.0, max(0.0, p))
    disc = math.exp(-r * dt)

    j = np.arange(steps + 1)
    ST = S * u ** (steps - j) * d ** j
    V = np.maximum(cp_flag * (ST - K), 0.0)
    for i in range(steps - 1, -1, -1):
        V = disc * (p * V[:i + 1] + (1 - p) * V[1:i + 2])
        if american:
            STi = S * u ** (i - np.arange(i + 1)) * d ** np.arange(i + 1)
            V = np.maximum(V, cp_flag * (STi - K))
    return _round(float(V[0]))


def asian_geometric(S: float, K: float, T: float, r: float, sigma: float,
                    cp: str = "call", q: float = 0.0) -> float:
    """Continuous geometric-average Asian (closed form, FinancePy style)."""
    cp_flag = 1 if cp.lower().startswith("c") else -1
    sig_x = sigma / math.sqrt(3.0)
    b_x = r - q + (sigma * sigma - sig_x * sig_x) / 2.0
    d1 = (math.log(S / K) + (b_x + 0.5 * sig_x * sig_x) * T) / (sig_x * math.sqrt(T))
    d2 = d1 - sig_x * math.sqrt(T)
    disc_r = math.exp(-(r - q + b_x - r + q) * T)  # = exp(-r*T) when b_x consistent
    disc_r = math.exp(-r * T)
    if cp_flag == 1:
        price = S * math.exp((b_x - r) * T) * _n(d1) - K * disc_r * _n(d2)
    else:
        price = K * disc_r * _n(-d2) - S * math.exp((b_x - r) * T) * _n(-d1)
    return _round(price)


def mc_gbm_price(S: float, K: float, T: float, r: float, sigma: float,
                 cp: str = "call", n_paths: int = 100_000,
                 seed: int = 42) -> Dict:
    """Antithetic GBM Monte-Carlo (Finance-Python style) with stderr."""
    cp_flag = 1 if cp.lower().startswith("c") else -1
    rng = np.random.default_rng(seed)
    n_half = n_paths // 2
    z = rng.standard_normal(n_half)
    z = np.concatenate([z, -z])          # antithetic variates
    ST = S * np.exp((r - 0.5 * sigma * sigma) * T + sigma * math.sqrt(T) * z)
    payoff = np.maximum(cp_flag * (ST - K), 0.0)
    disc = math.exp(-r * T)
    price = disc * float(payoff.mean())
    stderr = disc * float(payoff.std(ddof=1) / math.sqrt(len(payoff)))
    return {"price": _round(price), "stderr": _round(stderr),
            "paths": int(len(payoff)), "antithetic": True, "seed": seed}


# =============================================================================
# 4. SABR smile (pysabr / Hagan 2002 lognormal expansion)
# =============================================================================
def sabr_vol(F: float, K: float, T: float, alpha: float, beta: float,
             rho: float, nu: float) -> float:
    if F <= 0 or K <= 0 or T <= 0:
        return float("nan")
    logFK = math.log(F / K)
    FK_beta = (F * K) ** ((1.0 - beta) / 2.0)
    A = alpha / (FK_beta * (1.0 + (1.0 - beta) ** 2 / 24.0 * logFK ** 2
                            + (1.0 - beta) ** 4 / 1920.0 * logFK ** 4))
    B1 = ((1.0 - beta) ** 2 / 24.0) * (alpha ** 2 / FK_beta ** 2)
    B2 = 0.25 * rho * beta * nu * alpha / FK_beta
    B3 = (2.0 - 3.0 * rho ** 2) * nu ** 2 / 24.0
    z = nu / alpha * FK_beta * logFK
    xz = math.log((math.sqrt(1.0 - 2.0 * rho * z + z * z) + z - rho) / (1.0 - rho))
    if abs(logFK) < 1e-10:
        return alpha / (F ** (1.0 - beta))
    return A * (1.0 + (B1 + B2 + B3) * T) * (z / xz) if xz != 0 else A


def sabr_smile(F: float, T: float, atm_vol: float, beta: float, rho: float,
               nu: float, moneyness: Optional[List[float]] = None) -> Dict:
    """Smile points from ATM vol (alpha back-solved at K=F)."""
    if moneyness is None:
        moneyness = [0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20]
    alpha = atm_vol * (F ** (1.0 - beta))  # ATM: sigma(atm) = alpha / F^(1-beta)
    points = []
    for m in moneyness:
        K = F * m
        v = sabr_vol(F, K, T, alpha, beta, rho, nu)
        points.append({"moneyness": _round(m), "strike": _round(K),
                       "vol": _round(v)})
    return {"forward": _round(F), "T": T, "atm_vol": _round(atm_vol),
            "beta": beta, "rho": rho, "nu": nu, "alpha": _round(alpha),
            "smile": points}


# =============================================================================
# 5. Heston semi-analytic (Lewis 2001 single-integral, tf-quant-finance analog)
# =============================================================================
def _heston_cf_phi(u: complex, T: float, r: float, q: float,
                   kappa: float, theta: float, sig: float, rho: float,
                   v0: float, S0: float) -> complex:
    x = math.log(S0)
    a = kappa * theta
    u1 = 0.5
    b = kappa - rho * sig * 1j * u
    d = np.sqrt(b * b - sig * sig * (2 * u1 * 1j * u + u * u * (-1)))
    g = (b - d) / (b + d)
    C = (r - q) * 1j * u * T + a / (sig * sig) * ((b - d) * T - 2 * math.log((1 - g * math.exp(-d * T)) / (1 - g)))
    D = (b - d) / (sig * sig) * (1 - math.exp(-d * T)) / (1 - g * math.exp(-d * T))
    return np.exp(C + D * v0 + 1j * u * x)


def heston_call_lewis(S: float, K: float, T: float, r: float, q: float,
                      kappa: float, theta: float, sigma_v: float,
                      rho: float, v0: float) -> float:
    """Heston call via Lewis (2001) Gauss-Legendre integral (pure numpy)."""
    k = math.log(K)

    def integrand(u: float) -> float:
        phi = _heston_cf_phi(complex(u, -0.5), T, r, q, kappa, theta,
                             sigma_v, rho, v0, S)
        fk = np.exp(complex(0, u) * (-k)) * phi / (u * u - 1j * u)
        return float(np.real(fk))

    nodes, weights = np.polynomial.legendre.leggauss(200)
    us = 0.5 * 400.0 * (nodes + 1.0)     # (0, 400)
    ws = 0.5 * 400.0 * weights
    total = sum(w * integrand(u) for u, w in zip(us, ws))
    price = S * math.exp(-q * T) - math.sqrt(S * K) * math.exp(-r * T) / math.pi * total
    return _round(max(price, 0.0))


# =============================================================================
# 6. Bond analytics (pyql / FinancePy inspired)
# =============================================================================
def bond_analytics(face: float, coupon_rate: float, ytm: float, years: float,
                   freq: int = 2) -> Dict:
    """Price, duration, convexity for a level-coupon bond."""
    n = int(round(years * freq))
    c = coupon_rate / freq * face
    y = ytm / freq
    dfs = np.array([(1.0 + y) ** -(i + 1) for i in range(n)])
    cfs = np.array([c] * n)
    cfs[-1] += face
    price = float(np.sum(cfs * dfs))
    t = np.arange(1, n + 1) / freq
    macaulay = float(np.sum(t * cfs * dfs) / price)
    modified = macaulay / (1.0 + ytm / freq)
    convexity = float(np.sum(t * (t + 1.0 / freq) * cfs * (1.0 + y) ** -(t * freq + 2.0)) / price)
    return {"price": _round(price, 2), "macaulay_duration": _round(macaulay, 3),
            "modified_duration": _round(modified, 3), "convexity": _round(convexity, 3),
            "cashflows": n}


def bond_ytm(price: float, face: float, coupon_rate: float, years: float,
             freq: int = 2) -> Optional[float]:
    n = int(round(years * freq))
    c = coupon_rate / freq * face

    def f(y):
        dfs = (1.0 + y) ** -np.arange(1, n + 1)
        cfs = np.array([c] * n, dtype=float)
        cfs[-1] += face
        return float(np.sum(cfs * dfs)) - price

    try:
        return _round(brentq(f, 1e-9, 1.0, xtol=1e-8) * freq)
    except Exception:
        return None


def _round(x, nd=4):
    v = float(x)
    if not np.isfinite(v):
        return None
    return round(v, nd)
