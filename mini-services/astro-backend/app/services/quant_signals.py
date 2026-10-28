"""
Classic strategy signal board — the systematic rules from
je-suis-tm/quant-trading, howtrader (51bitquant) and OpenBB's `ta` menu,
each turned into a daily BUY / SELL / NEUTRAL state, back-tested in a fully
vectorised way on the symbol's whole history, and explained in plain English.

Backtest conventions (kept deliberately simple and honest):
  * a signal observed at today's close is traded at the NEXT close (shift 1);
  * the strategy curve is long-or-cash (no shorting, no leverage, no costs);
  * "hit rate" counts fresh BUY signals followed by a higher close 20 trading
    days later plus fresh SELL signals followed by a lower close;
  * forward returns are measured close-to-close after each fresh signal.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.services.quant_common import clean, downsample, insight, naive, r

ANN = 252


# ── indicator primitives ─────────────────────────────────────────────────────

def ema(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(span=n, adjust=False, min_periods=n).mean()


def wilder(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def true_range(d: pd.DataFrame) -> pd.Series:
    pc = d["Close"].shift(1)
    return pd.concat([d["High"] - d["Low"], (d["High"] - pc).abs(), (d["Low"] - pc).abs()], axis=1).max(axis=1)


def atr(d: pd.DataFrame, n: int = 14) -> pd.Series:
    return wilder(true_range(d), n)


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    up = wilder(delta.clip(lower=0), n)
    dn = wilder(-delta.clip(upper=0), n)
    rs = up / dn.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(dn != 0, 100.0)


def hold(buy: pd.Series, sell: pd.Series, flat: Optional[pd.Series] = None) -> pd.Series:
    """Event masks → persistent state (+1 after a buy, -1 after a sell, 0 after a flat event)."""
    ev = pd.Series(np.nan, index=buy.index)
    if flat is not None:
        ev[flat.fillna(False).astype(bool)] = 0.0
    ev[sell.fillna(False).astype(bool)] = -1.0
    ev[buy.fillna(False).astype(bool)] = 1.0
    return ev.ffill().fillna(0.0)


def cross_up(a: pd.Series, b) -> pd.Series:
    b_prev = b.shift(1) if isinstance(b, pd.Series) else b
    return (a > b) & (a.shift(1) <= b_prev)


def cross_dn(a: pd.Series, b) -> pd.Series:
    b_prev = b.shift(1) if isinstance(b, pd.Series) else b
    return (a < b) & (a.shift(1) >= b_prev)


def _sign_state(x: pd.Series, thresh: float = 0.0) -> pd.Series:
    s = pd.Series(0.0, index=x.index)
    s[x > thresh] = 1.0
    s[x < -thresh] = -1.0
    return s.where(x.notna(), 0.0)


# ── strategies (each returns state series + optional "levels"/readout) ──────

def s_sma_cross(d):
    c = d["Close"]
    f, s = c.rolling(50).mean(), c.rolling(200).mean()
    return _sign_state(f - s), {"SMA50": f.iloc[-1], "SMA200": s.iloc[-1]}


def s_ema_cross(d):
    c = d["Close"]
    f, s = ema(c, 12), ema(c, 26)
    return _sign_state(f - s), {"EMA12": f.iloc[-1], "EMA26": s.iloc[-1]}


def s_macd(d):
    c = d["Close"]
    m = ema(c, 12) - ema(c, 26)
    sig = m.ewm(span=9, adjust=False).mean()
    return _sign_state(m - sig), {"MACD": m.iloc[-1], "Signal": sig.iloc[-1]}


def s_rsi(d):
    x = rsi(d["Close"])
    return hold(cross_up(x, 30), cross_dn(x, 70)), {"RSI14": x.iloc[-1]}


def s_bbands(d):
    c = d["Close"]
    mid = c.rolling(20).mean()
    sd = c.rolling(20).std()
    up, lo = mid + 2 * sd, mid - 2 * sd
    # W-bottom proxy: close re-enters the band from below; M-top proxy: from above
    buy = (c > lo) & (c.shift(1) <= lo.shift(1))
    sell = (c < up) & (c.shift(1) >= up.shift(1))
    return hold(buy, sell), {"Upper": up.iloc[-1], "Middle": mid.iloc[-1], "Lower": lo.iloc[-1]}


def s_psar(d, step: float = 0.02, max_af: float = 0.2):
    h, lo = d["High"].to_numpy(), d["Low"].to_numpy()
    n = len(h)
    sar = np.empty(n)
    trend = np.ones(n)
    up = True
    af = step
    ep = h[0]
    sar[0] = lo[0]
    for i in range(1, n):
        prev = sar[i - 1]
        cur = prev + af * (ep - prev)
        if up:
            cur = min(cur, lo[i - 1], lo[i - 2] if i > 1 else lo[i - 1])
            if lo[i] < cur:
                up, cur, ep, af = False, ep, lo[i], step
            elif h[i] > ep:
                ep, af = h[i], min(af + step, max_af)
        else:
            cur = max(cur, h[i - 1], h[i - 2] if i > 1 else h[i - 1])
            if h[i] > cur:
                up, cur, ep, af = True, ep, h[i], step
            elif lo[i] < ep:
                ep, af = lo[i], min(af + step, max_af)
        sar[i] = cur
        trend[i] = 1.0 if up else -1.0
    st = pd.Series(trend, index=d.index)
    st.iloc[:5] = 0.0
    return st, {"SAR": sar[-1]}


def s_heikin_ashi(d):
    o, h, lo, c = (d[k].to_numpy() for k in ("Open", "High", "Low", "Close"))
    hc = (o + h + lo + c) / 4.0
    ho = np.empty(len(c))
    ho[0] = (o[0] + c[0]) / 2.0
    for i in range(1, len(c)):
        ho[i] = (ho[i - 1] + hc[i - 1]) / 2.0
    hh = np.maximum(h, np.maximum(ho, hc))
    hl = np.minimum(lo, np.minimum(ho, hc))
    body = np.abs(hc - ho)
    bull = (hc > ho) & ((np.minimum(ho, hc) - hl) <= 0.1 * body)   # no lower shadow
    bear = (hc < ho) & ((hh - np.maximum(ho, hc)) <= 0.1 * body)   # no upper shadow
    idx = d.index
    return hold(pd.Series(bull, index=idx), pd.Series(bear, index=idx)), {"HA close": hc[-1], "HA open": ho[-1]}


def s_awesome(d):
    mp = (d["High"] + d["Low"]) / 2
    ao = mp.rolling(5).mean() - mp.rolling(34).mean()
    return _sign_state(ao), {"AO": ao.iloc[-1]}


def s_dual_thrust(d, n: int = 4, k: float = 0.3):
    hh = d["High"].rolling(n).max().shift(1)
    ll = d["Low"].rolling(n).min().shift(1)
    hc = d["Close"].rolling(n).max().shift(1)
    lc = d["Close"].rolling(n).min().shift(1)
    rng = np.maximum(hh - lc, hc - ll)
    upper = d["Open"] + k * rng
    lower = d["Open"] - k * rng
    return hold(d["Close"] > upper, d["Close"] < lower), {"Upper trigger": upper.iloc[-1], "Lower trigger": lower.iloc[-1]}


def s_range_breakout(d):
    ph, pl = d["High"].shift(1), d["Low"].shift(1)
    buf = 0.25 * (ph - pl)
    upper, lower = ph + buf, pl - buf
    return hold(d["Close"] > upper, d["Close"] < lower), {"Break-up level": upper.iloc[-1] if len(d) else None,
                                                          "Break-down level": lower.iloc[-1]}


def s_ichimoku(d):
    h, lo, c = d["High"], d["Low"], d["Close"]
    tenkan = (h.rolling(9).max() + lo.rolling(9).min()) / 2
    kijun = (h.rolling(26).max() + lo.rolling(26).min()) / 2
    span_a = ((tenkan + kijun) / 2).shift(26)
    span_b = ((h.rolling(52).max() + lo.rolling(52).min()) / 2).shift(26)
    top = np.maximum(span_a, span_b)
    bot = np.minimum(span_a, span_b)
    s = pd.Series(0.0, index=d.index)
    s[(c > top) & (tenkan > kijun)] = 1.0
    s[(c < bot) & (tenkan < kijun)] = -1.0
    return s, {"Tenkan": tenkan.iloc[-1], "Kijun": kijun.iloc[-1], "Cloud top": top.iloc[-1], "Cloud bottom": bot.iloc[-1]}


def s_stochastic(d):
    ll = d["Low"].rolling(14).min()
    hh = d["High"].rolling(14).max()
    k = 100 * (d["Close"] - ll) / (hh - ll).replace(0, np.nan)
    k = k.rolling(3).mean()
    dd = k.rolling(3).mean()
    buy = cross_up(k, dd) & (dd < 25)
    sell = cross_dn(k, dd) & (dd > 75)
    return hold(buy, sell), {"%K": k.iloc[-1], "%D": dd.iloc[-1]}


def s_adx(d):
    up = d["High"].diff()
    dn = -d["Low"].diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=d.index)
    ndm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=d.index)
    tr = wilder(true_range(d), 14)
    pdi = 100 * wilder(pdm, 14) / tr
    ndi = 100 * wilder(ndm, 14) / tr
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
    adx = wilder(dx, 14)
    s = pd.Series(0.0, index=d.index)
    s[(adx > 20) & (pdi > ndi)] = 1.0
    s[(adx > 20) & (ndi > pdi)] = -1.0
    return s, {"ADX": adx.iloc[-1], "+DI": pdi.iloc[-1], "-DI": ndi.iloc[-1]}


def s_aroon(d, n: int = 25):
    hi_age = d["High"].rolling(n + 1).apply(lambda x: n - int(np.argmax(x)), raw=True)
    lo_age = d["Low"].rolling(n + 1).apply(lambda x: n - int(np.argmin(x)), raw=True)
    a_up = 100 * (n - hi_age) / n
    a_dn = 100 * (n - lo_age) / n
    osc = a_up - a_dn
    return _sign_state(osc, 40), {"Aroon up": a_up.iloc[-1], "Aroon down": a_dn.iloc[-1]}


def s_cci(d, n: int = 20):
    tp = (d["High"] + d["Low"] + d["Close"]) / 3
    sma = tp.rolling(n).mean()
    mad = tp.rolling(n).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    cci = (tp - sma) / (0.015 * mad.replace(0, np.nan))
    return hold(cross_up(cci, 100), cross_dn(cci, -100)), {"CCI20": cci.iloc[-1]}


def s_turtle(d):
    c = d["Close"].to_numpy()
    h20 = d["High"].rolling(20).max().shift(1).to_numpy()
    l20 = d["Low"].rolling(20).min().shift(1).to_numpy()
    h10 = d["High"].rolling(10).max().shift(1).to_numpy()
    l10 = d["Low"].rolling(10).min().shift(1).to_numpy()
    st = np.zeros(len(c))
    cur = 0.0
    for i in range(len(c)):
        if np.isnan(h20[i]):
            continue
        if cur <= 0 and c[i] > h20[i]:
            cur = 1.0
        elif cur >= 0 and c[i] < l20[i]:
            cur = -1.0
        elif cur == 1.0 and c[i] < l10[i]:
            cur = 0.0
        elif cur == -1.0 and c[i] > h10[i]:
            cur = 0.0
        st[i] = cur
    return pd.Series(st, index=d.index), {"20d high": h20[-1], "20d low": l20[-1], "10d exit (long)": l10[-1]}


def s_keltner(d):
    mid = ema(d["Close"], 20)
    a = atr(d, 10)
    up, lo = mid + 2 * a, mid - 2 * a
    return hold(d["Close"] > up, d["Close"] < lo), {"Upper": up.iloc[-1], "Mid": mid.iloc[-1], "Lower": lo.iloc[-1]}


def s_obv(d):
    obv = (np.sign(d["Close"].diff()).fillna(0) * d["Volume"]).cumsum()
    return _sign_state(obv - ema(obv, 20)), {"OBV vs 20d EMA": float(obv.iloc[-1] - ema(obv, 20).iloc[-1])}


def s_adl(d):
    rng = (d["High"] - d["Low"]).replace(0, np.nan)
    clv = (((d["Close"] - d["Low"]) - (d["High"] - d["Close"])) / rng).fillna(0)
    ad = (clv * d["Volume"]).cumsum()
    return _sign_state(ad - ema(ad, 20)), {"A/D vs 20d EMA": float(ad.iloc[-1] - ema(ad, 20).iloc[-1])}


def s_fibonacci(d, n: int = 126):
    c = d["Close"]
    hi = d["High"].rolling(n).max()
    lo = d["Low"].rolling(n).min()
    retr = (hi - c) / (hi - lo).replace(0, np.nan)
    up = c > c.rolling(200).mean()
    s = pd.Series(0.0, index=d.index)
    s[up & (retr >= 0.382) & (retr <= 0.618)] = 1.0
    s[retr > 0.786] = -1.0
    H, L = float(hi.iloc[-1]), float(lo.iloc[-1])
    lv = {f"{p:g}%": H - (H - L) * p / 100 for p in (0, 23.6, 38.2, 50, 61.8, 78.6, 100)}
    return s, lv


def s_zscore(d):
    c = d["Close"]
    z = (c - c.rolling(20).mean()) / c.rolling(20).std()
    flat = (np.sign(z) != np.sign(z.shift(1))) & z.notna() & z.shift(1).notna()
    return hold(z < -2, z > 2, flat=flat), {"z-score (20d)": z.iloc[-1]}


def s_grid(d):
    c = d["Close"]
    mid = c.rolling(50).mean()
    step = 1.5 * atr(d, 14)
    g = (c - mid) / step.replace(0, np.nan)
    flat = (np.sign(g) != np.sign(g.shift(1))) & g.notna() & g.shift(1).notna()
    M, S = float(mid.iloc[-1]), float(step.iloc[-1])
    lv = {f"{'+' if k > 0 else ''}{k} step": M + k * S for k in (3, 2, 1, 0, -1, -2, -3)}
    return hold(g <= -2, g >= 2, flat=flat), lv


def s_williams(d):
    hh = d["High"].rolling(14).max()
    ll = d["Low"].rolling(14).min()
    wr = -100 * (hh - d["Close"]) / (hh - ll).replace(0, np.nan)
    return hold(cross_up(wr, -80), cross_dn(wr, -20)), {"%R": wr.iloc[-1]}


def s_tsmom(d):
    m = d["Close"] / d["Close"].shift(126) - 1
    return _sign_state(m), {"6-month return %": m.iloc[-1] * 100}


# (key, name, family, source, rule, fn, needs_volume)
STRATEGIES: List[Tuple[str, str, str, str, str, Callable, bool]] = [
    ("sma_cross", "SMA 50/200 crossover", "Trend", "OpenBB ta · je-suis-tm",
     "Long while the 50-day average is above the 200-day (golden cross), bearish below (death cross).", s_sma_cross, False),
    ("ema_cross", "EMA 12/26 crossover", "Trend", "howtrader CTA · OpenBB ta",
     "Fast exponential average above the slow one = short-term uptrend.", s_ema_cross, False),
    ("macd", "MACD oscillator", "Momentum", "je-suis-tm/quant-trading",
     "MACD line above its 9-day signal line = momentum accelerating up.", s_macd, False),
    ("rsi", "RSI pattern (30/70)", "Mean-reversion", "je-suis-tm/quant-trading",
     "Buy when RSI climbs back above 30 from oversold; sell when it drops back below 70.", s_rsi, False),
    ("bbands", "Bollinger Bands W / M", "Mean-reversion", "je-suis-tm/quant-trading",
     "Buy when price re-enters the 2σ band from below (W-bottom), sell when it falls back in from above (M-top).", s_bbands, False),
    ("psar", "Parabolic SAR", "Trend", "je-suis-tm/quant-trading",
     "Trailing stop that flips: price above the SAR dots = long, below = short.", s_psar, False),
    ("heikin", "Heikin-Ashi candles", "Trend", "je-suis-tm/quant-trading",
     "Smoothed candles: a strong green candle with no lower wick = buy, strong red with no upper wick = sell.", s_heikin_ashi, False),
    ("awesome", "Awesome Oscillator", "Momentum", "je-suis-tm/quant-trading",
     "5-bar vs 34-bar midpoint average: above zero = bullish momentum.", s_awesome, False),
    ("dual_thrust", "Dual Thrust", "Breakout", "je-suis-tm/quant-trading · howtrader",
     "Breakout when the close moves more than 30% of the recent 4-day range away from today's open (daily adaptation of the intraday rule).", s_dual_thrust, False),
    ("range_break", "Range breakout (London-Breakout style)", "Breakout", "je-suis-tm/quant-trading",
     "Daily adaptation of London Breakout: trade the break of yesterday's high/low plus a 25% buffer.", s_range_breakout, False),
    ("ichimoku", "Ichimoku cloud", "Trend", "OpenBB ta",
     "Price above the cloud with Tenkan above Kijun = bull trend; below the cloud with Tenkan below Kijun = bear.", s_ichimoku, False),
    ("stoch", "Stochastic %K/%D", "Mean-reversion", "OpenBB ta · howtrader",
     "%K crossing up through %D in the oversold zone = buy; crossing down in overbought = sell.", s_stochastic, False),
    ("adx", "ADX / DMI", "Trend", "OpenBB ta",
     "When ADX > 20 a trend exists; +DI above -DI says it is up, -DI above +DI says it is down.", s_adx, False),
    ("aroon", "Aroon (25)", "Trend", "OpenBB ta",
     "Measures how recently the 25-day high vs low was made; strongly positive = new highs dominate.", s_aroon, False),
    ("cci", "CCI (20)", "Momentum", "je-suis-tm · OpenBB ta",
     "Commodity Channel Index above +100 = strong up-thrust, below -100 = strong down-thrust.", s_cci, False),
    ("turtle", "Donchian / Turtle (20/10)", "Breakout", "howtrader · OpenBB ta",
     "Buy a 20-day high breakout, exit on a 10-day low (the original Turtle rules); mirror for shorts.", s_turtle, False),
    ("keltner", "Keltner channel", "Breakout", "OpenBB ta · howtrader",
     "Close outside EMA20 ± 2×ATR = volatility breakout in that direction.", s_keltner, False),
    ("obv", "On-Balance Volume trend", "Volume", "OpenBB ta",
     "Running volume total above its 20-day average = buyers are accumulating.", s_obv, True),
    ("adl", "Accumulation / Distribution", "Volume", "OpenBB ta",
     "Chaikin A/D line above its 20-day average = closes near the highs on volume (accumulation).", s_adl, True),
    ("fib", "Fibonacci retracement", "Mean-reversion", "OpenBB ta (fib)",
     "In an uptrend, a pullback to the 38.2–61.8% retracement zone is a buy; losing 78.6% breaks the trend.", s_fibonacci, False),
    ("zscore", "Mean-reversion z-score", "Mean-reversion", "je-suis-tm (pair/mean-rev) · QuantMuse",
     "Buy when price is 2 standard deviations below its 20-day mean, exit at the mean; mirror for sells.", s_zscore, False),
    ("grid", "Grid levels", "Mean-reversion", "howtrader grid strategy",
     "Grid of ATR-spaced levels around the 50-day mean: buy 2 steps below, sell 2 steps above, reset at the mean.", s_grid, False),
    ("williams", "Williams %R", "Mean-reversion", "OpenBB ta",
     "Buy when %R rises back through -80, sell when it falls back through -20.", s_williams, False),
    ("tsmom", "Time-series momentum (6m)", "Momentum", "QuantMuse · ffn",
     "Long when the last 6 months' return is positive — the best-documented anomaly in finance.", s_tsmom, False),
]


# bars an indicator needs before its state means anything (timeframe heatmap)
MIN_BARS = {"sma_cross": 200, "fib": 200, "tsmom": 127, "ichimoku": 78, "awesome": 34, "macd": 35,
            "aroon": 26, "adx": 42, "grid": 50}


# ── backtest ─────────────────────────────────────────────────────────────────

def _max_dd(eq: np.ndarray) -> float:
    if len(eq) == 0:
        return 0.0
    peak = np.maximum.accumulate(eq)
    return float((eq / peak - 1).min() * 100)


def _cagr(eq: np.ndarray, n: int) -> Optional[float]:
    if n < 20 or eq[-1] <= 0:
        return None
    return float((eq[-1] ** (ANN / n) - 1) * 100)


def backtest(close: pd.Series, state: pd.Series, fwd5: pd.Series, fwd20: pd.Series) -> Dict:
    ret = close.pct_change().fillna(0.0)
    valid = state.ne(0).cummax() if state.ne(0).any() else pd.Series(False, index=state.index)
    start = int(np.argmax(valid.to_numpy())) if valid.any() else len(state)
    st = state.iloc[start:]
    rt = ret.iloc[start:]
    pos = (st.shift(1) == 1).astype(float)
    strat = (pos * rt).to_numpy()
    eq = np.cumprod(1 + strat)
    bh = np.cumprod(1 + rt.to_numpy())
    n = len(st)
    prev = state.shift(1)
    buy_ev = (state == 1) & (prev != 1)
    sell_ev = (state == -1) & (prev != -1)
    b5, b20 = fwd5[buy_ev].dropna(), fwd20[buy_ev].dropna()
    s20 = fwd20[sell_ev].dropna()
    hits = int((b20 > 0).sum() + (s20 < 0).sum())
    tot = int(len(b20) + len(s20))
    vol = float(np.std(strat) * np.sqrt(ANN)) if n > 2 else 0.0
    sharpe = float(np.mean(strat) * ANN / vol) if vol > 0 else 0.0
    bh_vol = float(np.std(rt) * np.sqrt(ANN)) if n > 2 else 0.0
    bh_sharpe = float(np.mean(rt) * ANN / bh_vol) if bh_vol > 0 else 0.0
    return {
        "signals": int(buy_ev.sum() + sell_ev.sum()),
        "buy_signals": int(buy_ev.sum()),
        "hit_rate": r(100 * hits / tot, 1) if tot else None,
        "avg_fwd5_buy": r(b5.mean() * 100, 2) if len(b5) else None,
        "avg_fwd20_buy": r(b20.mean() * 100, 2) if len(b20) else None,
        "avg_fwd20_sell": r(s20.mean() * 100, 2) if len(s20) else None,
        "cagr": r(_cagr(eq, n), 2),
        "bh_cagr": r(_cagr(bh, n), 2),
        "max_dd": r(_max_dd(eq), 1),
        "bh_max_dd": r(_max_dd(bh), 1),
        "sharpe": r(sharpe, 2),
        "bh_sharpe": r(bh_sharpe, 2),
        "time_in_market": r(100 * float(pos.mean()), 0) if n else None,
        "years": r(n / ANN, 1),
    }


def _label(v: float) -> str:
    return "BUY" if v > 0 else "SELL" if v < 0 else "NEUTRAL"


def _row_meaning(name: str, sig: str, age: int, bt: Dict) -> Tuple[str, str]:
    hr = bt.get("hit_rate")
    f20 = bt.get("avg_fwd20_buy")
    cagr, bh = bt.get("cagr"), bt.get("bh_cagr")
    sh, bsh = bt.get("sharpe") or 0, bt.get("bh_sharpe") or 0
    dd, bdd = bt.get("max_dd"), bt.get("bh_max_dd")
    parts = [f"{sig} for {age} day{'s' if age != 1 else ''}."]
    if hr is not None:
        parts.append(f"Past fresh signals were right {hr:.0f}% of the time over 20 days")
        if f20 is not None:
            parts[-1] += f"; after BUYs the next month averaged {f20:+.1f}%"
        parts[-1] += "."
    if cagr is not None and bh is not None:
        parts.append(f"Long-or-cash version: {cagr:.1f}%/yr (max DD {dd:.0f}%) vs buy-and-hold {bh:.1f}%/yr (max DD {bdd:.0f}%).")
    if (bt.get("signals") or 0) < 20:
        return " ".join(parts), ("Too few signals in history to judge this rule on this symbol — "
                                 "treat the verdict as anecdotal, not statistical.")
    good = sh >= bsh * 0.9 and (hr or 0) >= 50
    smoother = dd is not None and bdd is not None and dd > bdd * 0.7
    if good and sig == "BUY":
        act = f"{name} has a real historical edge here and says BUY — a valid green light for adding."
    elif good and sig == "SELL":
        act = f"{name} has a real historical edge and says SELL — tighten stops or hedge."
    elif smoother:
        act = "Weak as a return engine but it cut drawdowns — use it as a risk filter, not an entry trigger."
    else:
        act = "No reliable edge on this symbol — treat it as background colour, not a trigger."
    return " ".join(parts), act


def _states_for(d: pd.DataFrame, has_volume: bool) -> Dict[str, Tuple[pd.Series, Dict]]:
    out = {}
    for key, _n, _f, _src, _rule, fn, needs_vol in STRATEGIES:
        if needs_vol and not has_volume:
            continue
        try:
            st, lv = fn(d)
            out[key] = (st.fillna(0.0), lv)
        except Exception:  # pragma: no cover - defensive; one bad indicator must not kill the board
            continue
    return out


def _resample(d: pd.DataFrame, rule: str) -> pd.DataFrame:
    return d.resample(rule).agg({"Open": "first", "High": "max", "Low": "min", "Close": "last",
                                 "Volume": "sum"}).dropna(subset=["Close"])


def build_signals(df: pd.DataFrame, symbol: str) -> Dict:
    d = naive(df)
    if len(d) < 260:
        return {"success": False, "error": "need at least ~1 year of daily history"}
    close = d["Close"]
    has_volume = bool((d["Volume"].tail(260) > 0).mean() > 0.9)
    fwd5 = close.shift(-5) / close - 1
    fwd20 = close.shift(-20) / close - 1
    fwd60 = close.shift(-60) / close - 1
    states = _states_for(d, has_volume)

    rows = []
    for key, name, fam, src, rule, _fn, _v in STRATEGIES:
        if key not in states:
            continue
        st, lv = states[key]
        now = float(st.iloc[-1])
        sig = _label(now)
        chg = st.ne(st.shift(1)).to_numpy()
        last_change = int(np.flatnonzero(chg)[-1]) if chg.any() else 0
        age = len(st) - 1 - last_change
        bt = backtest(close, st, fwd5, fwd20)
        means, action = _row_meaning(name, sig, age, bt)
        rows.append({
            "key": key, "name": name, "family": fam, "source": src, "rule": rule,
            "signal": sig, "value": now, "age_days": age, "fresh": age <= 5,
            "readout": {k: r(v, 2) for k, v in lv.items()},
            "backtest": bt,
            "insight": insight(rule, means, action),
        })

    # consensus (simple vote + edge-weighted vote)
    votes = np.array([rw["value"] for rw in rows]) if rows else np.zeros(1)
    weights = np.array([(max(0.0, (rw["backtest"].get("sharpe") or 0.0)) if (rw["backtest"].get("signals") or 0) >= 20 else 0.0) + 0.05
                        for rw in rows]) if rows else np.ones(1)
    score = float(votes.mean() * 100)
    wscore = float((votes * weights).sum() / weights.sum() * 100)
    n_buy = int((votes > 0).sum()); n_sell = int((votes < 0).sum()); n_neu = int((votes == 0).sum())
    lab = ("Strong BUY" if wscore >= 50 else "BUY" if wscore >= 15 else
           "Strong SELL" if wscore <= -50 else "SELL" if wscore <= -15 else "NEUTRAL")

    # consensus history + its own forward-return evidence
    mat = pd.DataFrame({k: v[0] for k, v in states.items()})
    cons = mat.mean(axis=1) * 100
    tail = cons.index >= cons.index.max() - pd.Timedelta(days=730)
    hist_idx = downsample(int(tail.sum()), 260)
    ct = cons[tail].iloc[hist_idx]
    pt = close[tail].iloc[hist_idx]
    bull_days = fwd20[cons >= 30].dropna()
    bear_days = fwd20[cons <= -30].dropna()
    all_days = fwd20.dropna()
    ev_line = (f"Historically, when the consensus was ≥ +30 the next 20 days averaged {bull_days.mean()*100:+.2f}% "
               f"({len(bull_days)} days); when ≤ -30 they averaged {bear_days.mean()*100:+.2f}% ({len(bear_days)} days); "
               f"any day: {all_days.mean()*100:+.2f}%.") if len(bull_days) and len(bear_days) else ""
    contrarian = bool(len(bull_days) and len(bear_days) and bear_days.mean() > bull_days.mean())
    best = sorted([rw for rw in rows if rw["backtest"].get("sharpe") is not None and (rw["backtest"].get("signals") or 0) >= 20],
                  key=lambda x: x["backtest"]["sharpe"], reverse=True)[:3]
    consensus = {
        "score": r(score, 0), "weighted_score": r(wscore, 0), "label": lab,
        "buy": n_buy, "sell": n_sell, "neutral": n_neu, "total": len(rows),
        "history": {"dates": [str(i.date()) for i in ct.index], "score": [r(v, 1) for v in ct],
                    "close": [r(v, 2) for v in pt]},
        "best_rules": [b["name"] for b in best],
        "insight": insight(
            f"{n_buy} of {len(rows)} classic rules say BUY, {n_sell} say SELL and {n_neu} are neutral; "
            f"weighting each rule by its own historical Sharpe gives {wscore:+.0f}.",
            (ev_line + " " if ev_line else "")
            + f"The rules with the best track record on {symbol} are {', '.join(b['name'] for b in best)}.",
            ("Majority and the best-performing rules agree on the upside — trend-following entries are favoured."
             if wscore >= 15 else
             "Majority and the best-performing rules lean bearish — protect capital first, buy only on confirmed turns."
             if wscore <= -15 else
             "Rules disagree — no edge from the board today; wait for alignment or trade smaller.")
            + (" Caution: on this symbol a bearish board has historically been followed by BETTER returns than a "
               "bullish one (it mean-reverts) — fade extremes rather than follow them." if contrarian else "")),
    }

    # signal × timeframe heatmap
    tf = {"Daily": d, "Weekly": _resample(d, "W-FRI"), "Monthly": _resample(d, "ME")}
    tf_states = {}
    for lab_tf, dd_ in tf.items():
        if len(dd_) < 60:
            tf_states[lab_tf] = {}
            continue
        hv = bool((dd_["Volume"].tail(60) > 0).mean() > 0.9)
        tf_states[lab_tf] = {k: float(v[0].iloc[-1]) for k, v in _states_for(dd_, hv).items()
                             if len(dd_) >= MIN_BARS.get(k, 40) + 10}
    tf_rows = []
    for rw in rows:
        tf_rows.append({"name": rw["name"], "values": [tf_states[t].get(rw["key"]) for t in tf]})
    agree = [sum(1 for v in tr["values"] if v is not None and v > 0) - sum(1 for v in tr["values"] if v is not None and v < 0)
             for tr in tf_rows]
    aligned_up = sum(1 for a in agree if a == 3); aligned_dn = sum(1 for a in agree if a == -3)
    tf_heat = {
        "timeframes": list(tf.keys()), "rows": tf_rows,
        "insight": insight(
            "Each cell is a rule's verdict on daily, weekly and monthly bars (green = BUY, red = SELL, beige = neutral).",
            f"{aligned_up} rules are BUY on all three timeframes and {aligned_dn} are SELL on all three. "
            "Signals that agree across timeframes are far more reliable than a lone daily flicker.",
            ("Multi-timeframe alignment is bullish — buy pullbacks on the daily chart in the direction of the weekly/monthly trend."
             if aligned_up > aligned_dn + 2 else
             "Multi-timeframe alignment is bearish — rallies on the daily chart are selling opportunities until weekly bars turn."
             if aligned_dn > aligned_up + 2 else
             "Timeframes conflict — the bigger (monthly) column wins; size down until daily signals line up with it.")),
    }

    # signal × forward-horizon edge heatmap
    base = {h: float(f.dropna().mean() * 100) for h, f in (("5d", fwd5), ("20d", fwd20), ("60d", fwd60))}
    hz_rows = []
    for rw in rows:
        st = states[rw["key"]][0]
        vals = []
        for h, f in (("5d", fwd5), ("20d", fwd20), ("60d", fwd60)):
            m = f[st == 1].dropna()
            vals.append(r(m.mean() * 100 - base[h], 2) if len(m) > 30 else None)
        hz_rows.append({"name": rw["name"], "values": vals})
    best_h = max(hz_rows, key=lambda x: x["values"][1] if x["values"][1] is not None else -1e9) if hz_rows else None
    worst_h = min(hz_rows, key=lambda x: x["values"][1] if x["values"][1] is not None else 1e9) if hz_rows else None
    horizon_heat = {
        "horizons": ["5d", "20d", "60d"], "rows": hz_rows,
        "baseline": {k: r(v, 2) for k, v in base.items()},
        "insight": insight(
            "Extra forward return (vs. an average day) earned while each rule was in BUY mode, over 5, 20 and 60 trading days.",
            (f"{best_h['name']} adds the most over 20 days ({best_h['values'][1]:+.2f}%), "
             f"{worst_h['name']} the least ({worst_h['values'][1]:+.2f}%). Green columns that grow left-to-right are rules whose edge compounds.")
            if best_h and worst_h and best_h["values"][1] is not None and worst_h["values"][1] is not None else
            "Not enough signal history for a horizon comparison.",
            "Favour rules that are green across all three horizons; rules that are red mean their BUY signals historically came before below-average returns — fade or ignore them."),
    }

    return clean({
        "success": True, "symbol": symbol, "start": str(d.index[0].date()), "bars": len(d),
        "has_volume": has_volume, "rules": rows, "consensus": consensus,
        "timeframe_heatmap": tf_heat, "horizon_heatmap": horizon_heat,
        "method": ("Signals on today's close, traded next close; long-or-cash curve, no costs; "
                   f"tested on {len(d):,} daily bars since {d.index[0].date()}. Educational, not advice."),
    })
