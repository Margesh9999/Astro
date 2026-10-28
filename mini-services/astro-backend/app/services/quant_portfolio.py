"""
Portfolio construction for a small basket around the selected symbol
(Riskfolio-Lib, ffn, pynance, QuantPy, OpenBB `portfolio/po`):
  equal-weight, inverse-volatility, minimum-variance, maximum-Sharpe,
  risk-parity (equal risk contribution) and Hierarchical Risk Parity (HRP),
  plus the efficient frontier and a random-portfolio cloud.
Covariance uses Ledoit-Wolf shrinkage (sklearn). Long-only, fully invested.
"""
from __future__ import annotations

import logging
from typing import Dict, List

import numpy as np
import pandas as pd
from scipy import optimize
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import squareform

from app.services import universe
from app.services.quant_common import clean, insight, naive, r

logger = logging.getLogger(__name__)
ANN = 252

HOME = {
    "US": ["^GSPC", "TLT", "GLD"],
    "UK": ["^FTSE", "IGLT.L", "GLD"],
    "India": ["^NSEI", "GOLDBEES.NS"],
    "Crypto": ["^GSPC", "GLD"],
}
DEFAULT_HOME = ["^GSPC", "TLT", "GLD"]


def pick_basket(symbol: str, max_assets: int = 6) -> List[str]:
    row = universe.get(symbol) or {}
    mk, typ, sec = row.get("market"), row.get("type"), row.get("sector")
    basket = [symbol]
    peers: List[str] = []
    if row:
        cands = [x for x in universe._ROWS if x["symbol"] != symbol and x["market"] == mk and x["type"] == typ]
        same = [x["symbol"] for x in cands if x.get("sector") == sec]
        other = [x["symbol"] for x in cands if x.get("sector") != sec]
        peers = (same + other)[:2]
    for s in peers + HOME.get(mk or "", DEFAULT_HOME):
        if s not in basket:
            basket.append(s)
        if len(basket) >= max_assets:
            break
    return basket


# ── optimisers ───────────────────────────────────────────────────────────────

def _cons(n):
    return ({"type": "eq", "fun": lambda w: w.sum() - 1.0},)


def _bounds(n):
    return [(0.0, 1.0)] * n


def min_variance(cov: np.ndarray) -> np.ndarray:
    n = len(cov)
    res = optimize.minimize(lambda w: w @ cov @ w, np.ones(n) / n, method="SLSQP",
                            bounds=_bounds(n), constraints=_cons(n))
    return _norm(res.x)


def max_sharpe(mu: np.ndarray, cov: np.ndarray, rf: float = 0.0) -> np.ndarray:
    n = len(cov)

    def neg(w):
        v = np.sqrt(w @ cov @ w)
        return -(w @ mu - rf) / v if v > 0 else 0.0
    res = optimize.minimize(neg, np.ones(n) / n, method="SLSQP", bounds=_bounds(n), constraints=_cons(n))
    return _norm(res.x)


def risk_parity(cov: np.ndarray) -> np.ndarray:
    n = len(cov)

    def obj(w):
        pv = w @ cov @ w
        rc = w * (cov @ w) / pv
        return float(((rc - 1.0 / n) ** 2).sum()) * 1e4
    w0 = 1 / np.sqrt(np.diag(cov)); w0 /= w0.sum()
    res = optimize.minimize(obj, w0, method="SLSQP", bounds=[(1e-6, 1.0)] * n, constraints=_cons(n))
    return _norm(res.x)


def hrp(cov: np.ndarray, corr: np.ndarray) -> np.ndarray:
    """López de Prado (2016) Hierarchical Risk Parity."""
    n = len(cov)
    if n == 1:
        return np.ones(1)
    dist = np.sqrt(np.clip((1 - corr) / 2.0, 0, None))
    np.fill_diagonal(dist, 0.0)
    link = linkage(squareform(dist, checks=False), method="single")
    order = list(leaves_list(link))
    w = np.ones(n)
    clusters = [order]
    while clusters:
        nxt = []
        for c in clusters:
            if len(c) < 2:
                continue
            half = len(c) // 2
            c1, c2 = c[:half], c[half:]

            def cvar(ix):
                sub = cov[np.ix_(ix, ix)]
                iv = 1 / np.diag(sub); iv /= iv.sum()
                return iv @ sub @ iv
            v1, v2 = cvar(c1), cvar(c2)
            a = 1 - v1 / (v1 + v2)
            w[c1] *= a
            w[c2] *= 1 - a
            nxt += [c1, c2]
        clusters = nxt
    return _norm(w)


