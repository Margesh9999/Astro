import type {
  AstroEvent,
  BacktestResult,
  MarketQuote,
  NatalResponse,
  PlanetaryResponse,
  PredictResult,
  SymbolInfo,
  TrainResult,
} from './types';

/**
 * All calls go through the same-origin Next.js proxy /api/astro/*, which
 * forwards to the FastAPI mini-service on port 8000. This works both when
 * the app is accessed directly on :3000 and through the Caddy gateway.
 *
 * ⚠️ NEVER append ?XTransformPort=8000 here: the gateway honours that param
 * and would proxy the request straight to :8000 while PRESERVING the path
 * (/api/astro/...), which the FastAPI backend does not serve (it only
 * exposes /api/v1/*) — resulting in 404s for every external API call.
 * Same-origin /api/astro/* + server-side path rewrite is the only correct
 * route in every access mode (direct :3000, gateway, preview URL).
 */
const q = (extra?: Record<string, string | number | boolean | undefined>) => {
  const params = new URLSearchParams();
  if (extra) {
    for (const [k, v] of Object.entries(extra)) {
      if (v !== undefined) params.set(k, String(v));
    }
  }
  const s = params.toString();
  return s;
};

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data?.detail) detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const astroApi = {
  health: () =>
    fetch(`/api/astro/health?${q()}`, { cache: 'no-store' }).then((r) =>
      jsonOrThrow<{ status: string; service: string; version: string }>(r),
    ),

  symbols: () =>
    fetch(`/api/astro/symbols?${q()}`, { cache: 'no-store' }).then((r) =>
      jsonOrThrow<{ symbols: SymbolInfo[] }>(r),
    ),

  planetary: (date: string, vedic: boolean) =>
    fetch(`/api/astro/planetary/${date}?${q({ vedic })}`, { cache: 'no-store' }).then((r) =>
      jsonOrThrow<PlanetaryResponse>(r),
    ),

  market: (symbol: string) =>
    fetch(`/api/astro/market/${encodeURIComponent(symbol)}?${q()}`, { cache: 'no-store' }).then((r) =>
      jsonOrThrow<MarketQuote>(r),
    ),

  train: (symbol: string, lookbackYears: number, useVedic: boolean) =>
    fetch(`/api/astro/train?${q()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, lookback_years: lookbackYears, use_vedic: useVedic }),
      cache: 'no-store',
    }).then((r) => jsonOrThrow<TrainResult>(r)),

  predict: (symbol: string, daysAhead: number, useVedic: boolean) =>
    fetch(`/api/astro/predict?${q()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, days_ahead: daysAhead, use_vedic: useVedic }),
      cache: 'no-store',
    }).then((r) => jsonOrThrow<PredictResult>(r)),

  backtest: (symbol: string, lookbackYears: number, useVedic: boolean) =>
    fetch(`/api/astro/backtest?${q()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, lookback_years: lookbackYears, use_vedic: useVedic }),
      cache: 'no-store',
    }).then((r) => jsonOrThrow<BacktestResult>(r)),

  events: (days: number = 45) =>
    fetch(`/api/astro/events?${q({ days })}`, { cache: 'no-store' }).then((r) =>
      jsonOrThrow<{ success: boolean; events: AstroEvent[]; count: number }>(r),
    ),

  natal: () =>
    fetch(`/api/astro/natal?${q()}`, { cache: 'no-store' }).then((r) => jsonOrThrow<NatalResponse>(r)),
};
import type {
  AstroSignalResponse,
  OptionsPriceResponse,
  QuantRiskResponse,
  QuantStatsResponse,
  SabrResponse,
} from './types';

// appended to the base astroApi object above (same proxy discipline applies)
export const quantApi = {
  astroSignal: (symbol: string) =>
    fetch(`/api/astro/astro-signal/${encodeURIComponent(symbol)}?${q()}`, { cache: 'no-store' }).then(
      (r) => jsonOrThrow<AstroSignalResponse>(r),
    ),

  quantStats: (symbol: string, years = 3) =>
    fetch(`/api/astro/quant/stats/${encodeURIComponent(symbol)}?${q({ years })}`, { cache: 'no-store' }).then(
      (r) => jsonOrThrow<QuantStatsResponse>(r),
    ),

  quantRisk: (symbol: string, years = 3, conf = 0.95, position = 1_000_000) =>
    fetch(`/api/astro/quant/risk/${encodeURIComponent(symbol)}?${q({ years, conf, position })}`, {
      cache: 'no-store',
    }).then((r) => jsonOrThrow<QuantRiskResponse>(r)),

  optionPrice: (body: {
    model: string; cp: string; S: number; K: number; T?: number; r?: number; q?: number;
    sigma?: number; american?: boolean; steps?: number; n_paths?: number;
    kappa?: number; theta?: number; sigma_v?: number; rho?: number; v0?: number;
  }) =>
    fetch(`/api/astro/options/price?${q()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store',
    }).then((r) => jsonOrThrow<OptionsPriceResponse>(r)),

  impliedVol: (body: { price: number; S: number; K: number; T?: number; r?: number; q?: number; cp: string }) =>
    fetch(`/api/astro/options/iv?${q()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store',
    }).then((r) => jsonOrThrow<{ success: boolean; implied_vol: number }>(r)),

  sabrSmile: (body: { forward: number; T?: number; atm_vol: number; beta?: number; rho?: number; nu?: number }) =>
    fetch(`/api/astro/options/sabr?${q()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store',
    }).then((r) => jsonOrThrow<SabrResponse>(r)),
};

