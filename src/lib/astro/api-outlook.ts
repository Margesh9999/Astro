/**
 * v1.6 Market Outlook client: astrology-based sector forecast per horizon (each call back-tested
 * on the sector's real prices) and an income plan sized by the jataka's strategy fits.
 * Same-origin /api/astro/* proxy only.
 */
import type { BirthInput } from './api-jataka';

export type Horizon = 'week' | 'month' | 'year';
export type OutlookDirection = 'up' | 'down' | 'range';

export interface Driver { planet: string; state: string; score: number; effect: '+' | '−' | '·' }
export interface SectorBacktest {
  n: number;
  windows?: number;
  hit_pct?: number;
  expected_pct?: number;
  z?: number;
  verdict: string;
  base_up_pct?: number;
  avg_ret_up_calls_pct?: number | null;
  avg_ret_down_calls_pct?: number | null;
  since?: string;
}
export interface SectorCall {
  sector: string;
  z: number;
  direction: OutlookDirection;
  strength_pct: number;
  drivers: Driver[];
  changes: string[];
  proxy: string;
  fno: string[];
  etf: string | null;
  backtest: SectorBacktest;
  options: { income: string; directional: string; trust: string };
}
export interface IncomeBucket {
  horizon: Horizon;
  label: string;
  how: string;
  ideas: { name: string; kind: string; yield: string }[];
  risk: string;
  allocation_pct: number;
  amount: number;
  chart_fit: number | null;
  market_bias: OutlookDirection | null;
}
export interface MarketOutlook {
  success: boolean;
  as_of: string;
  horizons: Record<Horizon, { sessions: number; sectors: SectorCall[]; summary: string }>;
  income_plan: {
    buckets: IncomeBucket[];
    split_source: string;
    personal_picks: { horizon: Horizon; sector: string; why: string }[];
    natal_sectors: string[];
  };
  jataka: { used: boolean; name?: string };
  method: string;
  disclaimer: string;
}

export const outlookApi = {
  get: async (birth: BirthInput, capital: number): Promise<MarketOutlook> => {
    const p = new URLSearchParams({ capital: String(capital), name: birth.name, birth_date: birth.date, time: birth.time, place: birth.place });
    if (birth.lat != null) p.set('lat', String(birth.lat));
    if (birth.lon != null) p.set('lon', String(birth.lon));
    if (birth.tz != null) p.set('tz', String(birth.tz));
    if (birth.tz_name) p.set('tz_name', birth.tz_name);
    p.set('node', birth.node);
    p.set('ayanamsa', birth.ayanamsa);
    const res = await fetch(`/api/astro/outlook?${p}`, { cache: 'no-store' });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        detail = (await res.json()).detail ?? detail;
      } catch {
        /* keep status text */
      }
      throw new Error(detail);
    }
    return res.json();
  },
};
