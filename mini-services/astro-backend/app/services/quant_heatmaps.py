"""
Quant Desk heatmaps (ffn monthly table, sunday-quant-scientist seasonality,
OpenBB `qa`/`ca` correlation views):
  * year × month returns (full history, with annual column)
  * day-of-week × month seasonality
  * year × month realised volatility
  * return-distribution by year
  * rolling (quarterly) correlation vs major cross-asset benchmarks + 1y matrix
Every block carries a dynamic plain-English insight.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

from app.services.quant_common import BENCH_NAMES, clean, insight, naive, r

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DOWS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
DOW_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
BINS = [-np.inf, -0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03, np.inf]
BIN_LABELS = ["< -3%", "-3…-2%", "-2…-1%", "-1…0%", "0…1%", "1…2%", "2…3%", "> 3%"]


def _monthly(close: pd.Series) -> Dict:
    m = close.resample("ME").last()
    mret = m.pct_change() * 100
    y = close.resample("YE").last().pct_change() * 100
    df = pd.DataFrame({"y": mret.index.year, "m": mret.index.month, "v": mret.values}).dropna()
    piv = df.pivot_table(index="y", columns="m", values="v", aggfunc="sum").reindex(columns=range(1, 13))
    years = [int(v) for v in piv.index]
    annual = {int(i.year): float(v) for i, v in y.dropna().items()}
    # first (partial) year: compound the months we have
    for yr in years:
        if yr not in annual:
            vals = piv.loc[yr].dropna() / 100
            annual[yr] = float(((1 + vals).prod() - 1) * 100)
    pos = (df.assign(p=df["v"] > 0).groupby("m")["p"].mean() * 100).reindex(range(1, 13))
    avg = df.groupby("m")["v"].mean().reindex(range(1, 13))
    best_m, worst_m = int(avg.idxmax()), int(avg.idxmin())
    up_years = sum(1 for v in annual.values() if v > 0)
    cur_m = int(close.index[-1].month)
    nxt = cur_m % 12 + 1
    return {
        "years": years, "months": MONTHS,
        "values": [[r(piv.loc[yy, mm], 2) for mm in range(1, 13)] for yy in years],
        "annual": [r(annual.get(yy), 1) for yy in years],
        "avg": [r(v, 2) for v in avg], "pct_positive": [r(v, 0) for v in pos],
        "insight": insight(
            f"Every calendar month since {years[0]} ({len(years)} years) — green up, red down; last column is the full year.",
            f"{MONTHS[best_m-1]} is the best month on average ({avg[best_m]:+.2f}%, up {pos[best_m]:.0f}% of the time) and "
            f"{MONTHS[worst_m-1]} the worst ({avg[worst_m]:+.2f}%). {up_years} of {len(annual)} years finished positive.",
            f"Next month is {MONTHS[nxt-1]}: historically {avg[nxt]:+.2f}% on average and positive {pos[nxt]:.0f}% of the time — "
            + ("a seasonal tailwind; lean into planned buys." if avg[nxt] > avg.mean() and pos[nxt] >= 55 else
               "a seasonal headwind; stagger entries and keep some cash for a better price." if avg[nxt] < 0 or pos[nxt] < 50 else
               "seasonally ordinary; let trend and signals decide.")),
    }


def _dow_month(ret: pd.Series) -> Dict:
    df = pd.DataFrame({"r": ret * 100, "dow": ret.index.day_of_week, "m": ret.index.month})
    df = df[df["dow"] < 5]
    avg = df.pivot_table(index="dow", columns="m", values="r", aggfunc="mean").reindex(index=range(5), columns=range(1, 13))
    hit = df.assign(p=df["r"] > 0).pivot_table(index="dow", columns="m", values="p", aggfunc="mean").reindex(index=range(5), columns=range(1, 13)) * 100
    cnt = df.pivot_table(index="dow", columns="m", values="r", aggfunc="count").reindex(index=range(5), columns=range(1, 13))
    by_dow = df.groupby("dow")["r"].agg(["mean", "std", "count"]).reindex(range(5))
    t = by_dow["mean"] / (by_dow["std"] / np.sqrt(by_dow["count"]))
    best_d, worst_d = int(by_dow["mean"].idxmax()), int(by_dow["mean"].idxmin())
    stack = avg.stack()
    (bd, bm), (wd, wm) = stack.idxmax(), stack.idxmin()
    sig = bool(abs(t[best_d]) > 2 or abs(t[worst_d]) > 2)
    return {
        "rows": DOWS, "cols": MONTHS,
        "values": [[r(avg.loc[d, m], 3) for m in range(1, 13)] for d in range(5)],
        "hit": [[r(hit.loc[d, m], 0) for m in range(1, 13)] for d in range(5)],
        "count": [[int(cnt.loc[d, m]) if not np.isnan(cnt.loc[d, m]) else 0 for m in range(1, 13)] for d in range(5)],
        "by_dow": [r(v, 3) for v in by_dow["mean"]], "t_stat": [r(v, 2) for v in t],
        "insight": insight(
            "Average daily return for every weekday-in-month combination across the full history.",
            f"{DOW_FULL[best_d]} is the strongest weekday ({by_dow['mean'][best_d]:+.3f}%/day) and {DOW_FULL[worst_d]} the weakest "
            f"({by_dow['mean'][worst_d]:+.3f}%). Best cell: {DOW_FULL[bd]}s in {MONTHS[bm-1]} ({stack.max():+.3f}%); worst: {DOW_FULL[wd]}s in {MONTHS[wm-1]} "
            f"({stack.min():+.3f}%). " + ("The weekday gap is statistically significant (|t| > 2)." if sig else
                                          "The weekday differences are NOT statistically significant (|t| < 2) — mostly noise."),
            (f"If you are buying anyway, place orders on {DOW_FULL[worst_d]}s and trim on {DOW_FULL[best_d]}s — a small, free edge."
             if sig else "Don't build a strategy on weekday effects here; at most use them to time an order you were already placing."),
        ),
    }


def _vol_heat(ret: pd.Series) -> Dict:
    df = pd.DataFrame({"r": ret, "y": ret.index.year, "m": ret.index.month})
    v = df.groupby(["y", "m"])["r"].std().unstack() * np.sqrt(252) * 100
    v = v.reindex(columns=range(1, 13))
    years = [int(y) for y in v.index]
    mavg = v.mean()
    hi_m, lo_m = int(mavg.idxmax()), int(mavg.idxmin())
    yv = df.groupby("y")["r"].std() * np.sqrt(252) * 100
    cur = float(v.iloc[-1].dropna().iloc[-1]) if v.iloc[-1].notna().any() else float("nan")
    med = float(np.nanmedian(v.to_numpy()))
    return {
        "years": years, "months": MONTHS,
        "values": [[r(v.loc[y, m], 1) for m in range(1, 13)] for y in years],
        "median": r(med, 1),
        "insight": insight(
            "Annualised volatility of daily returns inside each month — darker = wilder month.",
            f"{MONTHS[hi_m-1]} is the most volatile month on average ({mavg[hi_m]:.0f}%), {MONTHS[lo_m-1]} the calmest ({mavg[lo_m]:.0f}%). "
            f"Calmest year {int(yv.idxmin())} ({yv.min():.0f}%), wildest {int(yv.idxmax())} ({yv.max():.0f}%). "
            f"This month so far: {cur:.0f}% vs a typical {med:.0f}%.",
            ("Volatility is running hot — halve position sizes or use defined-risk option structures until it cools."
             if cur > med * 1.4 else
             "Volatility is unusually calm — cheap time to buy protection; premium sellers get paid less."
             if cur < med * 0.7 else
             "Volatility is normal — standard position sizes apply."),
        ),
    }


def _dist_by_year(ret: pd.Series, max_years: int = 40) -> Dict:
    cat = pd.cut(ret, BINS, labels=BIN_LABELS)
    tab = pd.crosstab(ret.index.year, cat, normalize="index") * 100
    tab = tab.reindex(columns=BIN_LABELS).fillna(0.0).tail(max_years)
    years = [int(y) for y in tab.index]
    tails = tab["< -3%"] + tab["> 3%"]
    flat = tab["-1…0%"] + tab["0…1%"]
    recent = float(tails.tail(1).iloc[0]); typical = float(tails.median())
    return {
        "years": years, "bins": BIN_LABELS,
        "values": [[r(tab.loc[y, b], 1) for b in BIN_LABELS] for y in years],
        "insight": insight(
            "For each year, the share of trading days that fell in each daily-return bucket (rows sum to 100%).",
            f"In a typical year {float(flat.median()):.0f}% of days move less than ±1% and {typical:.1f}% are ±3% shocks. "
            f"{years[-1]} so far has {recent:.1f}% shock days; the most turbulent year was {int(tails.idxmax())} "
            f"({tails.max():.1f}% of days beyond ±3%).",
            ("This year is far more jumpy than usual — use wider stops and smaller size; gaps through stops are likely."
             if recent > typical * 2 + 0.5 else
             "This year's day-to-day behaviour is within normal bounds — usual stop distances are fine."),
        ),
    }


def _correlations(close: pd.Series, symbol: str, bench: Dict[str, pd.Series]) -> Optional[Dict]:
    if not bench:
        return None
    rets = {symbol: close.pct_change()}
    for k, s in bench.items():
        if k == symbol:
            continue
        rets[k] = s.pct_change()
    df = pd.DataFrame(rets).dropna(how="all")
    df = df[df.index >= df.index.max() - pd.Timedelta(days=3 * 365 + 120)]
    df = df.dropna(subset=[symbol])
    names = [k for k in df.columns if k != symbol and df[k].notna().sum() > 120]
    if not names:
        return None
    # quarterly rolling 63-day correlation
    qends = pd.date_range(df.index.min() + pd.Timedelta(days=95), df.index.max(), freq="QE")
    labels, cols = [], []
    for qe in list(qends[-12:]):
        win = df[(df.index > qe - pd.Timedelta(days=92)) & (df.index <= qe)]
        labels.append(f"{qe.year % 100:02d}Q{(qe.month - 1) // 3 + 1}")
        cols.append({k: win[symbol].corr(win[k]) if win[[symbol, k]].dropna().shape[0] > 30 else np.nan for k in names})
    last = df[df.index > df.index.max() - pd.Timedelta(days=92)]
    labels.append("Now 3m")
    cols.append({k: last[symbol].corr(last[k]) if last[[symbol, k]].dropna().shape[0] > 30 else np.nan for k in names})
    rows = [{"symbol": k, "name": BENCH_NAMES.get(k, k),
             "values": [r(c[k], 2) for c in cols]} for k in names]
    yr = df[df.index > df.index.max() - pd.Timedelta(days=365)]
    mat_syms = [symbol] + names
    cm = yr[mat_syms].corr(min_periods=60)
    matrix = {"symbols": mat_syms, "names": [BENCH_NAMES.get(s, "THIS") if s != symbol else symbol for s in mat_syms],
              "values": [[r(cm.loc[a, b], 2) for b in mat_syms] for a in mat_syms]}
    now = {k: cols[-1][k] for k in names if not np.isnan(cols[-1][k])}
    year_ago = {k: np.nanmean([c[k] for c in cols[-5:-3]]) for k in names}
    if not now:
        return None
    hi = max(now, key=lambda k: now[k]); lo = min(now, key=lambda k: now[k])
    drift = sorted(((now[k] - year_ago[k], k) for k in now if not np.isnan(year_ago[k])), reverse=True)
    hedges = [BENCH_NAMES.get(k, k) for k in now if now[k] < -0.2]
    mv = ""
    if drift:
        d_up, k_up = drift[0]
        mv = f" Biggest change: correlation with {BENCH_NAMES.get(k_up, k_up)} moved {d_up:+.2f} vs a year ago."
    return {
        "periods": labels, "rows": rows, "matrix": matrix,
        "insight": insight(
            "Correlation of daily returns with major indices, gold, oil, VIX, the US 10-year yield and GBP/USD — "
            "one cell per quarter (63-day window), plus the latest 3 months.",
            f"{symbol} moves most with {BENCH_NAMES.get(hi, hi)} ({now[hi]:+.2f}) and most against {BENCH_NAMES.get(lo, lo)} "
            f"({now[lo]:+.2f}).{mv}",
            (f"Natural hedges right now: {', '.join(hedges)} (negative correlation) — a small allocation dampens swings."
             if hedges else
             f"No asset in the set is currently a meaningful hedge; diversify with the lowest-correlation one ({BENCH_NAMES.get(lo, lo)}) "
             "or use options for protection."),
        ),
    }


def build_heatmaps(df: pd.DataFrame, symbol: str, bench: Optional[Dict[str, pd.Series]] = None) -> Dict:
    d = naive(df)
    if len(d) < 260:
        return {"success": False, "error": "need at least ~1 year of daily history"}
    close = d["Close"]
    ret = close.pct_change().dropna()
    bench_n = {}
    for k, s in (bench or {}).items():
        try:
            bench_n[k] = naive(pd.DataFrame({"Close": s}))["Close"]
        except Exception:
            continue
    out = {
        "success": True, "symbol": symbol, "start": str(d.index[0].date()),
        "monthly": _monthly(close),
        "dow_month": _dow_month(ret),
        "vol_month": _vol_heat(ret),
        "dist_year": _dist_by_year(ret),
        "correlation": _correlations(close, symbol, bench_n),
        "benchmarks_loaded": sorted(bench_n.keys()),
        "benchmarks_missing": sorted(k for k in BENCH_NAMES if k not in bench_n and k != symbol),
    }
    return clean(out)
