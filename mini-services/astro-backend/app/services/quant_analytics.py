"""
Quant Desk analytics — trend charts, heatmaps and a plain-English
interpretation line under EVERY chart (T1: "each chart with a simple,
easy-to-understand actionable interpretation").
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


def _interpret_trend(df: pd.DataFrame, last: pd.Series) -> str:
    price = float(last["Close"])
    sma50 = float(df["Close"].rolling(50).mean().iloc[-1]) if len(df) >= 50 else price
    sma200 = float(df["Close"].rolling(200).mean().iloc[-1]) if len(df) >= 200 else price
    if price > sma50 > sma200:
        return ("Strong uptrend — price is above both its 50- and 200-day averages. "
                "Actionable: stay long or buy dips toward the 50-day line; avoid shorting strength.")
    if price < sma50 < sma200:
        return ("Established downtrend — price sits below both key averages. "
                "Actionable: prefer waiting or hedged income (credit spreads) over bottom-fishing.")
    if price > sma200:
        return ("Mixed but constructive — price is above the 200-day average yet below the 50-day. "
                "Actionable: reduce size, buy only if price reclaims the 50-day average.")
    return ("Mixed and weak — price is under the 200-day average. "
            "Actionable: keep cash ready; confirmation comes only when price closes back above the 200-day line.")


def _interpret_drawdown(cur_dd: float, max_dd: float) -> str:
    if cur_dd > -3:
        return (f"Current drawdown is just {cur_dd:.1f}% — the trend is intact. "
                f"Actionable: normal position sizing is fine; the worst historical peak-to-trough was {max_dd:.1f}%.")
    if cur_dd > -10:
        return (f"A {abs(cur_dd):.1f}% pullback is underway (historical worst {max_dd:.1f}%). "
                "Actionable: this is the zone where patient buyers usually get paid — scale in across 2–3 entries.")
    return (f"Deep drawdown of {abs(cur_dd):.1f}% (historical worst {max_dd:.1f}%). "
            "Actionable: do NOT panic-sell into weakness; average in slowly and only with money you won't need for 12+ months.")


def _interpret_vol(vol_now: float, vol_med: float) -> str:
    ratio = vol_now / max(vol_med, 1e-9)
    if ratio > 1.4:
        return (f"Volatility {vol_now*100:.1f}% is {ratio:.1f}× the typical {vol_med*100:.1f}% — stress regime. "
                "Actionable: cut leverage, widen stops, and prefer defined-risk options structures.")
    if ratio < 0.7:
        return (f"Volatility {vol_now*100:.1f}% is unusually low (typical {vol_med*100:.1f}%). "
                "Actionable: good moment to SELL premium / collect income, but keep tail hedges — quiet never lasts.")
    return (f"Volatility {vol_now*100:.1f}% is near its normal {vol_med*100:.1f}% — steady regime. "
            "Actionable: standard swing and income playbooks apply.")


def _interpret_rsi(rsi: float) -> str:
    if rsi >= 70:
        return (f"RSI {rsi:.0f} = overbought. Actionable: avoid fresh longs here; take partial profits "
                "or sell covered calls into strength.")
    if rsi <= 30:
        return (f"RSI {rsi:.0f} = oversold. Actionable: watch for a reversal candle; staged buying or "
                "bull put spreads get the best entry prices in this zone.")
    return (f"RSI {rsi:.0f} = neutral momentum. Actionable: let the trend lead; use 40–60 readings to "
            "add on quiet days rather than chase strength.")


def build_analytics(df: pd.DataFrame, symbol: str,
                    benchmark_closes: Optional[Dict[str, pd.Series]] = None,
                    benchmark_names: Optional[Dict[str, str]] = None) -> Dict:
    """Return the full chart pack: series, monthly heatmap, stats + interpretations."""
    d = df.copy()
    d = d[d["Close"].notna()]
    if len(d) < 60:
        return {"success": False, "error": "not enough history"}

    close = d["Close"].astype(float)
    ret = close.pct_change().fillna(0.0)

    # --- price + moving averages (trim to ~2 years for the chart) ---
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    trim = d.index >= (d.index.max() - pd.Timedelta(days=730))
    price_series = {
        "dates": [str(i.date()) for i in d.index[trim]],
        "close": [round(float(v), 2) for v in close[trim]],
        "sma20": [round(float(v), 2) if not np.isnan(v) else None for v in sma20[trim]],
        "sma50": [round(float(v), 2) if not np.isnan(v) else None for v in sma50[trim]],
        "sma200": [round(float(v), 2) if not np.isnan(v) else None for v in sma200[trim]],
    }

    # --- drawdown series ---
    cummax = close.cummax()
    dd = (close / cummax - 1.0) * 100.0
    drawdown = {
        "dates": [str(i.date()) for i in d.index[trim]],
        "dd": [round(float(v), 2) for v in dd[trim]],
    }

    # --- rolling 21d annualised vol ---
    vol21 = ret.rolling(21).std() * np.sqrt(252) * 100
    volatility = {
        "dates": [str(i.date()) for i in d.index[trim]],
        "vol": [round(float(v), 2) if not np.isnan(v) else None for v in vol21[trim]],
    }

    # --- RSI 14 ---
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_s = 100 - 100 / (1 + rs)
    rsi = {"dates": [str(i.date()) for i in d.index[trim]],
           "rsi": [round(float(v), 1) if not np.isnan(v) else None for v in rsi_s[trim]]}

    # --- monthly returns heatmap (year x month) ---
    mret = close.resample("ME").last().pct_change() * 100
    mm = pd.DataFrame({"y": mret.index.year, "m": mret.index.month, "v": mret.values}).dropna()
    pivot = mm.pivot_table(index="y", columns="m", values="v", aggfunc="sum")
    pivot = pivot.tail(10)
    heatmap = {
        "years": [int(y) for y in pivot.index],
        "months": list(range(1, 13)),
        "values": [[round(float(pivot.loc[y, m]), 2) if (m in pivot.columns and not np.isnan(pivot.loc[y, m])) else None
                    for m in range(1, 13)] for y in pivot.index],
    }
    # best / worst months overall
    flat = mm.dropna()
    best = flat.loc[flat["v"].idxmax()] if len(flat) else None
    worst = flat.loc[flat["v"].idxmin()] if len(flat) else None

    # --- summary & interpretations ---
    last = d.iloc[-1]
    rsi_now = float(rsi_s.iloc[-1]) if not np.isnan(rsi_s.iloc[-1]) else 50.0
    vol_now = float(vol21.iloc[-1]) / 100 if not np.isnan(vol21.iloc[-1]) else 0.15
    vol_med = float(vol21.median()) / 100 if not np.isnan(vol21.median()) else 0.15
    cur_dd = float(dd.iloc[-1]); max_dd = float(dd.min())
    perf = {h: round(float(close.iloc[-1] / close.iloc[-n] - 1) * 100, 2)
            for h, n in {"1w": 5, "1m": 21, "3m": 63, "6m": 126, "1y": 252}.items() if len(close) > n}

    # seasonal: average by calendar month
    season = mm.groupby("m")["v"].mean()
    best_m = int(season.idxmax()); worst_m = int(season.idxmin())
    MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    base = {
        "success": True,
        "symbol": symbol,
        "history_days": int(len(d)),
        "start": str(d.index.min().date()),
        "price": {
            "series": price_series,
            "interpretation": _interpret_trend(d, last),
        },
        "drawdown": {
            "series": drawdown,
            "current": round(cur_dd, 2),
            "max": round(max_dd, 2),
            "interpretation": _interpret_drawdown(cur_dd, max_dd),
        },
        "volatility": {
            "series": volatility,
            "now_pct": round(vol_now * 100, 1),
            "median_pct": round(vol_med * 100, 1),
            "interpretation": _interpret_vol(vol_now, vol_med),
        },
        "rsi": {
            "series": rsi,
            "now": round(rsi_now, 1),
            "interpretation": _interpret_rsi(rsi_now),
        },
        "heatmap": {
            **heatmap,
            "interpretation": (
                f"Green cells are positive months, red cells negative. {MONTHS[best_m-1]} is historically the "
                f"strongest month (avg {float(season[best_m]):+.1f}%) and {MONTHS[worst_m-1]} the weakest "
                f"(avg {float(season[worst_m]):+.1f}%). Actionable: schedule bigger entries after weak-month "
                f"stretches and book partial profits into {MONTHS[best_m-1]} strength."
            ),
        },
        "performance": perf,
        "seasonality": {
            "by_month": [round(float(season.get(m, 0)), 2) for m in range(1, 13)],
            "best_month": MONTHS[best_m - 1],
            "worst_month": MONTHS[worst_m - 1],
            "best_month_ever": (f"{MONTHS[int(best['m'])-1]} {int(best['y'])} ({float(best['v']):+.1f}%)"
                                if best is not None else "n/a"),
            "worst_month_ever": (f"{MONTHS[int(worst['m'])-1]} {int(worst['y'])} ({float(worst['v']):+.1f}%)"
                                 if worst is not None else "n/a"),
        },
    }

    # ── round-3 extensions: indicators, memory, correlations, forecast ──────
    try:
        from app.services.quant_extra import extend_pack
        extras = extend_pack(
            d, close, ret,
            {"rsi": rsi_s, "sma50": sma50, "sma200": sma200,
             "vol21": vol21, "vol_med": vol_med, "perf": perf,
             "month_avg": float(season.get(int(d.index.max().month), 0.0))},
            benchmark_closes=benchmark_closes,
            benchmark_names=benchmark_names)
        return {**base, **extras}
    except Exception as e:
        logger.warning(f"quant extras unavailable for {symbol}: {e}")
        return base
