"""
TradingAgents-inspired multi-agent analysis (T11).

A deterministic, rule-based reimplementation of the TradingAgents pattern:
several specialist "agents" examine the selected symbol from different angles,
a bull and a bear researcher debate, a risk manager adds guardrails, and a
fund manager produces the final plain-English verdict. No LLM calls — the
reasoning is generated from live quant stats + astro signal so it always
reflects current data and runs offline.
"""
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


def _dir_word(x: float) -> str:
    return "up" if x > 0.5 else ("down" if x < -0.5 else "sideways")


class TradingAgentsEngine:
    """Compose agent opinions from observed data (quant + astro)."""

    def analyse(self, symbol: str, symbol_name: str, stats: Dict, astro: Dict,
                events: List[Dict]) -> Dict:
        perf = stats.get("performance", {})
        ret1y = perf.get("1y", 0.0) or 0.0
        rsi = astro.get("composite", {}).get("rsi14", 50)
        vol = astro.get("composite", {}).get("vol20_annualised", 0.2) * 100
        mood = astro.get("mood", {}).get("mood_index", 50)
        composite = astro.get("composite", {}).get("composite", 0)
        zone = astro.get("composite", {}).get("zone", "Neutral")
        n_alerts = len(astro.get("timing_alerts", []))
        dd = stats.get("risk", {}).get("max_drawdown_pct", -15.0)
        var95 = stats.get("risk", {}).get("var_95", 0.0)

        agents: List[Dict] = []

        # 1. Technical analyst
        if rsi >= 65 and ret1y > 10:
            tech = (f"Momentum is hot: RSI {rsi:.0f} with a +{ret1y:.0f}% year. Great trend, "
                    "crowded longs — entries should come from pullbacks, not breakouts.")
            stance = "bullish-cautious"
        elif rsi <= 35:
            tech = (f"RSI {rsi:.0f} says the selloff is stretched. Mean-reversion bounces are common "
                    "from here, but only with confirmation candles.")
            stance = "contrarian-bullish"
        else:
            tech = f"RSI {rsi:.0f} and {vol:.0f}% volatility — a balanced tape where swing ranges dominate."
            stance = "neutral"
        agents.append({"agent": "Technical Analyst", "role": "price structure & momentum",
                       "stance": stance, "view": tech})

        # 2. Fundamental / regime analyst
        fund = (f"{symbol_name} returned {ret1y:+.1f}% over the last year with a worst drawdown of "
                f"{dd:.1f}%. {'The regime has been rewarding trend-followers.' if ret1y > 8 else 'Returns have been grindy — regime favours mean-reversion income strategies.'}")
        agents.append({"agent": "Fundamental Analyst", "role": "regime & returns context",
                       "stance": "constructive" if ret1y > 8 else "selective", "view": fund})

        # 3. Astro analyst
        astro_view = (f"Market mood index reads {mood:.0f}/100 ({astro.get('mood', {}).get('mood_label', 'n/a')}) and the "
                      f"astro-technical composite is {composite:+.1f} ({zone}). {n_alerts} planetary timing "
                      f"window(s) land in the next 14 days — plan entries around them, not through them.")
        agents.append({"agent": "Astro Analyst", "role": "planetary timing & sentiment",
                       "stance": "bullish" if composite > 15 else ("bearish" if composite < -15 else "neutral"),
                       "view": astro_view})

        # 4 & 5. Bull vs Bear researchers
        bull = (f"Case for upside: the {ret1y:+.1f}% yearly trend plus mood {mood:.0f}/100 suggest dips keep "
                f"getting bought. Plan: buy staged entries near the 50-day average; add if the composite stays above +15.")
        bear = (f"Case for downside: volatility {vol:.0f}%, a {dd:.1f}% historical drawdown and {n_alerts} astro "
                f"reversal windows mean sharp shakes are plausible. Plan: keep stops below recent swing lows and "
                f"cap any single position at 10% of capital.")
        agents.append({"agent": "Bull Researcher", "role": "optimist brief", "stance": "bullish", "view": bull})
        agents.append({"agent": "Bear Researcher", "role": "risk brief", "stance": "bearish", "view": bear})

        # 6. Risk manager
        risk = (f"95% one-day VaR is ${var95:,.0f} on a £100k book. Position size so that 3 consecutive "
                f"losing days never exceeds 5% of capital. {'Reduce size while volatility is elevated.' if vol > 25 else 'Standard sizing is acceptable.'}")
        agents.append({"agent": "Risk Manager", "role": "capital protection",
                       "stance": "guarded", "view": risk})

        # 7. Fund manager verdict
        score = 0.0
        score += 15 if ret1y > 8 else (-10 if ret1y < -5 else 0)
        score += 15 if composite > 15 else (-15 if composite < -15 else 0)
        score += 10 if mood > 60 else (-10 if mood < 40 else 0)
        score += 5 if rsi < 35 else (-5 if rsi > 70 else 0)
        if score >= 20:
            verdict, action = "ACCUMULATE", (f"Add to {symbol_name} in 2–3 staged entries over the next two weeks; "
                                             "hold a trailing stop below the 50-day average.")
        elif score <= -15:
            verdict, action = "DEFEND", (f"Trim {symbol_name} exposure to core holdings, sell covered calls into "
                                         "any bounces and keep dry powder for lower prices.")
        else:
            verdict, action = "HOLD & HARVEST", (f"Keep {symbol_name} core intact and harvest income around it "
                                                 "(credit spreads / covered calls) while the composite stays neutral.")
        manager = (f"Aggregate score {score:+.0f} → {verdict}. {action} Re-run this analysis after every "
                   f"major astro alert or a ±3% move in the stock.")

        return {
            "success": True,
            "symbol": symbol,
            "symbol_name": symbol_name,
            "agents": agents,
            "manager": {"verdict": verdict, "score": score, "view": manager},
            "disclaimer": "Rule-based agent simulation inspired by TradingAgents — educational only, not financial advice.",
        }
