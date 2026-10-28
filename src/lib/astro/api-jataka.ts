/**
 * v1.3 jataka API client + types (birth form, Stock × Kundli, money plan, Sky Today observer).
 * Same-origin /api/astro/* proxy → FastAPI /api/v1/*.
 */
import type { JatakaReport, PlanetaryResponse } from './types';

// ───────────────────────── birth input + persistence ─────────────────────────
export interface BirthInput {
  name: string;
  date: string;
  time: string;
  place: string;
  /** manual overrides — blank means "use the gazetteer" */
  lat?: number | null;
  lon?: number | null;
  /** manual UTC offset in hours (no DST logic) — blank means IANA zone of the place */
  tz?: number | null;
  tz_name?: string;
  node: 'mean' | 'true';
  ayanamsa: 'lahiri' | 'raman' | 'kp' | 'tropical';
}

export const DEFAULT_BIRTH: BirthInput = {
  name: 'Margesh',
  date: '1994-04-23',
  time: '06:45',
  place: 'Vallabh Vidyanagar, Gujarat, India',
  lat: null,
  lon: null,
  tz: null,
  tz_name: '',
  node: 'mean',
  ayanamsa: 'lahiri',
};

export interface MoneyInputs {
  capital: number;
  target_weekly: number;
  monthly_savings: number;
  base_return: number;
}
export const DEFAULT_MONEY: MoneyInputs = { capital: 50000, target_weekly: 500, monthly_savings: 500, base_return: 0.08 };

const BIRTH_KEY = 'astrotrader.jataka.birth.v1';
const MONEY_KEY = 'astrotrader.jataka.money.v1';

function readLS<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    return { ...fallback, ...(JSON.parse(raw) as Partial<T>) };
  } catch {
    return fallback;
  }
}
function writeLS(key: string, v: unknown) {
  try {
    window.localStorage.setItem(key, JSON.stringify(v));
  } catch {
    /* private mode / blocked storage — the form still works */
  }
}
export const loadBirth = () => readLS<BirthInput>(BIRTH_KEY, DEFAULT_BIRTH);
export const saveBirth = (b: BirthInput) => writeLS(BIRTH_KEY, b);
export const loadMoney = () => readLS<MoneyInputs>(MONEY_KEY, DEFAULT_MONEY);
export const saveMoney = (m: MoneyInputs) => writeLS(MONEY_KEY, m);

function qs(params: Record<string, string | number | boolean | null | undefined>) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue;
    p.set(k, String(v));
  }
  return p.toString();
}

async function json<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let detail = `HTTP ${r.status}`;
    try {
      const d = await r.json();
      if (d?.detail) detail = typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return r.json() as Promise<T>;
}

const birthParams = (b: BirthInput) => ({
  name: b.name, date: b.date, time: b.time, place: b.place,
  lat: b.lat ?? undefined, lon: b.lon ?? undefined, tz: b.tz ?? undefined,
  tz_name: b.tz_name || undefined, node: b.node, ayanamsa: b.ayanamsa,
});

// ───────────────────────── types ─────────────────────────
export interface JatakaPlaceV13 { name: string; lat: number; lon: number; tz: number; tz_name: string; country: string }

export interface DashaPeriodNow { lord: string; start: string; end: string; years: number; meaning: string }
export interface PlanFit { name: string; fit: number; why: string; drivers: string[] }
export interface PlanStrategy { key: string; label: string; fit: number; returns: { low: number; base: number; high: number }; why: string }
export interface Band { low: number; base: number; high: number }
export interface IncomeRow {
  strategy: string; key: string; fit: number;
  annual_return_pct: Band; weekly: Band; monthly: Band; yearly: Band; capital_for_target: number | null;
}
export interface WealthHouse {
  house: number; title: string; theme: string; sign: string; lord: string; lord_house: number;
  lord_sign: string; lord_dignity: string; occupants: string[]; bindus: number | null; score: number;
  tone: 'strong' | 'average' | 'weak'; plain: string;
}
export interface LifetimeRow { age: number; year: number; md: string | null; ad: string | null; dasha_mod: number; low: number; base: number; high: number }
export interface JatakaPlan {
  composite_strength: Record<string, { score: number; parts: Record<string, number> }>;
  wealth_houses: WealthHouse[];
  house_strength: Record<string, number>;
  markets: PlanFit[]; sectors: PlanFit[]; strategies: PlanStrategy[];
  dasha_factor: number; dasha_now: { md: string | null; ad: string | null };
  income: { capital: number; target_weekly: number; rows: IncomeRow[]; target_line: string; method: string };
  lifetime: {
    age_now: number;
    inputs: { capital: number; monthly_savings: number; base_return: number; retire_age: number; end_age: number };
    rows: LifetimeRow[];
    milestones: { age: number; year: number; md: string | null; low: number; base: number; high: number }[];
    plain: string; method: string;
  };
  summary: string; disclaimer: string;
  error?: string;
}

