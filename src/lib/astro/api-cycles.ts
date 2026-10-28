/**
 * v1.3 cycles client — Suri Cycles insight, cycle clock, full-history cycle
 * statistics and the Sky Events × Your Stock event study.
 * Same proxy discipline as api.ts: same-origin /api/astro/* only.
 */

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: 'no-store' });
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

export type Verdict = 'significant' | 'weak' | 'noise' | 'too few';

// ── cycle statistics ──────────────────────────────────────────────────────
export interface CycleBucketRow {
  label: string;
  n: number;
  mean_pct: number;
  hit_pct: number;
  diff_pct: number;
  hit_diff?: number;
  t: number;
  verdict: Verdict;
  vol_ratio?: number;
  next?: string | null;
  // moon phase extras
  fwd5_pct?: number;
  fwd5_diff?: number;
  // nakshatra extras
  lord?: string;
  // sun sign extras
  rashi?: string;
  months?: number;
  month_mean_pct?: number;
  month_hit_pct?: number;
}

export interface CycleBucket {
  baseline: { mean_pct: number; hit_pct: number; days: number };
  rows: CycleBucketRow[];
  current: string;
}

export interface RetroSide {
  n: number;
  mean_pct?: number;
  hit_pct?: number;
  vol_pct?: number;
  annual_pct?: number;
}

export interface RetroStat {
  retro: RetroSide;
  direct: RetroSide;
  vol_ratio?: number;
  t: number;
  verdict: Verdict;
  periods: number;
  period_mean_pct: number;
  period_hit_pct: number;
  avg_period_days: number;
  now: 'retrograde' | 'direct';
  next_change: string | null;
}

export interface CycleStats {
  success: boolean;
  symbol: string;
  name: string;
  history_start: string;
  history_end: string;
  days: number;
  moon_phase: CycleBucket;
  paksha: CycleBucket;
  nakshatra: CycleBucket;
  sun_sign: CycleBucket;
  retrograde: Record<string, RetroStat>;
  conclusions: Record<string, string>;
  method: string;
  data_source: string;
  demo_data: boolean;
  disclaimer: string;
}

// ── cycle clock ───────────────────────────────────────────────────────────
export interface ClockItem {
  id: string;
  label: string;
  progress: number;
  state: string;
  detail: string;
  next_label: string;
  next_date: string | null;
  days_to_next: number | null;
  meaning: string;
  retro?: boolean;
}

export interface CycleClock {
  date: string;
  items: ClockItem[];
}

// ── insight (today's reading) ─────────────────────────────────────────────
export interface SuriMood {
  mood_index: number;
  mood_label: string;
  phase_angle: number;
  lunar: string;
  retrogrades: number;
  components: Record<string, number>;
}

export interface SuriComposite {
  technical_score: number;
  astro_score: number;
  composite: number;
  zone: string;
  rsi14: number;
  trend_pct: number;
  vol20_annualised: number;
  vol_percentile: number;
}

export interface SuriRange {
  spot: number;
  horizon_days: number;
  ewma_daily_vol: number;
  horizon_sigma: number;
  astro_multiplier: number;
  bands: { outer: { high: number; low: number }; inner: { high: number; low: number } };
  support: number;
  resistance: number;
}

export interface SuriAlert {
  date: string;
  kind: string;
  title: string;
  note?: string;
  strength?: number;
  score?: number;
}

export interface WeekDay {
  date: string;
  weekday: string;
  closed: boolean;
  phase: string;
  tithi: string;
  nakshatra: string;
  events: string[];
  carried?: string[];
  history: string;
  verdict: Verdict;
  todo: string;
}

export interface LunarDay {
  date: string;
  weekday: string;
  closed: boolean;
  phase: string;
  tithi: string;
  nakshatra: string;
  angle: number;
  hit_pct: number | null;
  verdict: Verdict;
  tilt: number;
  note: string;
}

export interface StockContext {
  trend: 'up' | 'down' | 'sideways';
  chg_3m_pct: number;
  vol21_pct: number;
  vol1y_pct: number;
  vol_state: 'elevated' | 'normal' | 'calm';
  spot: number;
}

