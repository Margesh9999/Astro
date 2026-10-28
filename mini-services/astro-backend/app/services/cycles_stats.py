"""
Historical cycle statistics (v1.3)
==================================
For the selected symbol over its FULL price history, measures how the stock
behaved in each classical cycle state:

  moon phase (8) · paksha (2) · Moon nakshatra (27) · Sun sidereal sign (12,
  i.e. Sankranti seasonality) · Mercury/Venus/Mars/Jupiter/Saturn retrograde
  vs direct.

Each bucket reports days, mean daily return, hit rate (share of up days), the
difference vs the stock's all-days baseline, a t-statistic and an honest
verdict that applies a multiple-comparison hurdle (testing 27 nakshatras will
always throw up a few "lucky" ones). Plain-English conclusions are generated
from the numbers. Educational only — past cycles do not guarantee anything.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from app.services.cycles_sky import (NAK_LORDS, NAKSHATRAS, PHASES8, RASHI, RETRO_PLANETS, SIGNS, SKY)

# multiple-comparison hurdles (approx. Bonferroni at 5% two-sided)
Z_CRIT = {2: 2.24, 8: 2.73, 12: 2.87, 27: 3.18}


def fnum(x, nd: int = 4) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(v) or math.isinf(v):
        return 0.0
    return round(v, nd)


def fmt_date(iso: Optional[str]) -> str:
    if not iso:
        return "—"
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {d.strftime('%b')}"


def verdict(t: float, n: int, groups: int, min_n: int = 30) -> str:
    if n < min_n:
        return "too few"
    zc = Z_CRIT.get(groups, 2.0 + 0.35 * math.log(max(groups, 2)))
    a = abs(t)
    if a >= zc:
        return "significant"
    if a >= 1.96:
        return "weak"
    return "noise"


# ---------------------------------------------------------------------------
# price alignment
# ---------------------------------------------------------------------------
class PricePanel:
    """Close prices aligned to sky-table rows."""

    def __init__(self, df: pd.DataFrame):
        SKY.ensure()
        s = df["Close"].dropna().astype(float)
        idx = pd.DatetimeIndex(s.index)
        if idx.tz is not None:
            idx = idx.tz_convert(None)
        d = idx.normalize().values.astype("datetime64[D]")
        keep = (d >= SKY.dates[0]) & (d <= SKY.dates[-1])
        self.dates = d[keep]
        self.close = s.values[keep]
        # dedupe same-day rows (keep last)
        if len(self.dates):
            _, last = np.unique(self.dates[::-1], return_index=True)
            sel = np.sort(len(self.dates) - 1 - last)
            self.dates, self.close = self.dates[sel], self.close[sel]
        self.sky_i = (self.dates - SKY.dates[0]).astype(int)
        self.n = len(self.close)
        self.ret = np.full(self.n, np.nan)
        if self.n > 1:
            self.ret[1:] = self.close[1:] / self.close[:-1] - 1.0
        self.absr = np.abs(self.ret)

    def first_on_or_after(self, sky_idx: int) -> int:
        """Trading-row index of the first session on/after a sky-table row."""
        return int(np.searchsorted(self.sky_i, sky_idx, side="left"))

    def fwd(self, k: int) -> np.ndarray:
        """k-day forward return from close[t-1] to close[t-1+k] for every row t."""
        memo = self.__dict__.setdefault("_fwd", {})
        if k not in memo:
            out = np.full(self.n, np.nan)
            if self.n > k:
                out[1:self.n - k + 1] = self.close[k:] / self.close[:self.n - k] - 1.0
            memo[k] = out
        return memo[k]

    def vol_log_ratios(self) -> np.ndarray:
        """log( mean|r| over rows t..t+4  ÷  mean|r| over rows t-60..t-1 ) for every row t."""
        memo = self.__dict__.setdefault("_vlr", None)
        if memo is not None:
            return memo
        a = np.nan_to_num(self.absr, nan=0.0)
        cs = np.concatenate([[0.0], np.cumsum(a)])
        out = np.full(self.n, np.nan)
        t = np.arange(61, self.n - 5)
        if len(t):
            post = (cs[t + 5] - cs[t]) / 5.0
            pre = (cs[t] - cs[t - 60]) / 60.0
            with np.errstate(divide="ignore", invalid="ignore"):
                lr = np.log(post / pre)
            lr[~np.isfinite(lr)] = np.nan
            out[t] = lr
        self._vlr = out
        return out

    @property
    def start(self) -> str:
        return str(self.dates[0]) if self.n else ""


def _bucket(r: np.ndarray, g: np.ndarray, labels: List[str], extra: Optional[List[Dict]] = None) -> Dict:
    ok = ~np.isnan(r)
    r, g = r[ok], g[ok]
    base_mean = float(np.mean(r))
    base_std = float(np.std(r))
    base_hit = float(np.mean(r > 0))
    rows = []
    G = len(labels)
    for k, lab in enumerate(labels):
        m = g == k
        n = int(m.sum())
        if n == 0:
            rows.append({"label": lab, "n": 0, "mean_pct": 0.0, "hit_pct": 0.0, "diff_pct": 0.0,
                         "t": 0.0, "verdict": "too few"})
            continue
        mu = float(np.mean(r[m]))
        hit = float(np.mean(r[m] > 0))
        t = (mu - base_mean) / (base_std / math.sqrt(n)) if base_std > 0 else 0.0
        row = {"label": lab, "n": n, "mean_pct": fnum(mu * 100, 4), "hit_pct": fnum(hit * 100, 1),
               "diff_pct": fnum((mu - base_mean) * 100, 4), "hit_diff": fnum((hit - base_hit) * 100, 1),
               "t": fnum(t, 2), "verdict": verdict(t, n, G),
               "vol_ratio": fnum(float(np.std(r[m])) / base_std if base_std > 0 else 1.0, 2)}
        if extra:
            row.update(extra[k])
        rows.append(row)
    return {"baseline": {"mean_pct": fnum(base_mean * 100, 4), "hit_pct": fnum(base_hit * 100, 1),
                         "days": int(len(r))}, "rows": rows}


def _two_state(r: np.ndarray, flag: np.ndarray) -> Dict:
    ok = ~np.isnan(r)
    r, flag = r[ok], flag[ok]
    a, b = r[flag], r[~flag]
    if len(a) < 2 or len(b) < 2:
        return {"retro": {"n": int(len(a))}, "direct": {"n": int(len(b))}, "t": 0.0, "verdict": "too few"}
    se = math.sqrt(np.var(a, ddof=1) / len(a) + np.var(b, ddof=1) / len(b))
    t = (np.mean(a) - np.mean(b)) / se if se > 0 else 0.0
    return {
        "retro": {"n": int(len(a)), "mean_pct": fnum(np.mean(a) * 100), "hit_pct": fnum(np.mean(a > 0) * 100, 1),
                  "vol_pct": fnum(np.std(a) * 100, 3), "annual_pct": fnum(np.mean(a) * 252 * 100, 1)},
        "direct": {"n": int(len(b)), "mean_pct": fnum(np.mean(b) * 100), "hit_pct": fnum(np.mean(b > 0) * 100, 1),
                   "vol_pct": fnum(np.std(b) * 100, 3), "annual_pct": fnum(np.mean(b) * 252 * 100, 1)},
        "vol_ratio": fnum(np.std(a) / np.std(b) if np.std(b) > 0 else 1.0, 2),
        "t": fnum(t, 2), "verdict": verdict(t, len(a), 2),
    }


def _runs(flag_rows: np.ndarray, close: np.ndarray, sky_i: np.ndarray) -> List[Dict]:
    """Contiguous runs where flag_rows is True -> compounded return per run."""
    out = []
    n = len(flag_rows)
    i = 0
    while i < n:
        if not flag_rows[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and flag_rows[j + 1] and sky_i[j + 1] - sky_i[j] <= 5:
            j += 1
        if i >= 1:
            out.append({"start": int(sky_i[i]), "end": int(sky_i[j]), "ret": close[j] / close[i - 1] - 1.0,
                        "days": j - i + 1})
        i = j + 1
    return out


def _next_idx(mask: np.ndarray, start: int) -> Optional[str]:
    j = SKY.next_where(mask, start)
    return SKY.date_of(j) if j is not None else None


# ---------------------------------------------------------------------------
# main entry
# ---------------------------------------------------------------------------
def cycle_stats(df: pd.DataFrame, symbol: str, name: str) -> Dict:
    pp = PricePanel(df)
    if pp.n < 300:
        return {"success": False, "error": "not enough price history for cycle statistics"}
    si = pp.sky_i
    r = pp.ret
    f5 = pp.fwd(5)
    t_i = SKY.today_idx()

    # --- moon phase (8) ----------------------------------------------------
    ph = SKY.phase8[si]
    nxt = [{"next": _next_idx(SKY.phase8 == k, t_i)} for k in range(8)]
    phase = _bucket(r, ph, PHASES8, nxt)
    p5 = _bucket(f5, ph, PHASES8)
    for row, row5 in zip(phase["rows"], p5["rows"]):
        row["fwd5_pct"] = row5["mean_pct"]
        row["fwd5_diff"] = row5["diff_pct"]
    phase["current"] = PHASES8[int(SKY.phase8[t_i])]

    # --- paksha (2) --------------------------------------------------------
    paksha = _bucket(r, SKY.paksha[si], ["Shukla (waxing)", "Krishna (waning)"],
                     [{"next": _next_idx(SKY.paksha == k, t_i)} for k in range(2)])
    paksha["current"] = ["Shukla (waxing)", "Krishna (waning)"][int(SKY.paksha[t_i])]

    # --- nakshatra (27) ----------------------------------------------------
    nk_extra = []
    for k in range(27):
        nk_extra.append({"lord": NAK_LORDS[k], "next": _next_idx(SKY.nakshatra == k, t_i + 1)})
    nak = _bucket(r, SKY.nakshatra[si], NAKSHATRAS, nk_extra)
    nak["current"] = NAKSHATRAS[int(SKY.nakshatra[t_i])]

    # --- sun sign (12) + Sankranti month returns ---------------------------
    ss = SKY.sun_sign[si]
    sun_extra = []
    for k in range(12):
        runs = _runs(ss == k, pp.close, si)
        rr = np.array([x["ret"] for x in runs]) if runs else np.array([])
        # next Sankranti into this sign
        mask = (SKY.sun_sign == k)
        mask_entry = np.zeros_like(mask)
        mask_entry[1:] = mask[1:] & ~mask[:-1]
        sun_extra.append({
            "rashi": RASHI[k], "months": int(len(rr)),
            "month_mean_pct": fnum(np.mean(rr) * 100 if len(rr) else 0.0, 2),
            "month_hit_pct": fnum(np.mean(rr > 0) * 100 if len(rr) else 0.0, 1),
            "next": _next_idx(mask_entry, t_i + 1),
        })
    sun = _bucket(r, ss, SIGNS, sun_extra)
    sun["current"] = SIGNS[int(SKY.sun_sign[t_i])]

    # --- retrogrades -------------------------------------------------------
    retro = {}
    for p in RETRO_PLANETS:
        flag = SKY.retro[p][si]
        st = _two_state(r, flag)
        runs = _runs(flag, pp.close, si)
        rr = np.array([x["ret"] for x in runs]) if runs else np.array([])
        st["periods"] = int(len(rr))
        st["period_mean_pct"] = fnum(np.mean(rr) * 100 if len(rr) else 0.0, 2)
        st["period_hit_pct"] = fnum(np.mean(rr > 0) * 100 if len(rr) else 0.0, 1)
        st["avg_period_days"] = fnum(np.mean([x["days"] for x in runs]) if runs else 0.0, 1)
        now_retro = bool(SKY.retro[p][t_i])
        flip = SKY.next_where(SKY.retro[p] != now_retro, t_i)
        st["now"] = "retrograde" if now_retro else "direct"
        st["next_change"] = SKY.date_of(flip) if flip is not None else None
        retro[p] = st

    out = {
        "success": True, "symbol": symbol, "name": name,
        "history_start": pp.start, "history_end": str(pp.dates[-1]), "days": int(pp.n),
        "moon_phase": phase, "paksha": paksha, "nakshatra": nak, "sun_sign": sun, "retrograde": retro,
    }
    out["conclusions"] = conclusions(out)
    out["method"] = ("Same-day close-to-close returns grouped by the sky state at noon UT that day "
                     "(sidereal/Lahiri). t = (bucket mean − all-days mean) ÷ standard error. "
                     "'Significant' must clear a multiple-comparison hurdle (|t| ≥ 2.7 for 8 phases, "
                     "2.9 for 12 signs, 3.2 for 27 nakshatras); 'weak' = |t| ≥ 1.96 only; otherwise noise.")
    return out


# ---------------------------------------------------------------------------
# plain-English conclusions
# ---------------------------------------------------------------------------
def _tag(v: str) -> str:
    return {"significant": "a statistically meaningful edge", "weak": "a weak hint, not reliable",
            "noise": "noise", "too few": "too little data to judge"}.get(v, v)


def _bucket_sentence(sec: Dict, name: str, what: str) -> str:
    rows = [r for r in sec["rows"] if r["n"] > 0]
    b = sec["baseline"]
    best = max(rows, key=lambda r: r["t"])
    worst = min(rows, key=lambda r: r["t"])
    cur = next((r for r in rows if r["label"] == sec.get("current")), None)
    s = (f"Best {what}: {best['label']} — {name} rose on {best['hit_pct']:.0f}% of those days vs "
         f"{b['hit_pct']:.0f}% on average (t {best['t']:+.1f}, {_tag(best['verdict'])}). "
         f"Weakest: {worst['label']} ({worst['hit_pct']:.0f}% up days, t {worst['t']:+.1f}, {_tag(worst['verdict'])}).")
    if cur:
        s += (f" Right now we are in {cur['label']}: historically {cur['hit_pct']:.0f}% up days, "
              f"avg {cur['mean_pct']:+.3f}%/day vs {b['mean_pct']:+.3f}% normal — {_tag(cur['verdict'])}.")
    if best["verdict"] in ("significant", "weak") and best.get("next"):
        s += f" Next {best['label']} window starts {fmt_date(best['next'])}."
    return s


def conclusions(st: Dict) -> Dict[str, str]:
    name = st["name"]
    out = {
        "moon_phase": _bucket_sentence(st["moon_phase"], name, "moon phase"),
        "paksha": "",
        "nakshatra": _bucket_sentence(st["nakshatra"], name, "Moon nakshatra"),
        "sun_sign": "",
    }
    pk = st["paksha"]["rows"]
    if len(pk) == 2 and pk[0]["n"] and pk[1]["n"]:
        wax, wan = pk
        diff_ann = (wax["mean_pct"] - wan["mean_pct"]) * 126
        lead = "waxing (Shukla)" if wax["mean_pct"] >= wan["mean_pct"] else "waning (Krishna)"
        tv = max(abs(wax["t"]), abs(wan["t"]))
        v = "significant" if tv >= Z_CRIT[2] else "weak" if tv >= 1.96 else "noise"
        out["paksha"] = (f"{name} did slightly better in the {lead} fortnight: {wax['hit_pct']:.0f}% vs "
                         f"{wan['hit_pct']:.0f}% up days (≈{abs(diff_ann):.1f}% a year if you only held one half) — "
                         f"{_tag(v)}. We are now in {st['paksha']['current']}.")
    sun = st["sun_sign"]["rows"]
    if sun:
        ranked = sorted([r for r in sun if r.get("months", 0) >= 5], key=lambda r: r["month_mean_pct"])
        if ranked:
            lo, hi = ranked[0], ranked[-1]
            cur = next((r for r in sun if r["label"] == st["sun_sign"]["current"]), None)
            out["sun_sign"] = (
                f"Sankranti seasonality: the strongest solar month for {name} has been Sun in {hi['label']} "
                f"({hi['rashi']}, avg {hi['month_mean_pct']:+.1f}%, up in {hi['month_hit_pct']:.0f}% of {hi['months']} years, "
                f"{_tag(hi['verdict'])}); the weakest Sun in {lo['label']} (avg {lo['month_mean_pct']:+.1f}%, "
                f"{_tag(lo['verdict'])}).")
            if cur:
                out["sun_sign"] += (f" Current month (Sun in {cur['label']}): avg {cur['month_mean_pct']:+.1f}%, "
                                    f"up {cur['month_hit_pct']:.0f}% of years.")
    rparts = []
    for p, r in st["retrograde"].items():
        if "mean_pct" not in r.get("retro", {}):
            continue
        rv, dv = r["retro"], r["direct"]
        better = "better" if rv["mean_pct"] > dv["mean_pct"] else "worse"
        rparts.append(
            f"{p} ℞: {rv['hit_pct']:.0f}% up days vs {dv['hit_pct']:.0f}% when direct "
            f"({better}, {r['vol_ratio']:.2f}× volatility, {_tag(r['verdict'])}); now {r['now']}"
            + (f" until {fmt_date(r['next_change'])}" if r.get("next_change") else "") + ".")
    out["retrograde"] = " ".join(rparts)
    sig = [s for s, v in (("moon phase", st["moon_phase"]), ("nakshatra", st["nakshatra"]), ("sun sign", st["sun_sign"]))
           if any(x["verdict"] == "significant" for x in v["rows"])]
    sig += [f"{p} retrograde" for p, r in st["retrograde"].items() if r.get("verdict") == "significant"]
    out["overall"] = (
        f"Across {st['days']:,} trading days since {st['history_start'][:4]}, the cycles that clear the "
        f"significance bar for {name} are: {', '.join(sig)}. Use them as a mild tilt on timing, never as the reason to trade."
        if sig else
        f"Across {st['days']:,} trading days since {st['history_start'][:4]}, no lunar, solar or retrograde cycle "
        f"gives {name} an edge that survives a multiple-comparison check — treat the cycle calendar as context, "
        f"and let price trend and risk limits drive decisions.")
    return out
