/**
 * v1.3 Quant Desk API — signal board, heatmaps, risk & regime, portfolio and
 * forecasting baselines. Same-origin /api/astro/* proxy (see api.ts).
 * Responses are memoised client-side for 10 minutes so switching tabs is instant.
 */

export interface Insight {
  shows: string;
  means: string;
  action: string;
}

/* ── signals ─────────────────────────────────────────────────────────────── */
export interface RuleBacktest {
  signals: number;
  buy_signals: number;
  hit_rate: number | null;
  avg_fwd5_buy: number | null;
  avg_fwd20_buy: number | null;
  avg_fwd20_sell: number | null;
  cagr: number | null;
  bh_cagr: number | null;
  max_dd: number | null;
  bh_max_dd: number | null;
  sharpe: number | null;
  bh_sharpe: number | null;
  time_in_market: number | null;
  years: number | null;
}
export type SignalLabel = 'BUY' | 'SELL' | 'NEUTRAL';
export interface SignalRule {
  key: string;
  name: string;
  family: string;
  source: string;
  rule: string;
  signal: SignalLabel;
  value: number;
  age_days: number;
  fresh: boolean;
  readout: Record<string, number | null>;
  backtest: RuleBacktest;
  insight: Insight;
}
export interface HeatRows {
  name: string;
  values: (number | null)[];
}
export interface SignalsResponse {
  success: boolean;
  symbol: string;
  start: string;
  bars: number;
  has_volume: boolean;
  rules: SignalRule[];
  consensus: {
    score: number;
    weighted_score: number;
    label: string;
    buy: number;
    sell: number;
    neutral: number;
    total: number;
    history: { dates: string[]; score: (number | null)[]; close: (number | null)[] };
    best_rules: string[];
    insight: Insight;
  };
  timeframe_heatmap: { timeframes: string[]; rows: HeatRows[]; insight: Insight };
  horizon_heatmap: { horizons: string[]; rows: HeatRows[]; baseline: Record<string, number | null>; insight: Insight };
  method: string;
}

/* ── heatmaps ────────────────────────────────────────────────────────────── */
export interface HeatmapsResponse {
  success: boolean;
  symbol: string;
  start: string;
  monthly: {
    years: number[];
    months: string[];
    values: (number | null)[][];
    annual: (number | null)[];
    avg: (number | null)[];
    pct_positive: (number | null)[];
    insight: Insight;
  };
  dow_month: {
    rows: string[];
    cols: string[];
    values: (number | null)[][];
    hit: (number | null)[][];
    count: number[][];
    by_dow: (number | null)[];
    t_stat: (number | null)[];
    insight: Insight;
  };
  vol_month: { years: number[]; months: string[]; values: (number | null)[][]; median: number | null; insight: Insight };
  dist_year: { years: number[]; bins: string[]; values: (number | null)[][]; insight: Insight };
  correlation: null | {
    periods: string[];
    rows: { symbol: string; name: string; values: (number | null)[] }[];
    matrix: { symbols: string[]; names: string[]; values: (number | null)[][] };
    insight: Insight;
  };
  benchmarks_loaded: string[];
  benchmarks_missing: string[];
}