export interface CyclesInsight {
  success: boolean;
  symbol: string;
  name: string;
  sector: string;
  date: string;
  spot: number;
  mood: SuriMood;
  reversal: { reversal_score: number; drivers: { detail: string }[] };
  volatility: { volatility_score: number; drivers: { detail: string }[] };
  timing_alerts: SuriAlert[];
  five_day_range: SuriRange | Record<string, never>;
  composite: SuriComposite | Record<string, never>;
  context: StockContext;
  reading: {
    sentences: string[];
    bias: 'Bullish' | 'Bearish' | 'Neutral';
    levels: { inner_support?: number; inner_resistance?: number; support?: number; resistance?: number };
    avoid: { date: string; title: string } | null;
  };
  explain: Record<string, string>;
  clock: CycleClock;
  week: { playbook: string; days: WeekDay[] };
  lunar: { summary: string; days: LunarDay[] };
  overall: string;
  data_source: string;
  demo_data: boolean;
  disclaimer: string;
}

// ── events study ──────────────────────────────────────────────────────────
export interface StudyHorizon {
  n: number;
  mean_pct: number;
  base_pct: number;
  excess_pct: number;
  hit_pct: number;
  base_hit_pct: number;
  t: number;
  abs_pct: number;
  base_abs_pct: number;
}

export interface EventStudy {
  key: string;
  label: string;
  n: number;
  verdict: Verdict;
  vol_verdict?: Verdict;
  vol_ratio?: number;
  vol_t?: number;
  h: Record<string, StudyHorizon>;
  first?: string;
  last?: string;
  recent?: { date: string; r20_pct: number }[];
}

export interface StudiedEvent {
  date: string;
  title: string;
  family: 'lunation' | 'eclipse' | 'station' | 'ingress' | 'aspect' | 'combustion';
  key: string;
  study_key: string;
  importance: 'High' | 'Medium' | 'Low';
  planets: string[];
  classical: string;
  meaning: string;
  action: string;
  tilt: number;
  study: EventStudy;
  expected_5d_pct: number;
  sector_rulers: { planet: string; sectors: string[] }[];
  touches_stock: boolean;
  touched_by: string[];
}

export interface EventsStudy {
  success: boolean;
  symbol: string;
  symbol_name: string;
  sector: string;
  sector_planets: string[];
  broad_market: boolean;
  context: StockContext;
  days: number;
  history_start: string;
  history_days: number;
  events: StudiedEvent[];
  count: number;
  summary: string;
  planets: string[];
  method: string;
  data_source: string;
  demo_data: boolean;
  disclaimer: string;
}

export const cyclesApi = {
  insight: (symbol: string) => getJson<CyclesInsight>(`/api/astro/cycles/insight/${encodeURIComponent(symbol)}`),
  stats: (symbol: string) => getJson<CycleStats>(`/api/astro/cycles/stats/${encodeURIComponent(symbol)}`),
  clock: () => getJson<CycleClock & { success: boolean }>(`/api/astro/cycles/clock`),
  eventsStudy: (symbol: string, days = 45) =>
    getJson<EventsStudy>(
      `/api/astro/events/study?${new URLSearchParams({ symbol, days: String(days) }).toString()}`,
    ),
};

/** "2026-11-09" -> "9 Nov" */
export function shortDate(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso.slice(0, 10) + 'T00:00:00');
  return `${d.getDate()} ${d.toLocaleString('en-US', { month: 'short' })}`;
}

export const VERDICT_STYLE: Record<Verdict, { cls: string; label: string }> = {
  significant: { cls: 'border-[#a8d8bf] bg-[#e2f3e9] text-[#2f7357]', label: 'significant' },
  weak: { cls: 'border-[#eed9b4] bg-[#fdf3dc] text-[#8a6a3a]', label: 'weak hint' },
  noise: { cls: 'border-[#e5dccb] bg-[#f6f1e7] text-[#97795a]', label: 'noise' },
  'too few': { cls: 'border-[#e5dccb] bg-[#f6f1e7] text-[#b39a76]', label: 'too few' },
};