import type {
  IncomePlanResponse,
  OptionChainResponse,
  OptionExpirationsResponse,
  StrategyAnalysis,
  StrategyMeta,
  UniverseEntry,
  UniverseMeta,
} from './types';

// Options Lab / universe client (same proxy discipline as above)
export const labApi = {
  universe: (params?: { q?: string; market?: string; type?: string; options_only?: boolean; limit?: number }) =>
    fetch(`/api/astro/universe?${q(params as Record<string, string | number | boolean | undefined>)}`, {
      cache: 'no-store',
    }).then((r) => jsonOrThrow<{ success: boolean; count: number; results: UniverseEntry[] }>(r)),

  universeMeta: () =>
    fetch(`/api/astro/universe/meta?${q()}`, { cache: 'no-store' }).then((r) =>
      jsonOrThrow<{ success: boolean; meta: UniverseMeta }>(r),
    ),

  expirations: (symbol: string) =>
    fetch(`/api/astro/options/expirations/${encodeURIComponent(symbol)}?${q()}`, {
      cache: 'no-store',
    }).then((r) => jsonOrThrow<OptionExpirationsResponse>(r)),

  chain: (symbol: string, expiry: string) =>
    fetch(
      `/api/astro/options/chain/${encodeURIComponent(symbol)}?${q({ expiry })}`,
      { cache: 'no-store' },
    ).then((r) => jsonOrThrow<OptionChainResponse>(r)),

  strategies: () =>
    fetch(`/api/astro/options/strategies?${q()}`, { cache: 'no-store' }).then((r) =>
      jsonOrThrow<{ success: boolean; strategies: StrategyMeta[] }>(r),
    ),

  analyzeStrategy: (body: {
    symbol: string;
    strategy: string;
    expiry?: string;
    dte_target?: number;
    qty?: number;
    exit_dte?: number;
    params?: Record<string, number>;
  }) =>
    fetch(`/api/astro/options/strategy?${q()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store',
    }).then((r) => jsonOrThrow<StrategyAnalysis>(r)),

  incomePlan: (body: { capital: number; target_weekly: number; focus: string }) =>
    fetch(`/api/astro/income/plan?${q()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store',
    }).then((r) => jsonOrThrow<IncomePlanResponse>(r)),
};

import type {
  AgentsAnalysis,
  AnalyticsPack,
  ConceptsResponse,
  EventsForecast,
  JatakaPlace,
  JatakaReport,
  SuriCycles,
  ZooTrainResult,
} from './types';

// T1–T13 enhancement client (same proxy discipline as above)
export const enhanceApi = {
  jatakaPlaces: (search: string = '') =>
    fetch(`/api/astro/jataka/places?${q({ q: search })}`, { cache: 'no-store' }).then((r) =>
      jsonOrThrow<{ success: boolean; places: JatakaPlace[] }>(r),
    ),

  jatakaReport: (params: { symbol: string; name?: string; date?: string; time?: string; place?: string; capital?: number; target_weekly?: number }) =>
    fetch(`/api/astro/jataka/report?${q(params as Record<string, string | number | undefined>)}`, {
      cache: 'no-store',
    }).then((r) => jsonOrThrow<JatakaReport>(r)),

  analyticsCharts: (symbol: string) =>
    fetch(`/api/astro/analytics/charts/${encodeURIComponent(symbol)}?${q()}`, { cache: 'no-store' }).then(
      (r) => jsonOrThrow<AnalyticsPack>(r),
    ),

  eventsForecast: (symbol: string, days = 45) =>
    fetch(`/api/astro/events/forecast?${q({ symbol, days })}`, { cache: 'no-store' }).then((r) =>
      jsonOrThrow<EventsForecast>(r),
    ),

  suriCycles: (symbol: string) =>
    fetch(`/api/astro/suri/cycles/${encodeURIComponent(symbol)}?${q()}`, { cache: 'no-store' }).then((r) =>
      jsonOrThrow<SuriCycles>(r),
    ),

  agents: (symbol: string) =>
    fetch(`/api/astro/agents/${encodeURIComponent(symbol)}?${q()}`, { cache: 'no-store' }).then((r) =>
      jsonOrThrow<AgentsAnalysis>(r),
    ),

  concepts: () =>
    fetch(`/api/astro/concepts?${q()}`, { cache: 'no-store' }).then((r) => jsonOrThrow<ConceptsResponse>(r)),

  trainZoo: (body: { symbol: string; use_vedic: boolean; full_history: boolean }) =>
    fetch(`/api/astro/train/zoo?${q()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store',
    }).then((r) => jsonOrThrow<ZooTrainResult>(r)),

  trainZooStatus: (symbol: string, vedic = false) =>
    fetch(`/api/astro/train/zoo/status?${q({ symbol, vedic, full_history: true })}`, { cache: 'no-store' }).then(
      (r) => jsonOrThrow<ZooTrainResult>(r),
    ),
};
