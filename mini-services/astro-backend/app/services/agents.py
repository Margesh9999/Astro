"""
TradingAgents-style multi-agent analysis (v1.3).

Mirrors the role structure and flow of TauricResearch/TradingAgents
(https://github.com/TauricResearch/TradingAgents):

    Analyst Team ──► Researcher Team (Bull ⇄ Bear, N rounds) ──► Research Manager
        │                                                            │
        └──────────────► Trader (concrete plan) ◄────────────────────┘
                              │
                 Risk Management (Aggressive ⇄ Conservative ⇄ Neutral)
                              │
                     Portfolio Manager — final 5-tier rating

Default mode is deterministic: every agent reasons over real data already in
the app (price/technicals, quant stats, Suri astro signal, sky events, dasha,
and — in live mode — Yahoo headlines/fundamentals). Optional LLM narration
(agents_llm) only rewrites the text; ratings and numbers stay rule-based.
Educational only — not financial advice.
"""
from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

RATINGS = ["SELL", "UNDERWEIGHT", "HOLD", "OVERWEIGHT", "BUY"]
ANALYST_WEIGHTS = {"market": 0.30, "fundamentals": 0.20, "sentiment": 0.15, "news": 0.15, "astro": 0.20}
HARD = ("square", "opposition")
SOFT = ("trine", "sextile")


def _num(x, d: float = 0.0) -> float:
    try:
        v = float(x)
        return d if (math.isnan(v) or math.isinf(v)) else v
    except (TypeError, ValueError):
        return d


