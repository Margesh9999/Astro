"""
Repo concept coverage matrix (v1.3 re-audit).

Every meaningful rule / model / strategy / chart from the audited
open-source quant repositories, mapped to WHERE it lives in AstroTrader
(exact card → tab) and what it means for a trader in plain English.

Status is deliberately honest:
  implemented — the product really computes and shows it today;
  partial     — a simplified or adjacent version exists (the note says what is missing);
  reference   — documented only (needs a data feed, account or model we don't ship).
"""
from typing import Dict, List

QD = "Quant Desk → "
OL = "Options Lab → "


def c(name: str, status: str, where: str, meaning: str) -> Dict:
    return {"name": name, "status": status, "where": where, "meaning": meaning}


REPOS: List[Dict] = [
    {"repo": "gs-quant", "url": "https://github.com/goldmansachs/gs-quant", "concepts": [
        c("VaR / CVaR risk measures", "implemented", QD + "Risk & Regime (VaR table) + Overview",
          "How much a bad day (95%/99%) can cost you — size positions before you trade, not after."),
        c("Timeseries toolkit (returns, vol, z-scores, moving averages, drawdowns)", "implemented", QD + "Trend Charts / Risk & Regime",
          "The building blocks every chart on the desk is made from."),
        c("Rolling beta & correlation (ts.beta / ts.correlation)", "implemented", QD + "Risk & Regime → Market sensitivity",
          "How strongly the stock follows the market — tells you whether index hedges will actually protect it."),
        c("Backtesting framework (triggers → actions)", "partial", QD + "Signals (vectorised) + Walk-Forward Backtest card",
          "Replays rules on history; we ship vectorised long-or-cash tests, not gs-quant's event engine."),
        c("Scenario / shock analysis", "partial", OL + "Strategy Lab scenario matrix; " + QD + "Risk & Regime MC cone",
          "What happens to P/L if price and volatility jump — explicit market-wide shock scenarios are not modelled."),
        c("Option greeks (Delta, Gamma, Vega, Theta)", "implemented", OL + "Pricer",
          "How the option price reacts to price, time and volatility moves."),
        c("Implied volatility surface", "partial", OL + "Pricer (IV solver + SABR smile)",
          "Single-expiry smile only; a full strike × expiry surface needs a live chain feed."),
        c("Portfolio construction & hedge optimiser", "partial", QD + "Portfolio",
          "Basket weights by min-var / max-Sharpe / risk parity / HRP; gs-quant's hedge optimiser is not replicated."),
        c("Rates/FX instrument pricing (IRSwap, Swaption, FX options) & DV01", "reference", "Requires GS Marquee account",
          "Interest-rate desk tooling — out of scope for a single-stock retail desk."),
        c("Marquee datasets API", "reference", "Requires GS Marquee account", "Institutional data catalogue — not available publicly."),
    ]},

    {"repo": "OpenBBTerminal", "url": "https://github.com/OpenBB-finance/OpenBBTerminal", "concepts": [
        c("stocks/load — historical data for any ticker", "implemented", "Instrument picker (352 symbols) + full history on every card",
          "Pick any stock, ETF, index, fund, FX pair or coin and every analysis reloads on its full history."),
        c("stocks/candle — candlestick chart", "partial", QD + "Trend Charts (close + MAs); Heikin-Ashi rule in Signals",
          "We draw close-price lines with moving averages; a full OHLC candle chart is not drawn."),
        c("stocks/quote — live quote", "implemented", "Market card", "Latest price, change and range at a glance."),
        c("stocks/news — headlines", "partial", "AI Agents → News analyst (when live headlines are available)",
          "Headline tone feeds one agent's vote; there is no standalone news reader."),
        c("stocks/dd — due diligence (analyst targets, SEC filings)", "reference", "No analyst/filings feed",
          "Broker ratings and filings need a paid data source."),
        c("stocks/fa — fundamental analysis (statements, ratios, DCF)", "partial", "AI Agents → Fundamentals analyst (key ratios when live)",
          "Basic valuation ratios inform the agents; full statements and DCF are not shown."),
        c("stocks/ta — technical analysis suite", "implemented", QD + "Signals, Momentum & Vol, Volume & Memory",
          "24 classic indicators, each with today's signal, a full-history backtest and a plain-English verdict."),
        c("stocks/qa — quantitative analysis (summary, normality, unit root, rolling stats, CAPM, VaR, ES)", "implemented",
          QD + "Risk & Regime + Overview",
          "Textbook statistics that tell you how wild, how predictable and how market-linked the asset is."),
        c("stocks/pred — ML price prediction", "implemented", "Model Lab + " + QD + "Forecast",
          "Many models are trained and ranked so the honest best one speaks first."),
        c("stocks/ba — behavioural / social sentiment (Reddit, Twitter, StockTwits)", "partial", "AI Agents → Sentiment analyst",
          "A sentiment score feeds the agents; raw social-media feeds are not pulled."),
        c("stocks/ca — comparison analysis (correlation, historical vs peers)", "implemented",
          QD + "Correlations, Heatmaps (rolling correlation) and Portfolio (peer basket)",
          "Shows what the stock moves with and which assets diversify it."),
        c("stocks/disc — discovery (gainers, trending)", "reference", "No market-wide scan feed", "Market-wide movers lists need a live scanner."),
        c("stocks/screener", "partial", "Instrument picker (filter by market / type / options)",
          "Filter the universe by market and asset type; fundamental screens are not available."),
        c("stocks/options — chain, greeks, IV, payoff", "implemented", OL + "Option Chain, Pricer, Strategy Lab",
          "Everything needed to design an options trade and see its payoff before placing it."),
        c("stocks/options — vol surface, max pain, put/call ratio", "reference", "Needs full live chains across expiries",
          "Crowd-positioning views; not computed today."),
        c("stocks/insider — insider trading", "reference", "No insider-filings feed", "Insider buying clusters can be bullish; data not wired."),
        c("stocks/gov — congress trading & lobbying", "reference", "No government-trading feed", "US-specific alternative data; not wired."),
        c("stocks/dps — dark pools & short interest", "reference", "No short-interest feed", "Crowded shorts can fuel squeezes; data not wired."),
        c("stocks/sia — sector & industry analysis", "partial", "Instrument universe sector tags + " + QD + "Portfolio sector peers",
          "Peers from the same sector are used for the basket; sector-wide statistics are not shown."),
        c("stocks/th — trading hours across exchanges", "reference", "Not shown", "Which exchanges are open now — informational only."),
        c("stocks/bt — simple strategy backtests (EMA, EMA cross, RSI)", "implemented", QD + "Signals (all 24 rules backtested)",
          "Shows whether a simple rule would have beaten buy-and-hold on this exact symbol."),
        c("crypto menu", "partial", "Crypto symbols in the universe get every Quant Desk analysis",
          "Price-based analytics work for BTC/ETH/SOL; on-chain and DeFi data are not wired."),
        c("etf menu", "partial", "ETFs in the universe get every Quant Desk analysis", "ETF holdings/weights lookups are not wired."),
        c("forex menu", "partial", "FX pairs in the universe; GBP/USD in the correlation heatmap", "Price analytics only; forward curves are not wired."),
        c("economy menu (CPI, GDP, yield curve, macro calendar)", "partial", QD + "Heatmaps → correlation with US 10y yield & VIX",
          "Macro links shown via yields and VIX; macro data series themselves are not plotted."),
        c("fixedincome menu (treasury rates, bond maths)", "partial", "Bond analytics API (/bond) + ^TNX in the correlation heatmap",
          "Bond price/duration/convexity is computed server-side; no dashboard panel yet."),
        c("alternative menu (covid, open-source, real estate)", "reference", "Not wired", "Niche alternative datasets — out of scope."),
        c("portfolio menu (holdings, performance, attribution)", "partial", QD + "Portfolio (model basket metrics)",
          "Return, vol, Sharpe, drawdown and risk contributions for a model basket; your own holdings cannot be uploaded yet."),
        c("portfolio/po — mean-variance, max-Sharpe, risk parity, HRP, efficient frontier", "implemented", QD + "Portfolio",
          "Six ways to split money across a basket and the efficient frontier that shows the best risk/return trade-off."),
        c("portfolio/po — Black-Litterman, HERC, NCO, max-diversification", "reference", "Not implemented",
          "Advanced allocators that blend views or nested clusters — documented only."),
        c("forecast — statistical models (naive, drift, SES, Holt, ARIMA, Theta)", "implemented", QD + "Forecast → statistical baselines",
          "Six classical forecasts with an honest backtest showing whether any beat 'no change'."),
        c("forecast — deep-learning models (RNN, N-BEATS, TFT, TCN, NHITS)", "partial", "Model Lab (gradient boosting / linear zoo)",
          "We ship tree and linear models; deep-learning forecasters are documented only."),
        c("quantitative menu (rolling stats, normality, unit root, Omega/Sortino)", "implemented", QD + "Risk & Regime + Overview",
          "Same toolkit as stocks/qa applied to any asset."),
        c("reports — automated research reports", "partial", "Final Strategy card + narrative on every chart",
          "Each chart writes its own sentences; there is no PDF report export."),
        c("dashboards", "implemented", "This AstroTrader dashboard", "All analytics in one interactive page."),
        c("econometrics — normality, unit root, OLS regression", "implemented", QD + "Risk & Regime → Statistical health checks + beta (OLS)",
          "Tells you whether price behaves like a random walk and how it relates to the market."),
        c("econometrics — Granger causality, cointegration, panel regression", "reference", "Not implemented",
          "Lead-lag and pair relationships — documented only."),
        c("funds menu (mutual fund lookup)", "partial", "Mutual funds in the universe get every analysis", "Fund holdings and fees are not wired."),
    ]},

    {"repo": "pyql (QuantLib Python)", "url": "https://github.com/enthought/pyql", "concepts": [
        c("Bond pricing, YTM, duration, convexity", "partial", "Bond analytics API (/bond)",
          "A bond's fair price and how much it moves when rates change — computed, not yet shown in the UI."),
        c("Analytic European & binomial option engines", "implemented", OL + "Pricer (BSM, CRR tree)",
          "Industry-standard option pricing, re-implemented natively."),
        c("Yield-curve bootstrapping", "reference", "Not implemented", "Building a zero curve from market rates — rates desks only."),
        c("Day-count conventions & holiday calendars", "reference", "Not implemented", "Precise accrual maths for bonds and swaps."),
    ]},

    {"repo": "vollib", "url": "https://github.com/vollib/vollib", "concepts": [
        c("Black-Scholes(-Merton) price & analytic greeks", "implemented", OL + "Pricer (BSM)",
          "The standard option formula plus the sensitivities that show how the price will move."),
        c("Black-76 for futures options", "implemented", OL + "Pricer (Black-76)", "Same idea priced off a futures/forward price."),
        c("Implied volatility solver", "implemented", OL + "Pricer (IV)",
          "Backs out the market's volatility expectation from an option price (root-finding, not Jäckel's 'Let's Be Rational')."),
        c("Numerical greeks", "partial", OL + "Pricer (analytic greeks only)", "Finite-difference greeks are not exposed separately."),
    ]},

    {"repo": "QuantPy", "url": "https://github.com/jsmidt/QuantPy", "concepts": [
        c("Performance metrics (CAGR, Sharpe, Sortino, Calmar, hit rate)", "implemented", QD + "Overview",
          "Scorecards that tell you if the return is worth the risk."),
        c("Markowitz efficient frontier", "implemented", QD + "Portfolio → Efficient frontier",
          "The curve of best possible return for each level of risk."),
        c("Monte-Carlo price simulation", "implemented", QD + "Risk & Regime → Monte-Carlo price cone",
          "Thousands of plausible futures give an honest planning range."),
        c("Event profiler (returns around events)", "partial", "Events card / cycles event study",
          "Average returns around astro events; earnings/corporate events are not profiled."),
    ]},

    {"repo": "Finance-Python (alpha-mind)", "url": "https://github.com/alpha-miner/Finance-Python", "concepts": [
        c("Streaming rolling-window operators (moving mean/max/min/std/RSI/correlation)", "implemented",
          QD + "Signals, Momentum & Vol (vectorised equivalents)", "Indicators updated bar by bar — the raw material of every signal."),
        c("Antithetic Monte-Carlo option pricing", "implemented", OL + "Pricer (Monte-Carlo)", "Variance-reduced simulation pricing."),
        c("Time-series z-score / normalisation", "implemented", QD + "Signals → Mean-reversion z-score",
          "How stretched price is vs its own recent average."),
        c("Cross-sectional factor operators (rank, neutralise, industry z-score)", "reference", "Not implemented",
          "Ranks many stocks against each other — needs a multi-stock factor pipeline."),
        c("Business-day calendars & schedules", "partial", OL + "expiry handling", "Option expiries are respected; full holiday calendars are not."),
    ]},

    {"repo": "ffn", "url": "https://github.com/pmorissette/ffn", "concepts": [
        c("calc_stats performance summary", "implemented", QD + "Overview", "One-glance scorecard of return, risk and drawdown."),
        c("Monthly returns table", "implemented", QD + "Heatmaps → Monthly returns (every year)",
          "Year-by-month profit grid so you can see which months historically pay you."),
        c("Drawdown details (top drawdowns, length, recovery)", "implemented", QD + "Risk & Regime → Drawdown history",
          "The worst falls, how long they lasted and how long they took to heal."),
        c("Drawdown & rebased series", "implemented", QD + "Trend Charts", "How far below its peak the asset is today."),
        c("Rolling Sharpe & volatility", "implemented", QD + "Risk & Regime → Rolling volatility & Sharpe",
          "Whether risk-adjusted returns are improving or fading."),
        c("Inverse-volatility & ERC weights, mean-variance", "implemented", QD + "Portfolio", "Classic allocation recipes."),
        c("Correlation clustering (calc_clusters)", "partial", QD + "Portfolio (HRP uses hierarchical clustering)",
          "Clusters drive HRP weights; the dendrogram itself is not drawn."),
    ]},

    {"repo": "pynance", "url": "https://github.com/GriffinAustin/pynance", "concepts": [
        c("Option spread analytics (verticals, straddles, condors)", "implemented", OL + "Strategy Lab (14 structures)",
          "Combines options into one trade with known max profit and loss."),
        c("Technical helpers (SMA, EMA, Bollinger)", "implemented", QD + "Trend Charts / Momentum & Vol / Signals", "Standard trend and band indicators."),
        c("Portfolio mean-variance optimisation", "implemented", QD + "Portfolio", "Best mix of assets for a target risk."),
        c("Regression-based prediction", "implemented", QD + "Forecast (drift/ARIMA) + Model Lab", "Simple statistical projections with tested error."),
    ]},

    {"repo": "pysabr", "url": "https://github.com/ynouri/pysabr", "concepts": [
        c("SABR lognormal smile (Hagan 2002)", "implemented", OL + "Pricer → smile chart",
          "Why far-from-the-money options carry different implied vols — the 'smile'."),
        c("SABR calibration to market quotes", "partial", OL + "Pricer (manual ρ/ν inputs)", "Parameters are user-set, not fitted to a live chain."),
        c("Normal (Bachelier) SABR", "reference", "Not implemented", "Used for negative-rate markets — not needed for equities."),
    ]},

    {"repo": "FinancePy", "url": "https://github.com/domokane/FinancePy", "concepts": [
        c("Equity vanilla options & greeks", "implemented", OL + "Pricer", "Standard calls and puts."),
        c("Asian (average-price) options", "implemented", OL + "Pricer (Asian)", "Payoff on the average price — smoother and cheaper."),
        c("Heston stochastic volatility", "implemented", OL + "Pricer (Heston)", "Lets volatility itself move — closer to real markets."),
        c("Barrier, digital, lookback exotics", "reference", "Not implemented", "Path-dependent exotics — documented only."),
        c("Bonds & fixed-income analytics", "partial", "Bond analytics API (/bond)", "Computed server-side, no UI panel yet."),
        c("Interest-rate swaps, CDS, credit", "reference", "Not implemented", "Rates and credit desks only."),
        c("FX options (Garman-Kohlhagen)", "partial", OL + "Pricer (BSM with dividend yield = foreign rate)", "Mathematically equivalent input; no FX-specific UI."),
    ]},

    {"repo": "willowtree", "url": "https://github.com/willowtreeapps/willowtree", "concepts": [
        c("Lattice (tree) valuation", "partial", OL + "Pricer (CRR binomial tree)",
          "Steps price up/down through time so early exercise can be valued; we use a CRR tree, not a willow tree."),
        c("Willow-tree sampling for path-dependent pricing", "reference", "Not implemented", "Faster lattice for exotic payoffs — documented only."),
    ]},

    {"repo": "financial-engineering (federicomariamassari)", "url": "https://github.com/federicomariamassari/financial-engineering", "concepts": [
        c("Monte-Carlo European option pricing", "implemented", OL + "Pricer (Monte-Carlo)", "Prices options by simulating many futures."),
        c("Variance reduction (antithetic variates)", "implemented", OL + "Pricer (Monte-Carlo, antithetic)", "Same accuracy with fewer simulations."),
        c("Longstaff-Schwartz American Monte-Carlo", "reference", "Not implemented (CRR tree used for American options)", "Regression-based early-exercise pricing."),
        c("Correlated multi-asset paths (Cholesky)", "reference", "Not implemented", "Simulating several assets that move together."),
        c("Block-bootstrap path simulation", "implemented", QD + "Risk & Regime → Monte-Carlo price cone", "Re-samples real return blocks to keep fat tails."),
    ]},

    {"repo": "optlib", "url": "https://github.com/dbrojas/optlib", "concepts": [
        c("CRR binomial American options", "implemented", OL + "Pricer (CRR, American toggle)", "Values the right to exercise early."),
        c("Generalised Black-Scholes family (BS, Black-76, Merton)", "implemented", OL + "Pricer", "One formula covering stocks, futures and dividends."),
        c("Implied volatility", "implemented", OL + "Pricer (IV)", "The market's volatility forecast hidden in an option price."),
        c("Bjerksund-Stensland American approximation", "reference", "Not implemented", "Fast closed-form American pricing."),
    ]},

    {"repo": "tf-quant-finance", "url": "https://github.com/google/tf-quant-finance", "concepts": [
        c("Heston model pricing", "implemented", OL + "Pricer (Heston via Lewis 2001)", "Stochastic-volatility option prices."),
        c("Monte-Carlo path simulation", "implemented", QD + "Risk & Regime MC cone + " + OL + "Pricer MC", "Simulated futures for pricing and planning."),
        c("Local volatility (Dupire)", "reference", "Not implemented", "Needs a full market vol surface."),
        c("Short-rate models (Hull-White, HJM)", "reference", "Not implemented", "Interest-rate modelling."),
        c("PDE / finite-difference solvers", "reference", "Not implemented", "Grid-based pricing for exotic options."),
    ]},

    {"repo": "Q-Fin", "url": "https://github.com/RomanMichaelPaolucci/Q-Fin", "concepts": [
        c("Historical & parametric VaR", "implemented", QD + "Risk & Regime → VaR table", "Two complementary answers to 'how bad can a day get?'"),
        c("Cornish-Fisher (fat-tail adjusted) VaR", "implemented", QD + "Risk & Regime → VaR table", "Corrects the bell curve for skew and fat tails."),
        c("Stochastic processes (GBM)", "implemented", OL + "Pricer (MC); " + QD + "Forecast fan", "The random-walk-with-drift model behind most pricing."),
        c("Ornstein-Uhlenbeck / CIR mean-reverting processes", "reference", "Not implemented", "Models for spreads and rates that snap back."),
        c("Monte-Carlo VaR", "partial", QD + "Risk & Regime → MC cone (P(−10% dip))", "Simulated loss probabilities; a dedicated MC-VaR figure is not shown."),
    ]},

    {"repo": "Quantsbin", "url": "https://github.com/quantsbin/Quantsbin", "concepts": [
        c("Payoff & P/L curve visualisation", "implemented", OL + "Strategy Lab payoff chart", "See profit/loss at expiry before you trade."),
        c("Multi-leg strategy builder", "implemented", OL + "Strategy Lab", "Combine legs into named strategies."),
        c("Pricing engines (BS, binomial, MC)", "implemented", OL + "Pricer", "Three ways to value the same option."),
        c("Greek sensitivity curves", "partial", OL + "Pricer (point greeks)", "Greeks at one point; curves across spot are not drawn."),
    ]},

    {"repo": "je-suis-tm/quant-trading", "url": "https://github.com/je-suis-tm/quant-trading", "concepts": [
        c("MACD oscillator strategy", "implemented", QD + "Signals", "Momentum acceleration — buy when MACD crosses above its signal line."),
        c("RSI pattern recognition", "implemented", QD + "Signals", "Buy the climb out of oversold, sell the drop out of overbought."),
        c("Bollinger Bands W-bottom / M-top", "implemented", QD + "Signals (band re-entry proxy)", "Reversal after a stretch outside the 2σ band."),
        c("Parabolic SAR", "implemented", QD + "Signals", "A trailing stop that flips you long or short."),
        c("Heikin-Ashi candlestick strategy", "implemented", QD + "Signals", "Smoothed candles that filter noise in trends."),
        c("Awesome Oscillator", "implemented", QD + "Signals", "5 vs 34-bar momentum of the bar midpoint."),
        c("Dual Thrust", "implemented", QD + "Signals (daily adaptation)", "Breakout beyond a fraction of the recent range."),
        c("London Breakout", "partial", QD + "Signals → Range breakout (daily adaptation)", "Original is an intraday FX session breakout; we apply it to daily bars."),
        c("Pair trading (cointegration)", "partial", QD + "Signals z-score + Correlations", "Single-asset z-score and correlations only; cointegrated pairs are not traded."),
        c("Options straddle", "implemented", OL + "Strategy Lab (Long Straddle)", "Profit from a big move in either direction."),
        c("Shooting-star candlestick", "reference", "Not implemented", "Single-candle reversal pattern."),
        c("VIX calculator", "reference", "Not implemented (VIX itself is in the correlation heatmap)", "Computes implied vol index from an options chain."),
        c("Monte-Carlo (and its forecasting limits)", "implemented", QD + "Risk & Regime → MC cone (shown as ranges, not targets)", "Simulation gives ranges, not predictions."),
        c("Oil Money (currency vs oil regression)", "partial", QD + "Heatmaps → correlation with crude oil", "Oil linkage is shown; the regression trade is not."),
        c("Wisdom of crowds (signal consensus)", "implemented", QD + "Signals → consensus gauge", "Many weak rules voting together beat any single one."),
    ]},

    {"repo": "StockSharp", "url": "https://github.com/StockSharp/StockSharp", "concepts": [
        c("Multi-exchange connectivity", "reference", "Architecture docs", "How firms connect to many brokers at once."),
        c("Candle builder (multi-timeframe bars)", "implemented", QD + "Heatmaps → Signal × timeframe", "Same rule on daily, weekly and monthly bars."),
        c("Strategy designer & backtester", "partial", QD + "Signals backtests", "Rules are fixed; no visual strategy designer."),
        c("Order book / market depth", "reference", "Not implemented", "Level-2 data needs a broker feed."),
    ]},

    {"repo": "Riskfolio-Lib", "url": "https://github.com/dcajasn/Riskfolio-Lib", "concepts": [
        c("Mean-variance (min-variance, max-Sharpe)", "implemented", QD + "Portfolio", "The classic Markowitz allocations."),
        c("Risk parity (equal risk contribution)", "implemented", QD + "Portfolio", "Each asset contributes the same share of risk."),
        c("Hierarchical Risk Parity (HRP)", "implemented", QD + "Portfolio", "Clusters similar assets first — robust to noisy estimates."),
        c("Ledoit-Wolf covariance shrinkage", "implemented", QD + "Portfolio", "Stabilises the risk model so weights don't swing wildly."),
        c("Efficient frontier plot", "implemented", QD + "Portfolio → Efficient frontier", "Best return for each level of risk."),
        c("Risk contribution report", "implemented", QD + "Portfolio (risk share column)", "Which asset is really driving portfolio risk."),
        c("CVaR / CDaR / EVaR risk-measure optimisation", "partial", QD + "Risk & Regime (CVaR reported)", "Tail risk is measured but not used as the optimisation target."),
        c("HERC / NCO / Black-Litterman", "reference", "Not implemented", "Advanced allocators — documented only."),
    ]},

    {"repo": "EliteQuant", "url": "https://github.com/EliteQuant/EliteQuant", "concepts": [
        c("Unified data → signal → risk → execution stack", "implemented", "Backend service layout", "The layered architecture serious funds use."),
        c("Event-driven backtest engine", "partial", QD + "Signals (vectorised) + Walk-Forward Backtest card", "Vectorised tests only; no tick-level event engine."),
        c("Live trading gateways", "reference", "Not implemented", "Order routing to brokers is out of scope (educational product)."),
    ]},

    {"repo": "Quant-Developers-Resources", "url": "https://github.com/cybergeekgyan/Quant-Developers-Resources", "concepts": [
        c("Curated quant learning map", "implemented", "Plain-English Shows / Means / Do lines on every chart", "You learn the concept while using it."),
        c("Time-series statistics curriculum (stationarity, autocorrelation, GARCH)", "implemented", QD + "Risk & Regime",
          "The textbook tests, run on your symbol and explained."),
    ]},

    {"repo": "TradeMaster-NTU/TradeMaster", "url": "https://github.com/TradeMaster-NTU/TradeMaster", "concepts": [
        c("Model zoo & benchmarking", "implemented", "Model Lab (leaderboard)", "Trains many models on your stock and ranks them."),
        c("Market-regime labelling (market dynamics modelling)", "implemented", QD + "Risk & Regime → Volatility regime", "Labels each day Calm or Stressed."),
        c("Evaluation toolkit (Sharpe, MDD, Calmar)", "implemented", QD + "Overview + Signals backtests", "Common scorecard for every strategy."),
        c("Reinforcement-learning trading agents (DQN, PPO)", "reference", "Not implemented", "Agents that learn to trade by trial and error — documented only."),
    ]},

    {"repo": "sunday-quant-scientist", "url": "https://github.com/quant-science/sunday-quant-scientist", "concepts": [
        c("Weekly seasonality review", "implemented", QD + "Heatmaps (monthly, weekday × month)", "Check which months and weekdays favour your stock."),
        c("Regime detection (HMM-style)", "implemented", QD + "Risk & Regime → Volatility regime", "Know whether you are in a calm or stressed market."),
        c("GARCH volatility forecasting", "implemented", QD + "Risk & Regime → GARCH", "Forecast tomorrow's and next month's volatility."),
        c("Vectorised strategy backtests (vectorbt-style)", "implemented", QD + "Signals", "Fast what-if tests of many rules at once."),
        c("Riskfolio portfolio tutorial", "implemented", QD + "Portfolio", "Allocation methods applied to your basket."),
    ]},

    {"repo": "QuantMuse", "url": "https://github.com/0xemmkty/QuantMuse", "concepts": [
        c("Narrative analytics", "implemented", "Every chart carries Shows / Means / Do", "Numbers become sentences you can act on."),
        c("Momentum & mean-reversion strategy templates", "implemented", QD + "Signals", "The two basic styles, tested on your symbol."),
        c("Multi-factor scoring (momentum, value, quality)", "partial", QD + "Signals (time-series momentum only)", "Value/quality factors need fundamentals data."),
        c("LLM news & sentiment analysis", "partial", "AI Agents", "Agents weigh sentiment; a full LLM news pipeline is optional."),
    ]},

    {"repo": "Options-Trading-Strategies-in-Python (PyPatel)", "url": "https://github.com/PyPatel/Options-Trading-Strategies-in-Python", "concepts": [
        c("Covered call", "implemented", OL + "Strategy Lab", "Get paid to wait by selling upside you don't expect."),
        c("Protective put / collar", "implemented", OL + "Strategy Lab (Collar)", "Insurance against a fall."),
        c("Bull / bear spreads", "implemented", OL + "Strategy Lab (4 vertical spreads)", "Directional bets with capped risk."),
        c("Straddle / strangle", "implemented", OL + "Strategy Lab", "Bets on a big move either way."),
        c("Butterfly / iron condor", "implemented", OL + "Strategy Lab (Iron Butterfly, Iron Condor)", "Income when price stays in a range."),
        c("Long call butterfly (debit)", "reference", "Not in the catalog (iron butterfly used)", "Cheap range bet with defined risk."),
    ]},

    {"repo": "howtrader (51bitquant)", "url": "https://github.com/51bitquant/howtrader", "concepts": [
        c("CTA strategy templates (EMA cross, Boll channel, ATR-RSI)", "implemented", QD + "Signals", "Trend-following rules ready for automation."),
        c("Grid trading", "implemented", QD + "Signals → Grid levels", "Buy fixed steps below the mean, sell steps above."),
        c("Turtle / Donchian breakout", "implemented", QD + "Signals", "Buy 20-day highs, exit on 10-day lows."),
        c("Dual Thrust", "implemented", QD + "Signals", "Range-breakout rule popular with CTAs."),
        c("Spot-futures / funding arbitrage", "reference", "Not implemented", "Crypto basis trades — needs exchange connectivity."),
        c("Live exchange gateway (Binance)", "reference", "Not implemented", "Automated execution is out of scope."),
    ]},

    {"repo": "goldmansachs (homepage)", "url": "https://github.com/goldmansachs", "concepts": [
        c("Institutional research-grade tooling ethos", "partial", "Whole Institutional Desk",
          "Publish your assumptions: every chart states its method and limits."),
    ]},

    {"repo": "TradingAgents", "url": "https://github.com/TauricResearch/TradingAgents", "concepts": [
        c("Multi-agent debate → fund-manager verdict", "implemented", "AI Agents section",
          "Seven specialist agents argue about your stock, then a manager gives one clear verdict."),
    ]},
]


def coverage_summary() -> Dict:
    total = sum(len(r["concepts"]) for r in REPOS)
    impl = sum(1 for r in REPOS for x in r["concepts"] if x["status"] == "implemented")
    part = sum(1 for r in REPOS for x in r["concepts"] if x["status"] == "partial")
    ref = sum(1 for r in REPOS for x in r["concepts"] if x["status"] == "reference")
    return {
        "repos": len(REPOS), "concepts": total,
        "implemented": impl, "partial": part, "reference": ref,
        "coverage_pct": round(100 * (impl + part) / total, 1),
    }


def all_concepts() -> Dict:
    return {"success": True, "summary": coverage_summary(), "repos": REPOS}
