/**
 * v1.3 strategy area client: TradingAgents debate + Final Strategy.
 * Same-origin /api/astro/* proxy discipline as api.ts.
 */

export type Stance = 'bullish' | 'bearish' | 'neutral' | 'abstain';
export type Rating = 'BUY' | 'OVERWEIGHT' | 'HOLD' | 'UNDERWEIGHT' | 'SELL';

export interface AnalystReport {
  key: 'market' | 'fundamentals' | 'sentiment' | 'news' | 'astro';
  agent: string;
  role: string;
  team: string;
  stance: Stance;
  score: number;
  confidence: number;
  abstain: boolean;
  report: string;
  key_points: { sign: number; text: string }[];
  data_used: string[];
  headlines?: { title: string; publisher: string; date: string; url: string; sentiment: number }[];
}

export interface DebateRound {
  round: number;
  bull: { text: string; point: string };
  bear: { text: string; point: string };
}

export interface TraderPlan {
  agent: string;
  action: string;
  direction: 'long' | 'reduce' | 'neutral';
  entry_low: number;
  entry_high: number;
  entry_mid: number;
  stop: number;
  target_1: number;
  target_2: number;
  reward_risk: number;
  size_units: number;
  size_value: number;
  size_pct_capital?: number;
  risk_budget: number;
  avoid_dates: string[];
  horizon: string;
  view: string;
}

export interface TradingAgentsResult {
  success: boolean;
  symbol: string;
  symbol_name: string;
  mode: string;
  llm_available: boolean;
  rounds: number;
  capital: number;
  spot: number;
  flow: string[];
  analysts: AnalystReport[];
  analyst_composite: number;
  debate: { rounds: DebateRound[]; bull_strength: number; bear_strength: number; bull_points: number; bear_points: number };
  research_manager: { agent: string; recommendation: 'BUY' | 'HOLD' | 'SELL'; score: number; view: string };
  trader: TraderPlan;
  risk_team: {
    views: { agent: string; stance: 'aggressive' | 'neutral' | 'conservative'; size_mult: number; view: string }[];
    score_adjust: number;
    summary: string;
  };
  portfolio_manager: {
    agent: string;
    rating: Rating;
    score: number;
    confidence: number;
    size_multiplier: number;
    final_plan: TraderPlan;
    view: string;
  };
  decision: { rating: Rating; confidence: number; score: number };
  plain_english: string;
  news: { available: boolean; reason?: string; avg_sentiment?: number };
  inputs_status?: Record<string, string>;
  inspired_by: string;
  inspired_by_url: string;
  disclaimer: string;
}

export interface ScoreRow {
  key: string;
  input: string;
  available: boolean;
  score: number;
  signal: 'bullish' | 'bearish' | 'neutral' | 'n/a';
  weight: number;
  reason: string;
}

export interface ChartPlanet {
  name: string;
  signNumber: number;
  degree: number;
  retrograde?: boolean;
  house?: number;
  dignity?: string;
  nakshatra?: string;
  pada?: number;
}

export interface NatalVsToday {
  lagna_sign_number: number;
  lagna_sign: string;
  moon_sign: string;
  rows: {
    graha: string;
    natal_sign: string;
    natal_degree: number;
    natal_house: number;
    natal_nakshatra: string;
    natal_dignity: string;
    natal_retro: boolean;
    strength: number | null;
    today_sign: string;
    today_degree: number;
    today_house: number;
    today_nakshatra: string;
    today_retro: boolean;
    house_from_moon: number;
    gochar: 'favourable' | 'challenging';
  }[];
  activations: { transit: string; natal: string; aspect: string; orb: number; tone: string; meaning: string }[];
  flags: { flag: string; tone: string; text: string }[];
  natal_chart: ChartPlanet[];
  today_chart: ChartPlanet[];
  score: number;
  favourable_count: number;
  interpretation: string;
}

export interface KeyDate {
  date: string;
  days_ahead: number;
  kind: 'sky' | 'timing' | 'dasha' | 'ingress' | 'station';
  title: string;
  weight: number;
  note: string;
}

export interface HorizonPlan {
  days: number;
  label: string;
  score: number;
  stance: string;
  signal: string;
  approach: string[];
  entry_low: number;
  entry_high: number;
  stop: number;
  target_1: number;
  target_2: number;
  expected_range: [number, number];
  position: { risk_pct: number; max_alloc_pct: number; units: number; value: number };
  key_dates: KeyDate[];
  income_focus: string;
  income_band: { low: number; base: number; high: number };
  summary: string;
}

export interface Band {
  low: number;
  base: number;
  high: number;
}

export interface FinalStrategy {
  success: boolean;
  symbol: string;
  symbol_name: string;
  spot: number;
  as_of: string;
  birth: { name?: string; date?: string; time?: string; place?: string };
  inputs_status: Record<string, string>;
  overall: { score: number; signal: string; stance: string; bullish: number; bearish: number; neutral: number; available: number };
  scoreboard: ScoreRow[];
  natal_vs_today: NatalVsToday | null;
  dasha: { md?: string; ad?: string; pd?: string; md_end?: string; ad_end?: string; pd_end?: string; favour?: number };
  agents_decision: { rating: Rating; confidence: number; score: number } | null;
  agents_plain_english: string | null;
  ml: { available: boolean; reason: string; score?: number };
  key_dates: KeyDate[];
  plans: HorizonPlan[];
  income: {
    capital: number;
    target_weekly: number;
    annual_target: number;
    blended_yield: Band;
    required_capital: Band;
    weekly_for_capital: Band;
    monthly_for_capital: Band;
    yearly_for_capital: Band;
    feasible_base: boolean;
    gap_to_base: number;
    verdict: string | null;
    max_sustainable_weekly?: number;
    ladder: { label: string; weight: number; allocation: number; target_weekly: number; yield_base: number }[];
    dasha_note?: string;
    explain: string;
  };
  weekly_routine: { day: string; task: string }[];
  bottom_line: string;
  risk_warning: string;
}

export interface FinalStrategyParams {
  symbol: string;
  name?: string;
  date?: string;
  time?: string;
  place?: string;
  capital?: number;
  target_weekly?: number;
}

const qs = (o: Record<string, string | number | boolean | undefined>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(o)) if (v !== undefined && v !== '') p.set(k, String(v));
  return p.toString();
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

export const strategyApi = {
  agents: (symbol: string, opts: { rounds?: number; capital?: number; llm?: boolean } = {}) =>
    fetch(`/api/astro/agents/${encodeURIComponent(symbol)}?${qs({ rounds: opts.rounds, capital: opts.capital, llm: opts.llm || undefined })}`, {
      cache: 'no-store',
    }).then((r) => jsonOrThrow<TradingAgentsResult>(r)),

  finalStrategy: ({ symbol, ...rest }: FinalStrategyParams) =>
    fetch(`/api/astro/strategy/final/${encodeURIComponent(symbol)}?${qs(rest)}`, { cache: 'no-store' }).then((r) =>
      jsonOrThrow<FinalStrategy>(r),
    ),
};

export const fmtPx = (x: number | null | undefined) => {
  const v = Number(x ?? 0);
  return Math.abs(v) >= 1000 ? v.toLocaleString('en-GB', { maximumFractionDigits: 0 }) : v.toLocaleString('en-GB', { maximumFractionDigits: 2 });
};

export const fmtGbp = (x: number | null | undefined) =>
  `£${Number(x ?? 0).toLocaleString('en-GB', { maximumFractionDigits: 0 })}`;