def _clip(x: float, lo: float = -100.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _stance(score: float, band: float = 12.0) -> str:
    return "bullish" if score >= band else ("bearish" if score <= -band else "neutral")


def rating_for(score: float) -> str:
    if score >= 35: return "BUY"
    if score >= 12: return "OVERWEIGHT"
    if score > -12: return "HOLD"
    if score > -35: return "UNDERWEIGHT"
    return "SELL"


def _lc(t: str) -> str:
    """Lower-case the first letter for mid-sentence use, keeping acronyms (MACD, RSI, OBV)."""
    if t.split(" ")[0] in ("Suri", "Jupiter", "Saturn", "Rahu", "Ketu", "Mars", "Venus", "Mercury"):
        return t
    if len(t) > 1 and t[0].isupper() and not t[1].isupper():
        return t[0].lower() + t[1:]
    return t


def _fmt(x: float) -> str:
    x = _num(x)
    return f"{x:,.2f}" if abs(x) < 1000 else f"{x:,.0f}"


class TradingAgentsEngine:
    """Deterministic TradingAgents pipeline over a context dict (see analyse())."""

    # ------------------------------------------------------------------ analysts
    def _market_analyst(self, c: Dict) -> Dict:
        a = c.get("analytics") or {}
        sig = a.get("signal") or {}
        rsi = _num(a.get("rsi"), 50)
        score = _num(sig.get("score"), 0)
        pts: List[Tuple[int, str]] = []
        for p in (sig.get("pillars") or [])[:8]:
            s = 1 if p.get("stance") == "bullish" else (-1 if p.get("stance") == "bearish" else 0)
            if s:
                pts.append((s, f"{p.get('name')}: {p.get('reading')}"))
        pb = a.get("pct_b")
        if pb is not None:
            pb = _num(pb, 0.5)
            if pb > 0.95: pts.append((-1, f"Price is pressing the upper Bollinger band (%B {pb:.2f}) — stretched short-term"))
            elif pb < 0.05: pts.append((1, f"Price is at the lower Bollinger band (%B {pb:.2f}) — bounce zone"))
        atr = _num(a.get("atr_pct"), 0)
        if not sig:
            report = "Technical pack unavailable — the market analyst falls back to RSI only."
            score = _clip((rsi - 50) * 1.2)
        else:
            report = (f"{sig.get('label', 'Neutral')} technical composite {score:+.0f}/100 "
                      f"({sig.get('n_bull', 0)} bullish vs {sig.get('n_bear', 0)} bearish pillars). "
                      f"RSI {rsi:.0f}, daily ATR ≈{atr:.1f}% of price, regime {a.get('regime', 'n/a')}. "
                      + ("Trend-followers have the edge; buy pullbacks, not breakouts." if score >= 15 else
                         "Sellers control the tape; respect resistance and keep size small." if score <= -15 else
                         "No clear edge from price alone — range tactics beat trend bets."))
        conf = min(0.9, 0.45 + abs(score) / 200 + (0.1 if sig else 0))
        return self._mk("market", "Market (Technical) Analyst", "price trend, momentum, volatility",
                        score, conf, report, pts, ["analytics pack", "RSI/MACD/Bollinger/ATR"])

    def _fundamentals_analyst(self, c: Dict) -> Dict:
        f = c.get("fundamentals") or {}
        st = c.get("stats") or {}
        sharpe = _num(st.get("sharpe"), 0); cagr = _num(st.get("cagr"), 0) * 100
        mdd = _num(st.get("max_drawdown"), 0) * 100; vol = _num(st.get("ann_vol"), 0) * 100
        pts: List[Tuple[int, str]] = []
        if f.get("available"):
            m = f.get("metrics", {})
            score = 0.0
            pe = m.get("trailingPE") or m.get("forwardPE")
            if isinstance(pe, (int, float)):
                if pe < 15: score += 25; pts.append((1, f"Valuation undemanding (P/E {pe:.1f})"))
                elif pe > 35: score -= 20; pts.append((-1, f"Rich valuation (P/E {pe:.1f}) leaves little room for misses"))
            for k, lbl in (("revenueGrowth", "Revenue growth"), ("earningsGrowth", "Earnings growth")):
                g = m.get(k)
                if isinstance(g, (int, float)):
                    if g > 0.08: score += 15; pts.append((1, f"{lbl} {g*100:+.0f}% y/y"))
                    elif g < 0: score -= 15; pts.append((-1, f"{lbl} {g*100:+.0f}% y/y — shrinking"))
            pm = m.get("profitMargins")
            if isinstance(pm, (int, float)):
                if pm > 0.15: score += 10; pts.append((1, f"Healthy profit margin {pm*100:.0f}%"))
                elif pm < 0: score -= 15; pts.append((-1, f"Loss-making (margin {pm*100:.0f}%)"))
            score += _clip(sharpe * 15, -15, 15)
            conf = 0.65
            src = "Yahoo company snapshot + 3-year return profile"
        else:
            # proxy: risk-adjusted return quality
            score = _clip(sharpe * 40 - 10 + (cagr - 6) * 1.2 + (10 if mdd > -20 else -10 if mdd < -35 else 0))
            conf = 0.4
            src = f"{f.get('reason', 'No fundamentals feed')} Using the 3-year return/risk profile as a proxy"
        if sharpe > 0.8: pts.append((1, f"3-year Sharpe {sharpe:.2f} — returns have paid for the risk"))
        elif sharpe < 0.2: pts.append((-1, f"3-year Sharpe only {sharpe:.2f} — poor reward per unit of risk"))
        if mdd < -25: pts.append((-1, f"Worst drawdown {mdd:.0f}% in 3 years — holders must stomach deep dips"))
        if cagr > 8: pts.append((1, f"Compounded {cagr:.1f}% a year over 3 years"))
        report = (f"{src}. CAGR {cagr:+.1f}%/yr, volatility {vol:.0f}%, Sharpe {sharpe:.2f}, max drawdown {mdd:.0f}%. "
                  + ("Quality of returns supports owning it." if score >= 12 else
                     "Return quality is weak — demand a discount before owning more." if score <= -12 else
                     "Middling quality — fine as a core holding, not a conviction add."))
        return self._mk("fundamentals", "Fundamentals Analyst", "valuation & return quality",
                        score, conf, report, pts, ["quant stats (3y)"] + (["yfinance .info"] if f.get("available") else []))

    def _sentiment_analyst(self, c: Dict) -> Dict:
        astro = c.get("astro") or {}
        a = c.get("analytics") or {}
        mood = _num((astro.get("mood") or {}).get("mood_index"), 50)
        perf = c.get("perf") or {}
        m1 = _num(perf.get("1m"), 0)
        rsi = _num(a.get("rsi"), 50)
        volp = _num((astro.get("composite") or {}).get("vol_percentile"), 0.5)
        news = c.get("news") or {}
        score = (mood - 50) * 0.8 + _clip(m1 * 6, -30, 30)
        pts: List[Tuple[int, str]] = []
        if rsi > 75: score -= 15; pts.append((-1, f"Crowd euphoria (RSI {rsi:.0f}) — late buyers usually get shaken out"))
        elif rsi < 25: score += 15; pts.append((1, f"Capitulation-level RSI {rsi:.0f} — sentiment washout often precedes bounces"))
        if volp > 0.8: score -= 8; pts.append((-1, f"Volatility in the {volp*100:.0f}th percentile — nervous crowd"))
        if m1 > 3: pts.append((1, f"Crowd is chasing: {m1:+.1f}% in a month"))
        elif m1 < -3: pts.append((-1, f"Crowd is selling: {m1:+.1f}% in a month"))
        if mood >= 60: pts.append((1, f"Astro market-mood index {mood:.0f}/100 (constructive)"))
        elif mood <= 40: pts.append((-1, f"Astro market-mood index {mood:.0f}/100 (defensive)"))
        if news.get("available"):
            score += _num(news.get("avg_sentiment"), 0) * 30
        score = _clip(score)
        report = ("No social-media feed is connected, so crowd sentiment is inferred from price behaviour "
                  f"(1-month move {m1:+.1f}%, RSI {rsi:.0f}, volatility percentile {volp*100:.0f}) and the astro "
                  f"mood index ({mood:.0f}/100)"
                  + (f", plus headline tone {news.get('avg_sentiment'):+.2f}." if news.get("available") else ".")
                  + (" Mood is supportive." if score >= 12 else " Mood is fragile." if score <= -12 else " Mood is mixed."))
        return self._mk("sentiment", "Sentiment (Social) Analyst", "crowd mood & positioning",
                        score, 0.4, report, pts, ["price-implied sentiment", "Suri mood index"])

    def _news_analyst(self, c: Dict) -> Dict:
        news = c.get("news") or {}
        if not news.get("available"):
            return self._mk("news", "News Analyst", "headlines & macro newsflow", 0.0, 0.0,
                            news.get("reason", "No news feed available — the news analyst abstains."),
                            [], ["yfinance Ticker.news (unavailable)"], abstain=True)
        heads = news.get("headlines", [])
        avg = _num(news.get("avg_sentiment"), 0)
        score = _clip(avg * 100 * min(1.0, len(heads) / 5))
        pts = [(1 if h["sentiment"] > 0 else -1, f"“{h['title'][:110]}” ({h.get('publisher') or 'news'})")
               for h in sorted(heads, key=lambda h: -abs(h["sentiment"])) if h["sentiment"] != 0][:4]
        report = (f"{len(heads)} recent headlines: {news.get('positive', 0)} positive, {news.get('negative', 0)} negative, "
                  f"average tone {avg:+.2f}. "
                  + ("Newsflow is a tailwind." if score >= 12 else "Newsflow is a headwind." if score <= -12
                     else "Newsflow is balanced — no headline edge.")
                  + " (Simple word-list scoring — read the headlines yourself before acting.)")
        return self._mk("news", "News Analyst", "headlines & macro newsflow", score,
                        0.35 + min(0.3, len(heads) * 0.04), report, pts, ["yfinance Ticker.news"],
                        extra={"headlines": heads})

    def _astro_analyst(self, c: Dict) -> Dict:
        astro = c.get("astro") or {}
        comp = astro.get("composite") or {}
        a_score = _num(comp.get("astro_score"), 0)
        composite = _num(comp.get("composite"), 0)
        events = c.get("events") or []
        near = [e for e in events if _num(e.get("days_ahead"), 99) <= 14 and e.get("type") in HARD + SOFT]
        hard = sum(1 for e in near if e.get("type") in HARD)
        soft = sum(1 for e in near if e.get("type") in SOFT)
        alerts = astro.get("timing_alerts") or []
        d = c.get("dasha") or {}
        fav = _num(d.get("favour"), 1.0)
        score = _clip(0.55 * a_score + 0.25 * composite + (soft - hard) * 6 + (fav - 1.0) * 60)
        pts: List[Tuple[int, str]] = []
        if a_score > 10: pts.append((1, f"Suri astro score {a_score:+.0f} — planetary backdrop supportive"))
        elif a_score < -10: pts.append((-1, f"Suri astro score {a_score:+.0f} — planetary backdrop hostile"))
        if hard: pts.append((-1, f"{hard} hard aspect(s) (square/opposition) in the next 14 days — reversal & gap risk"))
        if soft: pts.append((1, f"{soft} flowing aspect(s) (trine/sextile) in the next 14 days — trend continuation"))
        if alerts: pts.append((-1, f"{len(alerts)} timing window(s): {', '.join(x.get('date', '') for x in alerts[:3])} — avoid fresh entries ±1 day"))
        if d.get("md"):
            pts.append((1 if fav > 1.02 else (-1 if fav < 0.98 else 0),
                        f"Running {d.get('md')}–{d.get('ad')} dasha (favour ×{fav:.2f})"))
        pts = [p for p in pts if p[0] != 0]
        report = (f"Astro-technical composite {composite:+.1f} ({comp.get('zone', 'Neutral')}), astro score {a_score:+.0f}, "
                  f"{len(alerts)} timing alert(s) and {len(near)} major aspect(s) in 14 days"
                  + (f"; the native's {d.get('md')}/{d.get('ad')}/{d.get('pd') or '-'} dasha is running." if d.get("md") else ".")
                  + " Use this for timing, not direction alone.")
        return self._mk("astro", "Astro Analyst", "planetary timing, sky events & dasha", score, 0.35,
                        report, pts, ["Suri composite", "45-day sky events", "Vimshottari dasha"])

    @staticmethod
    def _mk(key, name, role, score, conf, report, pts, data, abstain=False, extra=None) -> Dict:
        score = round(_clip(_num(score)), 1)
        out = {"key": key, "agent": name, "role": role, "team": "Analyst Team",
               "stance": "abstain" if abstain else _stance(score), "score": score,
               "confidence": round(max(0.0, min(1.0, conf)), 2), "abstain": abstain,
               "report": report, "view": report,
               "key_points": [{"sign": s, "text": t} for s, t in pts],
               "data_used": data}
        if extra: out.update(extra)
        return out

    # ------------------------------------------------------------------ researchers
    def _debate(self, analysts: List[Dict], rounds: int, name: str) -> Dict:
        bull_pts, bear_pts = [], []
        for a in analysts:
            w = ANALYST_WEIGHTS.get(a["key"], 0.1) * (0.5 + a["confidence"])
            for p in a["key_points"]:
                (bull_pts if p["sign"] > 0 else bear_pts).append((w, a["agent"], p["text"]))
        bull_pts.sort(key=lambda x: -x[0]); bear_pts.sort(key=lambda x: -x[0])
        if not bull_pts: bull_pts = [(0.05, "Bull Researcher", f"Nothing structural is broken in {name}; long-run markets drift up")]
        if not bear_pts: bear_pts = [(0.05, "Bear Researcher", "Calm tapes breed complacency; every trend eventually meets a shock")]
        transcript = []
        for r in range(rounds):
            b = bull_pts[r % len(bull_pts)]; s = bear_pts[r % len(bear_pts)]
            b2 = bull_pts[(r + 1) % len(bull_pts)]; s2 = bear_pts[(r + 1) % len(bear_pts)]
            bull_txt = (f"{b[2]} (from the {b[1]})." if r == 0 else
                        f"My opponent stresses “{transcript[-1]['bear']['point']}”, but that is already in the price — "
                        f"meanwhile {_lc(b[2])} (from the {b[1]}).")
            if r == 0:
                bull_txt += f" Add to that: {_lc(b2[2])}." if b2 is not b else ""
            bear_txt = (f"The bull ignores risk: {_lc(s[2])} (from the {s[1]})."
                        + (f" And {_lc(s2[2])}." if s2 is not s and r == 0 else "")
                        if r == 0 else
                        f"“{b[2]}” sounds good, yet {_lc(s[2])} (from the {s[1]}) — "
                        "that is how good stories become drawdowns.")
            transcript.append({"round": r + 1,
                               "bull": {"text": bull_txt, "point": b[2][:80]},
                               "bear": {"text": bear_txt, "point": s[2][:80]}})
        bull_strength = round(sum(x[0] for x in bull_pts) * 100, 1)
        bear_strength = round(sum(x[0] for x in bear_pts) * 100, 1)
        return {"rounds": transcript, "bull_strength": bull_strength, "bear_strength": bear_strength,
                "bull_points": len(bull_pts), "bear_points": len(bear_pts)}

    # ------------------------------------------------------------------ main
    def analyse(self, symbol: str, symbol_name: str, ctx: Dict, rounds: int = 2,
                capital: float = 50000.0) -> Dict:
        rounds = max(1, min(3, int(rounds or 2)))
        analysts = [self._market_analyst(ctx), self._fundamentals_analyst(ctx),
                    self._sentiment_analyst(ctx), self._news_analyst(ctx), self._astro_analyst(ctx)]
        active = [a for a in analysts if not a["abstain"]]
        wsum = sum(ANALYST_WEIGHTS[a["key"]] for a in active) or 1.0
        composite = sum(ANALYST_WEIGHTS[a["key"]] * a["score"] for a in active) / wsum

        # Researcher team
        debate = self._debate(active, rounds, symbol_name)
        tilt = debate["bull_strength"] - debate["bear_strength"]
        research_score = _clip(composite * 0.8 + _clip(tilt, -30, 30) * 0.4)
        rm_call = "BUY" if research_score >= 12 else ("SELL" if research_score <= -12 else "HOLD")
        winner = "bull" if tilt > 3 else ("bear" if tilt < -3 else "neither side")
        research_manager = {
            "agent": "Research Manager", "team": "Researcher Team",
            "recommendation": rm_call, "score": round(research_score, 1),
            "view": (f"After {rounds} round(s), the {winner} made the stronger evidence-weighted case "
                     f"(bull {debate['bull_strength']:.0f} vs bear {debate['bear_strength']:.0f}). "
                     f"Analyst composite {composite:+.0f}/100 → research recommendation {rm_call}. "
                     + ("Investment plan: build exposure in tranches and let the trader time entries." if rm_call == "BUY" else
                        "Investment plan: reduce exposure into strength; protect capital first." if rm_call == "SELL" else
                        "Investment plan: hold core, harvest income, wait for a clearer edge.")),
        }

        # Trader
        trader = self._trader(symbol_name, ctx, rm_call, research_score, capital)

        # Risk team
        risk = self._risk_team(ctx, trader, research_score)

        # Portfolio manager
        a = ctx.get("analytics") or {}
        vol_ratio = _num(a.get("vol_ratio"), 1.0)
        final = research_score * (0.8 if vol_ratio > 1.3 else 1.0) + risk["score_adjust"]
        final = round(_clip(final), 1)
        rating = rating_for(final)
        signs = [1 if x["score"] > 5 else (-1 if x["score"] < -5 else 0) for x in active]
        agree = (sum(1 for s in signs if s == (1 if final > 0 else -1)) / len(signs)) if signs and final != 0 else 0.5
        confidence = int(max(30, min(90, 38 + abs(final) * 0.45 + agree * 22 - (5 * (5 - len(active))))))
        mult = {"BUY": risk["views"][0]["size_mult"] * 0.5 + risk["views"][1]["size_mult"] * 0.5,
                "OVERWEIGHT": risk["views"][1]["size_mult"],
                "HOLD": risk["views"][2]["size_mult"],
                "UNDERWEIGHT": risk["views"][2]["size_mult"], "SELL": 0.0}[rating]
        units = trader.get("size_units", 0) * mult
        final_plan = dict(trader)
        final_plan["size_units"] = round(units, 2)
        final_plan["size_value"] = round(units * _num(trader.get("entry_mid")), 0)
        final_plan["size_pct_capital"] = round(final_plan["size_value"] / capital * 100, 1) if capital else 0
        pm_view = (f"Rating {rating} with {confidence}% confidence (final score {final:+.0f}/100). "
                   f"I take the research manager's {rm_call} call, apply the risk team's "
                   f"{'neutral' if rating in ('OVERWEIGHT',) else 'blended' if rating == 'BUY' else 'conservative'} sizing "
                   f"(×{mult:.2f})" + (" and haircut conviction because volatility is elevated" if vol_ratio > 1.3 else "")
                   + ". " + self._pm_action(rating, symbol_name, final_plan))
        portfolio_manager = {"agent": "Portfolio Manager", "team": "Portfolio Management", "rating": rating,
                             "score": final, "confidence": confidence, "size_multiplier": round(mult, 2),
                             "final_plan": final_plan, "view": pm_view}

        plain = self._plain_english(symbol_name, rating, confidence, final_plan, active, ctx)

        legacy_agents = [{"agent": x["agent"], "role": x["role"], "stance": x["stance"], "view": x["report"]}
                         for x in analysts]
        return {
            "success": True, "symbol": symbol, "symbol_name": symbol_name,
            "mode": "rules", "llm_available": False, "rounds": rounds, "capital": capital,
            "spot": _num(ctx.get("spot")),
            "flow": ["Analyst Team", "Researcher Team", "Research Manager", "Trader",
                     "Risk Management", "Portfolio Manager"],
            "analysts": analysts,
            "analyst_composite": round(composite, 1),
            "debate": debate,
            "research_manager": research_manager,
            "trader": trader,
            "risk_team": risk,
            "portfolio_manager": portfolio_manager,
            "decision": {"rating": rating, "confidence": confidence, "score": final},
            "plain_english": plain,
            "news": ctx.get("news") or {},
            # backward-compatible fields (v1.2 card)
            "agents": legacy_agents,
            "manager": {"verdict": rating, "score": final, "view": pm_view},
            "inspired_by": "TauricResearch/TradingAgents — multi-agent LLM trading framework (role structure & flow)",
            "inspired_by_url": "https://github.com/TauricResearch/TradingAgents",
            "disclaimer": ("Deterministic rule-based re-implementation of the TradingAgents roles, computed from the "
                           "data in this app. Educational only — not financial advice."),
        }

    # ------------------------------------------------------------------ trader
    def _trader(self, name: str, c: Dict, call: str, score: float, capital: float) -> Dict:
        a = c.get("analytics") or {}
        spot = _num(c.get("spot")) or _num(a.get("last"), 0)
        sigma = _num(a.get("sigma_pct"), 1.2) / 100 or 0.012
        lv = {x.get("level"): _num(x.get("value")) for x in (a.get("levels") or [])}
        s20, s50, s200 = lv.get("SMA 20", spot), lv.get("SMA 50", spot), lv.get("SMA 200", spot)
        hi52, lo52 = lv.get("52-week high", spot * 1.1), lv.get("52-week low", spot * 0.9)
        h = math.sqrt(10)  # ~2-week swing horizon
        alerts = [x.get("date") for x in ((c.get("astro") or {}).get("timing_alerts") or [])[:4]]
        supports = sorted([v for v in (s20, s50, s200, lo52) if 0 < v < spot], reverse=True)
        if call == "BUY" or (call == "HOLD" and score >= 0):
            e_hi = spot * (1 - 0.3 * sigma * h)
            e_lo = max(spot * (1 - 1.2 * sigma * h), supports[0] if supports else 0)
            if e_lo >= e_hi: e_lo = e_hi * (1 - 0.6 * sigma * h)
            stop = min(e_lo * (1 - 0.8 * sigma * h), (supports[1] if len(supports) > 1 else e_lo) * 0.99)
            t1 = spot * (1 + 1.0 * sigma * h)
            t2 = max(t1 * 1.01, min(hi52, spot * (1 + 2.2 * sigma * h)) if hi52 > t1 else spot * (1 + 2.2 * sigma * h))
            action = "BUY in tranches" if call == "BUY" else "HOLD core / buy only at the entry zone"
            direction = "long"
        elif call == "SELL":
            e_lo = spot * (1 + 0.2 * sigma * h); e_hi = spot * (1 + 1.0 * sigma * h)
            stop = e_hi * (1 + 0.8 * sigma * h)
            t1 = spot * (1 - 1.0 * sigma * h); t2 = max(lo52, spot * (1 - 2.2 * sigma * h))
            action = "SELL / trim into bounces"
            direction = "reduce"
        else:
            e_hi = spot * (1 - 0.5 * sigma * h); e_lo = spot * (1 - 1.3 * sigma * h)
            stop = e_lo * (1 - 0.8 * sigma * h)
            t1 = spot * (1 + 0.8 * sigma * h); t2 = spot * (1 + 1.6 * sigma * h)
            action = "HOLD — sell premium around the position"
            direction = "neutral"
        entry_mid = (e_lo + e_hi) / 2
        risk_per_unit = abs(entry_mid - stop) or spot * 0.02
        risk_budget = capital * 0.01
        units = risk_budget / risk_per_unit
        units = min(units, capital * 0.20 / max(entry_mid, 1e-9))
        rr = abs(t1 - entry_mid) / risk_per_unit if risk_per_unit else 0
        view = (f"{action}. Entry zone {_fmt(e_lo)}–{_fmt(e_hi)}, protective stop {_fmt(stop)}, "
                f"targets {_fmt(t1)} then {_fmt(t2)} (reward:risk ≈ {rr:.1f}:1 to T1). Risking 1% of "
                f"£{capital:,.0f} gives about {units:,.2f} units (≈£{units * entry_mid:,.0f}, capped at 20% of capital)."
                + (f" Avoid opening new risk on {', '.join(alerts[:3])} (astro timing windows)." if alerts else ""))
        return {"agent": "Trader", "team": "Trader", "action": action, "direction": direction,
                "entry_low": round(e_lo, 2), "entry_high": round(e_hi, 2), "entry_mid": round(entry_mid, 2),
                "stop": round(stop, 2), "target_1": round(t1, 2), "target_2": round(t2, 2),
                "reward_risk": round(rr, 2), "size_units": round(units, 2),
                "size_value": round(units * entry_mid, 0), "risk_budget": round(risk_budget, 0),
                "avoid_dates": alerts, "horizon": "2–6 weeks", "view": view}

    # ------------------------------------------------------------------ risk team
    def _risk_team(self, c: Dict, trader: Dict, score: float) -> Dict:
        a = c.get("analytics") or {}
        st = c.get("stats") or {}
        rk = c.get("risk") or {}
        vol_ratio = _num(a.get("vol_ratio"), 1.0)
        var = _num(rk.get("var_hist_pct"), 0.015) * 100
        mdd = _num(st.get("max_drawdown"), -0.2) * 100
        events = c.get("events") or []
        hard = sum(1 for e in events if _num(e.get("days_ahead"), 99) <= 21 and e.get("type") in HARD)
        agg_mult = 1.5 if vol_ratio < 1.1 else 1.25
        con_mult = 0.5 if (vol_ratio > 1.2 or hard >= 2) else 0.65
        views = [
            {"agent": "Aggressive Risk Analyst", "stance": "aggressive", "size_mult": agg_mult,
             "view": (f"Reward:risk of {trader['reward_risk']:.1f}:1 justifies pressing: scale to ×{agg_mult:.2f} the base size "
                      f"and hold for target 2. Daily VaR of {var:.1f}% is the cost of admission, not a reason to sit out.")},
            {"agent": "Neutral Risk Analyst", "stance": "neutral", "size_mult": 1.0,
             "view": (f"Keep the trader's 1%-risk size (×1.00). Take half off at target 1, trail the rest. "
                      f"Volatility is {vol_ratio:.1f}× normal" + (" — fine." if vol_ratio <= 1.2 else " — tighten trailing stops."))},
            {"agent": "Conservative Risk Analyst", "stance": "conservative", "size_mult": con_mult,
             "view": (f"History shows a {mdd:.0f}% drawdown and {hard} hard sky aspect(s) in three weeks. Cut to ×{con_mult:.2f}, "
                      "enter only after a confirmation close, and consider a protective put or collar on any core holding.")},
        ]
        adjust = -4.0 if (vol_ratio > 1.3 or hard >= 2) else (2.0 if vol_ratio < 0.85 and score > 0 else 0.0)
        summary = (f"The aggressive analyst wants ×{agg_mult:.2f}, the conservative ×{con_mult:.2f}; the neutral analyst "
                   f"anchors at ×1.00. " + ("Risk conditions argue for caution." if adjust < 0 else
                                            "Calm conditions allow normal sizing." if adjust >= 0 else ""))
        return {"team": "Risk Management", "views": views, "score_adjust": adjust, "summary": summary}

    @staticmethod
    def _pm_action(rating: str, name: str, p: Dict) -> str:
        if rating in ("BUY", "OVERWEIGHT"):
            return (f"Build {name} in 2–3 tranches inside {_fmt(p['entry_low'])}–{_fmt(p['entry_high'])}, stop {_fmt(p['stop'])}, "
                    f"targets {_fmt(p['target_1'])}/{_fmt(p['target_2'])}; total ≈£{p['size_value']:,.0f}.")
        if rating == "HOLD":
            return (f"Keep existing {name} exposure, add only near {_fmt(p['entry_low'])}, and sell covered calls / "
                    f"cash-secured puts around the range; hard stop {_fmt(p['stop'])}.")
        if rating == "UNDERWEIGHT":
            return f"Trim {name} toward a small core, hedge the rest, and don't add until the score turns positive."
        return f"Exit or hedge {name}; re-assess after the next major sky event or a close back above key averages."

    @staticmethod
    def _plain_english(name: str, rating: str, conf: int, p: Dict, active: List[Dict], c: Dict) -> str:
        best = max(active, key=lambda x: x["score"]) if active else None
        worst = min(active, key=lambda x: x["score"]) if active else None
        what = {
            "BUY": "the team thinks the odds favour owning more",
            "OVERWEIGHT": "the team leans positive but wants you to add gradually",
            "HOLD": "the team sees no strong edge either way",
            "UNDERWEIGHT": "the team leans negative and would hold less than usual",
            "SELL": "the team thinks the risks outweigh the rewards right now",
        }[rating]
        txt = (f"In simple terms: for {name}, {what} ({rating}, {conf}% confidence). "
               + (f"The most positive voice is the {best['agent']} ({best['score']:+.0f}); " if best else "")
               + (f"the most worried is the {worst['agent']} ({worst['score']:+.0f}). " if worst else ""))
        if rating in ("BUY", "OVERWEIGHT", "HOLD") and p.get("direction") != "reduce":
            txt += (f"If you act, buy only between {_fmt(p['entry_low'])} and {_fmt(p['entry_high'])}, "
                    f"exit if it closes below {_fmt(p['stop'])}, and take profits near {_fmt(p['target_1'])}. ")
        else:
            txt += f"If you hold it, consider reducing into rallies toward {_fmt(p['entry_high'])} and keep a stop at {_fmt(p['stop'])}. "
        if p.get("avoid_dates"):
            txt += f"Don't open new trades on {', '.join(p['avoid_dates'][:2])}. "
        txt += "This is an educational simulation, not advice — never risk money you can't afford to lose."
        return txt

    # ------------------------------------------------------------------ LLM narration
    def apply_llm(self, result: Dict) -> Dict:
        """Rewrite agent texts with Claude when available; numbers unchanged."""
        from app.services import agents_llm
        result["llm_available"] = agents_llm.available()
        if not result["llm_available"]:
            return result
        items = [{"key": f"a:{i}", "role": a["agent"], "text": a["report"]}
                 for i, a in enumerate(result["analysts"]) if not a["abstain"]]
        items += [{"key": "rm", "role": "Research Manager", "text": result["research_manager"]["view"]},
                  {"key": "tr", "role": "Trader", "text": result["trader"]["view"]},
                  {"key": "pm", "role": "Portfolio Manager", "text": result["portfolio_manager"]["view"]},
                  {"key": "pe", "role": "Plain-English explainer for a beginner", "text": result["plain_english"]}]
        for r in result["debate"]["rounds"]:
            items.append({"key": f"b:{r['round']}", "role": "Bull Researcher", "text": r["bull"]["text"]})
            items.append({"key": f"s:{r['round']}", "role": "Bear Researcher", "text": r["bear"]["text"]})
        out = agents_llm.narrate(items)
        if not out:
            result["mode"] = "rules (LLM unavailable — fell back)"
            return result
        for k, txt in out.items():
            if k.startswith("a:"):
                a = result["analysts"][int(k[2:])]; a["report"] = a["view"] = txt
            elif k == "rm": result["research_manager"]["view"] = txt
            elif k == "tr": result["trader"]["view"] = txt
            elif k == "pm": result["portfolio_manager"]["view"] = txt; result["manager"]["view"] = txt
            elif k == "pe": result["plain_english"] = txt
            elif k[:2] in ("b:", "s:"):
                rnd = next(r for r in result["debate"]["rounds"] if r["round"] == int(k[2:]))
                rnd["bull" if k[0] == "b" else "bear"]["text"] = txt
        result["mode"] = f"llm ({agents_llm.MODEL} narration, rule-based numbers)"
        return result