/* ── regime ──────────────────────────────────────────────────────────────── */
export interface McHorizon {
  label: string;
  days: number;
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
  prob_up: number;
  prob_dd10: number;
}
export interface StatTest {
  test: string;
  stat: number | null;
  p: number | null;
  verdict: string;
  meaning: string;
}
export interface RegimeResponse {
  success: boolean;
  symbol: string;
  start: string;
  rolling: null | {
    dates: string[];
    vol21: (number | null)[];
    vol63: (number | null)[];
    sharpe252: (number | null)[];
    vol_now: number;
    vol_median: number;
    vol_pctile: number;
    sharpe_now: number;
    sharpe_median: number;
    insight: Insight;
  };
  garch: null | {
    alpha: number;
    beta: number;
    persistence: number;
    half_life_days: number | null;
    vol_next_day: number;
    vol_long_run: number;
    vol_1m: number;
    vol_3m: number;
    term: { h: number; vol: number }[];
    history: { dates: string[]; garch: (number | null)[]; realised: (number | null)[] };
    insight: Insight;
  };
  hurst: null | {
    full: number;
    now: number;
    regime: string;
    series: { dates: string[]; hurst: (number | null)[] };
    insight: Insight;
  };
  regime: null | {
    current: string;
    p_stress: number;
    states: {
      name: string;
      share_pct: number;
      ann_return_pct: number | null;
      ann_vol_pct: number | null;
      fwd20_pct: number | null;
      avg_duration_days: number;
    }[];
    stay_prob: { calm: number; stressed: number };
    series: { dates: string[]; p_stress: (number | null)[]; close: (number | null)[] };
    insight: Insight;
  };
  mc_cone: null | {
    last: number;
    paths: number;
    cone: { day: number; p5: number; p25: number; p50: number; p75: number; p95: number }[];
    horizons: McHorizon[];
    insight: Insight;
  };
  var: null | {
    rows: {
      conf: number;
      horizon_days: number;
      hist_var: number;
      hist_cvar: number;
      param_var: number;
      param_cvar: number;
      cf_var: number;
      hist_var_amt: number;
      cf_var_amt: number;
    }[];
    skew: number;
    excess_kurtosis: number;
    obs: number;
    notional: number;
    insight: Insight;
  };
  tests: null | { tests: StatTest[]; insight: Insight };
  beta: null | {
    benchmark: string;
    benchmark_name: string;
    beta_now: number;
    corr_now: number;
    alpha_ann_pct: number;
    up_capture: number | null;
    down_capture: number | null;
    series: { dates: string[]; beta: (number | null)[]; corr: (number | null)[] };
    insight: Insight;
  };
  drawdowns: null | {
    rows: {
      peak: string;
      trough: string;
      recovery: string | null;
      depth_pct: number;
      days_to_trough: number;
      days_to_recover: number | null;
      total_days: number;
    }[];
    current_pct: number;
    insight: Insight;
  };
  vol_cone: null | {
    rows: { window: number; min: number; p25: number; median: number; p75: number; max: number; now: number; pctile: number }[];
    insight: Insight;
  };
}

/* ── portfolio ───────────────────────────────────────────────────────────── */
export interface PortfolioMethod {
  name: string;
  weights: number[];
  exp_return_pct: number;
  vol_pct: number;
  sharpe: number;
  max_dd_pct: number;
  diversification_ratio: number;
  risk_contrib: number[];
}
export interface PortfolioResponse {
  success: boolean;
  symbol: string;
  assets: string[];
  names: string[];
  window: { start: string; end: string; days: number };
  asset_stats: { symbol: string; name: string; ret_pct: number; vol_pct: number; sharpe: number }[];
  corr: (number | null)[][];
  portfolios: PortfolioMethod[];
  alone: Omit<PortfolioMethod, 'name' | 'weights'>;
  frontier: { vol: number; ret: number }[];
  cloud: { vol: number; ret: number; sharpe: number }[];
  asset_points: { symbol: string; vol: number; ret: number }[];
  insight: Insight;
  method: string;
}

/* ── forecast baselines ──────────────────────────────────────────────────── */
export interface ForecastRow {
  model: string;
  description: string;
  mape: number;
  direction_hit: number | null;
  tests: number;
  forecast_end: number;
  change_pct: number;
}
export interface ForecastBaselinesResponse {
  success: boolean;
  symbol: string;
  horizon_days: number;
  table: ForecastRow[];
  best: string;
  ensemble_change_pct: number;
  band80_end: [number, number] | null;
  series: Record<string, (number | string | null)[]> & { dates: string[] };
  insight: Insight;
}

/* ── fetchers ────────────────────────────────────────────────────────────── */
const TTL = 10 * 60 * 1000;
const memo = new Map<string, { t: number; p: Promise<unknown> }>();

async function getJson<T>(path: string): Promise<T> {
  const hit = memo.get(path);
  if (hit && Date.now() - hit.t < TTL) return hit.p as Promise<T>;
  const p = fetch(`/api/astro/${path}`, { cache: 'no-store' }).then(async (res) => {
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
  });
  memo.set(path, { t: Date.now(), p });
  p.catch(() => memo.delete(path));
  return p;
}

const enc = encodeURIComponent;

export const quantDeskApi = {
  signals: (symbol: string) => getJson<SignalsResponse>(`quant/signals/${enc(symbol)}`),
  heatmaps: (symbol: string) => getJson<HeatmapsResponse>(`quant/heatmaps/${enc(symbol)}`),
  regime: (symbol: string) => getJson<RegimeResponse>(`quant/regime/${enc(symbol)}`),
  portfolio: (symbol: string) => getJson<PortfolioResponse>(`quant/portfolio/${enc(symbol)}`),
  forecast: (symbol: string) => getJson<ForecastBaselinesResponse>(`quant/forecast/${enc(symbol)}`),
};
