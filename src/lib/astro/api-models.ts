/**
 * v1.3 Model Lab API — full-history model zoo (~45 models, walk-forward CV),
 * plain-English insights, ensemble forecast and out-of-sample backtest.
 * Same-origin /api/astro/* proxy (see api.ts).
 */

export type ModelStatus = 'ok' | 'skipped' | 'failed';

export interface ZooRow {
  key: string;
  name: string;
  family: string;
  kind: 'reg' | 'ts' | 'naive' | 'ens' | 'clf';
  desc: string;
  cap: number | null;
  status: ModelStatus;
  reason?: string;
  features_used?: string | null;
  r2_os?: number | null;
  rmse?: number | null;
  mae?: number | null;
  hit_rate?: number | null;
  ic?: number | null;
  dm_t?: number | null;
  folds_r2_os?: (number | null)[];
  folds_beat?: number;
  n_folds?: number;
  interval90_coverage?: number | null;
  members?: string[];
  weights?: Record<string, number | null>;
  seconds?: number;
  insight: string;
  // classifiers
  horizon?: number;
  accuracy?: number | null;
  balanced_accuracy?: number | null;
  auc?: number | null;
  base_rate?: number | null;
  up_share?: number | null;
  edge_vs_base?: number | null;
}

export interface ImportanceRow {
  feature: string;
  group: 'astro' | 'technical' | 'calendar';
  meaning: string;
  importance: number | null;
  importance_sd: number | null;
  real: boolean;
}

export interface ForecastHorizon {
  horizon: number;
  expected_return_pct: number | null;
  band_low_pct: number | null;
  band_high_pct: number | null;
  expected_price: number | null;
  price_low: number | null;
  price_high: number | null;
  p_up: number | null;
  p_up_source: string;
  p_up_best?: number | null;
  best_classifier?: string;
  hist_up_share: number | null;
  member_forecasts_pct: (number | null)[];
}

export interface ZooResult {
  success: boolean;
  symbol: string;
  vedic: boolean;
  zodiac: string;
  data: {
    rows: number;
    start: string;
    end: string;
    years: number;
    features: number;
    oos_days: number;
    oos_start: string;
    oos_years: number;
    folds: number;
  };
  leaderboard: ZooRow[];
  classifiers: ZooRow[];
  best_model: string | null;
  best_name: string | null;
  ensemble_members: string[];
  feature_importance: {
    model: string | null;
    model_name?: string;
    method?: string;
    unit?: string;
    features: ImportanceRow[];
    group_share?: Record<string, number | null>;
    n_real?: number;
  };
  pred_vs_actual: {
    model?: string;
    series?: { date: string; actual: number | null; predicted: number | null }[];
    deciles?: { decile: number; avg_predicted: number | null; avg_actual: number | null; up_share: number | null }[];
    corr?: number | null;
  };
  forecast: { next_session: string; last_close: number | null; horizons: ForecastHorizon[]; members: string[]; band_method: string };
  insights: {
    headline: string;
    overall: string[];
    direction: string[];
    features: string[];
    forecast: string[];
    what_to_do: string;
    beats_naive: boolean;
    significant: boolean;
    best_model: string | null;
  };
  families: string[];
  caps: { model: string; max_train_rows: number }[];
  method: string;
  counts: { trained: number; skipped: number; failed: number };
  runtime_seconds: number;
  disclaimer: string;
}

export type ZooStatus =
  | ({ status: 'done'; cached?: boolean } & ZooResult)
  | { status: 'running'; stage: string; progress: number; done?: number; total?: number; rows?: number; elapsed?: number }
  | { status: 'started'; stage: string; progress: number }
  | { status: 'failed'; error: string }
  | { status: 'idle' };

export interface ModelBacktest {
  success: boolean;
  symbol: string;
  model: string;
  model_name: string;
  source: string;
  rule: string;
  cost_bps: number;
  mode: string;
  test_range: string;
  test_samples: number;
  test_years: number;
  strategy: {
    total_return: number;
    annual_return: number;
    sharpe: number;
    max_drawdown: number;
    win_rate: number | null;
    exposure: number;
    trades: number;
  };
  buy_hold: { total_return: number; annual_return: number; sharpe: number; max_drawdown: number };
  years_beat: number;
  years_total: number;
  equity_curve: { date: string; strategy: number; buy_hold: number }[];
  verdict: string;
  options: { key: string; name: string }[];
  disclaimer: string;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const d = await res.json();
      if (d?.detail) detail = typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const modelsApi = {
  zooTrain: (symbol: string, vedic: boolean, force = false) =>
    fetch('/api/astro/models/zoo/train', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, use_vedic: vedic, force }),
    }).then((r) => json<ZooStatus>(r)),

  zooStatus: (symbol: string, vedic: boolean) =>
    fetch(`/api/astro/models/zoo/status?symbol=${encodeURIComponent(symbol)}&vedic=${vedic}`, {
      cache: 'no-store',
    }).then((r) => json<ZooStatus>(r)),

  backtest: (symbol: string, vedic: boolean, model: string, costBps = 5, mode = 'long_cash') =>
    fetch('/api/astro/models/backtest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, use_vedic: vedic, model, cost_bps: costBps, mode }),
    }).then((r) => json<ModelBacktest>(r)),
};