export interface PDNode { lord: string; glyph: string; start: string; end: string; years: number; balance_at_birth?: boolean }
export interface ADNode extends PDNode { pratyantardashas: PDNode[] }
export interface MDNode { lord: string; glyph: string; start: string; end: string; years: number; antardashas: ADNode[] }

export type JatakaReportV13 = Omit<JatakaReport, 'dasha_tree' | 'birth'> & {
  birth: JatakaReport['birth'] & { tz_name: string; dst: boolean; place_resolved: boolean };
  settings: { ayanamsa: string; node: string; house_system: string };
  dasha_tree: {
    first_lord: string; balance_years: number; moon_nakshatra_index: number; pada: number;
    elapsed_years_at_birth: number; year_days: number; mahadashas: MDNode[];
  };
  current_dasha: JatakaReport['current_dasha'] & {
    pd_start: string | null; pd_end: string | null;
    trading: { mahadasha: DashaPeriodNow | null; antardasha: DashaPeriodNow | null; pratyantardasha: DashaPeriodNow | null };
  };
  positions: Record<string, JatakaReport['positions'][string] & { combust?: boolean; sun_separation?: number }>;
  plan: JatakaPlan;
};

export interface PeriodStat {
  days: number; total_return: number | null; ann_return: number | null; vol: number | null; hit_rate: number | null;
  from: string; to: string;
}
export interface LordStat { lord: string; periods: number; days: number; ann_return: number | null; hit_rate: number | null; vol: number | null }
export interface TransitRow {
  transit: string; natal: string; natal_label: string; contact: string; label: string; days: number;
  fwd_mean_pct: number | null; edge_pct: number | null; hit_rate: number | null; t_stat: number | null;
  verdict: 'better' | 'worse' | 'no clear edge'; active_now: boolean;
  window_90d: { from: string; to: string; until_after_window: boolean } | null;
}
export interface SynastryContact { stock: string; native: string; aspect: string; orb: number | null; points: number | null; tone: string; meaning: string }
export interface StockKundli {
  success: boolean; error?: string;
  symbol: string; symbol_name: string;
  history: { start: string; end: string; days: number };
  data_note: string; native: string;
  dasha_now: { mahadasha: DashaPeriodNow | null; antardasha: DashaPeriodNow | null; pratyantardasha: DashaPeriodNow | null };
  periods: {
    mahadashas: (PeriodStat & { lord: string; start: string; end: string; running: boolean })[];
    antardashas: (PeriodStat & { md: string; lord: string; label: string; start: string; end: string; running: boolean })[];
    ad_by_lord: LordStat[]; pd_by_lord: LordStat[]; baseline: PeriodStat | null; plain: string; note: string;
  };
  transits: {
    rows: TransitRow[]; active_now: TransitRow[]; upcoming: TransitRow[];
    baseline: { fwd_mean_pct: number | null; hit_rate: number | null; days: number };
    active_edge_pct: number | null; plain: string; method: string;
  };
  synastry: {
    stock_birth: { date: string; note: string; source: string; positions: Record<string, { sign: string; degree: number | null }> };
    contacts: SynastryContact[];
    house_overlay: { stock: string; house: number; points: number; meaning: string }[];
    score: number; plain: string; note: string;
  };
  verdict: {
    score: number; tone: 'favourable' | 'neutral' | 'unfavourable';
    components: { dasha_history: number; transits: number; synastry: number };
    actions: string[];
    windows: { label: string; from: string; to: string; edge_pct: number | null; kind: 'favourable' | 'caution' }[];
    plain: string; disclaimer: string;
  };
}

export interface SkyObserver { lat: number; lon: number; place: string; utc: string; node: string; ayanamsa: string }
export type PlanetaryResponseV13 = PlanetaryResponse & { observer?: SkyObserver | null };

// ───────────────────────── calls ─────────────────────────
export const jatakaApi = {
  places: (q: string) =>
    fetch(`/api/astro/jataka/places?${qs({ q })}`, { cache: 'no-store' }).then((r) =>
      json<{ success: boolean; places: JatakaPlaceV13[] }>(r),
    ),
  report: (symbol: string, b: BirthInput, m: MoneyInputs) =>
    fetch(`/api/astro/jataka/report?${qs({ symbol, ...birthParams(b), ...m })}`, { cache: 'no-store' }).then((r) =>
      json<JatakaReportV13>(r),
    ),
  stockCorrelation: (symbol: string, b: BirthInput) =>
    fetch(`/api/astro/jataka/stock-correlation?${qs({ symbol, ...birthParams(b) })}`, { cache: 'no-store' }).then((r) =>
      json<StockKundli>(r),
    ),
  skyNow: (o: { lat?: number; lon?: number; place?: string }) => {
    const today = new Date().toISOString().slice(0, 10);
    return fetch(`/api/astro/planetary/${today}?${qs({ vedic: true, at: 'now', ...o })}`, { cache: 'no-store' }).then((r) =>
      json<PlanetaryResponseV13>(r),
    );
  },
};
