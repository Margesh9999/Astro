/**
 * v1.4 Panchang client — five limbs, Rahu Kaal, the symbol's historical stats for
 * today's paksha / nakshatra, and the forward market-weather calendar (+ .ics).
 * Same proxy discipline as api.ts: same-origin /api/astro/* only.
 */
import type { CycleBucketRow } from './api-cycles';

export interface Span { start: string; end: string }
export interface Panchang {
  success: boolean;
  date: string;
  place: string;
  lat: number;
  lon: number;
  tz_hours: number;
  sunrise: string;
  sunset: string;
  vara: { name: string; lord: string; weekday: string };
  tithi: { index: number; paksha: string; name: string; label: string; ends: string };
  nakshatra: { index: number; name: string; pada: number; ends: string; lord: string };
  yoga: { index: number; name: string; ends: string; auspicious: boolean };
  karana: { index: number; name: string; ends: string };
  moon_sign: string;
  sun_sign: string;
  rahu_kaal: Span;
  yamaganda: Span;
  gulika: Span;
  abhijit: Span;
  flags: string[];
  tone: 'favourable' | 'mixed' | 'caution';
  notes: string[];
  plain_english: string;
  disclaimer: string;
  symbol_context?: {
    symbol: string;
    name: string;
    baseline: { mean_pct: number; hit_pct: number; days: number };
    paksha?: CycleBucketRow | null;
    nakshatra?: CycleBucketRow | null;
    plain_english?: string;
    data_source: string;
  } | null;
}

export interface CalendarRow {
  date: string;
  weekday: string;
  tithi: string;
  nakshatra: string;
  yoga: string;
  karana: string;
  rahu_kaal: string;
  flags: string[];
  tone: 'favourable' | 'mixed' | 'caution';
  is_weekend: boolean;
}
export interface SkyEvent { when: string; kind: string; body: string; title: string; meaning: string }
export interface MarketCalendar {
  success: boolean;
  start: string;
  days: number;
  place: string;
  rows: CalendarRow[];
  events: SkyEvent[];
  weekday_tone_counts: Record<'favourable' | 'mixed' | 'caution', number>;
  how_to_read: string;
}

export interface Place { label: string; lat: number; lon: number; tz: number }
export const PLACES: Place[] = [
  { label: 'Mumbai (NSE / BSE)', lat: 19.076, lon: 72.8777, tz: 5.5 },
  { label: 'Vallabh Vidyanagar', lat: 22.5347, lon: 73.13, tz: 5.5 },
  { label: 'London (LSE)', lat: 51.5074, lon: -0.1278, tz: 0 },
  { label: 'New York (NYSE)', lat: 40.7128, lon: -74.006, tz: -5 },
];

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

const qs = (p: Record<string, string | number | undefined>) => {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(p)) if (v !== undefined && v !== '') s.set(k, String(v));
  return s.toString();
};

const loc = (pl: Place) => ({ lat: pl.lat, lon: pl.lon, tz: pl.tz, place: pl.label });

export const panchangApi = {
  today: (pl: Place, date?: string, symbol?: string) =>
    getJson<Panchang>(`/api/astro/panchang?${qs({ ...loc(pl), date, symbol })}`),
  calendar: (pl: Place, days = 30, start?: string) =>
    getJson<MarketCalendar>(`/api/astro/panchang/calendar?${qs({ ...loc(pl), days, start })}`),
  icsUrl: (pl: Place, days = 30) => `/api/astro/panchang/calendar.ics?${qs({ ...loc(pl), days })}`,
};