def _norm(w: np.ndarray) -> np.ndarray:
    w = np.clip(np.asarray(w, dtype=float), 0, None)
    w[w < 1e-4] = 0.0
    return w / w.sum() if w.sum() > 0 else np.ones(len(w)) / len(w)


def _stats(w: np.ndarray, mu: np.ndarray, cov: np.ndarray, rets: pd.DataFrame) -> Dict:
    er = float(w @ mu); vol = float(np.sqrt(w @ cov @ w))
    port = rets.to_numpy() @ w
    eq = np.cumprod(1 + port)
    mdd = float((eq / np.maximum.accumulate(eq) - 1).min())
    sd = np.sqrt(np.diag(cov))
    dr = float((w @ sd) / vol) if vol > 0 else 1.0
    rc = w * (cov @ w) / (vol ** 2) if vol > 0 else w
    return {"exp_return_pct": r(er * 100, 2), "vol_pct": r(vol * 100, 2), "sharpe": r(er / vol if vol else 0, 2),
            "max_dd_pct": r(mdd * 100, 1), "diversification_ratio": r(dr, 2),
            "risk_contrib": [r(x * 100, 1) for x in rc]}


def build_portfolio(symbol: str, closes: Dict[str, pd.Series], years: int = 5) -> Dict:
    from sklearn.covariance import LedoitWolf
    px = {}
    for k, s in closes.items():
        try:
            c = naive(pd.DataFrame({"Close": s}))["Close"]
            if len(c) > 260:
                px[k] = c
        except Exception:
            continue
    if symbol not in px:
        return {"success": False, "error": "no price history for the selected symbol"}
    df = pd.DataFrame(px)
    df = df[df.index >= df.index.max() - pd.Timedelta(days=int(years * 365.25))]
    # keep assets with enough overlap, then drop rows with gaps (forward-fill holidays across markets)
    df = df.ffill(limit=3)
    keep = [c for c in df.columns if df[c].notna().mean() > 0.8]
    if symbol not in keep or len(keep) < 3:
        return {"success": False, "error": "not enough overlapping history in the basket"}
    rets = df[keep].pct_change().dropna()
    if len(rets) < 250:
        return {"success": False, "error": "not enough overlapping history in the basket"}
    assets = [symbol] + [k for k in keep if k != symbol]
    rets = rets[assets]
    mu = rets.mean().to_numpy() * ANN
    lw = LedoitWolf().fit(rets.to_numpy())
    cov = lw.covariance_ * ANN
    sd = np.sqrt(np.diag(cov))
    corr = cov / np.outer(sd, sd)
    n = len(assets)

    ports = {
        "Equal weight": np.ones(n) / n,
        "Inverse volatility": _norm(1 / sd),
        "Minimum variance": min_variance(cov),
        "Maximum Sharpe": max_sharpe(mu, cov),
        "Risk parity (ERC)": risk_parity(cov),
        "Hierarchical Risk Parity": hrp(cov, corr),
    }
    single = np.zeros(n); single[0] = 1.0
    alone = _stats(single, mu, cov, rets)
    out_ports = []
    for name, w in ports.items():
        st = _stats(w, mu, cov, rets)
        out_ports.append({"name": name, "weights": [r(x * 100, 1) for x in w], **st})

    # efficient frontier
    wmv = ports["Minimum variance"]
    lo, hi = float(wmv @ mu), float(mu.max())
    frontier = []
    if hi > lo:
        w_prev = wmv
        for t in np.linspace(lo, hi, 22):
            cons = ({"type": "eq", "fun": lambda w: w.sum() - 1.0},
                    {"type": "eq", "fun": lambda w, t=t: w @ mu - t})
            res = optimize.minimize(lambda w: w @ cov @ w, w_prev, method="SLSQP", bounds=_bounds(n), constraints=cons)
            if res.success:
                w_prev = res.x
                frontier.append({"vol": r(np.sqrt(res.x @ cov @ res.x) * 100, 2), "ret": r(t * 100, 2)})
    rng = np.random.default_rng(3)
    W = rng.dirichlet(np.ones(n) * 0.6, size=600)
    cloud = [{"vol": r(np.sqrt(w @ cov @ w) * 100, 2), "ret": r(w @ mu * 100, 2),
              "sharpe": r((w @ mu) / np.sqrt(w @ cov @ w), 2)} for w in W]
    asset_pts = [{"symbol": a, "vol": r(sd[i] * 100, 2), "ret": r(mu[i] * 100, 2)} for i, a in enumerate(assets)]

    names = {a: (universe.get(a) or {}).get("name", a) for a in assets}
    ms = next(p for p in out_ports if p["name"] == "Maximum Sharpe")
    mv = next(p for p in out_ports if p["name"] == "Minimum variance")
    rp = next(p for p in out_ports if p["name"] == "Risk parity (ERC)")
    hr = next(p for p in out_ports if p["name"] == "Hierarchical Risk Parity")
    avg_sym_w = float(np.mean([p["weights"][0] for p in out_ports]))
    best_div = min(range(1, n), key=lambda i: corr[0, i]) if n > 1 else 0

    def topw(p):
        i = int(np.argmax(p["weights"]))
        return f"{assets[i]} {p['weights'][i]:.0f}%"

    advice = (
        f"Every method still gives {symbol} a meaningful slot (avg {avg_sym_w:.0f}%) — it earns its place in a diversified basket."
        if avg_sym_w >= 0.8 * 100 / n else
        f"Most methods give {symbol} less than an equal share (avg {avg_sym_w:.0f}%) — on risk/return grounds it should be a satellite, not a core holding."
    )
    return clean({
        "success": True, "symbol": symbol, "assets": assets, "names": [names[a] for a in assets],
        "window": {"start": str(rets.index[0].date()), "end": str(rets.index[-1].date()), "days": len(rets)},
        "asset_stats": [{"symbol": a, "name": names[a], "ret_pct": r(mu[i] * 100, 2), "vol_pct": r(sd[i] * 100, 2),
                         "sharpe": r(mu[i] / sd[i] if sd[i] else 0, 2)} for i, a in enumerate(assets)],
        "corr": [[r(corr[i, j], 2) for j in range(n)] for i in range(n)],
        "portfolios": out_ports, "alone": alone,
        "frontier": frontier, "cloud": cloud, "asset_points": asset_pts,
        "insight": insight(
            f"Six ways to split money across {', '.join(assets)} using {len(rets):,} days of returns "
            f"({rets.index[0].year}–{rets.index[-1].year}), Ledoit-Wolf shrunk covariance, long-only.",
            f"Holding {symbol} alone: {alone['exp_return_pct']:.1f}%/yr at {alone['vol_pct']:.1f}% vol (max DD {alone['max_dd_pct']:.0f}%). "
            f"Minimum-variance cuts vol to {mv['vol_pct']:.1f}% ({topw(mv)}); max-Sharpe reaches Sharpe {ms['sharpe']:.2f} ({topw(ms)}); "
            f"risk parity balances risk at {rp['vol_pct']:.1f}% vol; HRP gives {symbol} {hr['weights'][0]:.0f}%. "
            f"Best diversifier for {symbol}: {assets[best_div]} (correlation {corr[0, best_div]:+.2f}).",
            advice + " Max-Sharpe relies on noisy historical returns — risk parity and HRP are the more robust choices for real money.",
        ),
        "method": "Long-only, fully invested; past 5 years; covariance Ledoit-Wolf shrinkage; expected returns = historical means "
                  "(noisy — illustrative only, not a recommendation).",
    })
