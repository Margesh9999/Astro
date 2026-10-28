'use client';

import { useEffect, useState } from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import type { Insight } from '@/lib/astro/api-quant';
import { Eye, Lightbulb, Target } from 'lucide-react';

/* Shared building blocks for the v1.3 Quant Desk tabs (pastel Vedic theme). */

export const TIP_STYLE = {
  background: '#fffdf6',
  border: '1px solid #ecdec2',
  borderRadius: 8,
  fontSize: 11,
} as const;

export const AXIS_TICK = { fontSize: 9, fill: '#b39a76' } as const;

export const C = {
  green: '#3f8a6e',
  red: '#c9553f',
  amber: '#c98a2e',
  brown: '#5c4327',
  text: '#7c5a2e',
  muted: '#97795a',
  faint: '#b39a76',
  teal: '#4fa8a0',
  lilac: '#9b8ac4',
  rose: '#d96f85',
  copper: '#b0763a',
} as const;

export function ChartTitle({ children }: { children: React.ReactNode }) {
  return <p className="mb-1 text-xs font-medium text-[#5c4327]">{children}</p>;
}

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-1 flex items-center gap-2">
      <p className="font-display text-[11px] font-semibold uppercase tracking-[0.16em] text-[#97795a]">{children}</p>
      <div className="h-px flex-1 bg-gradient-to-r from-[#e3cfa4] to-transparent" />
    </div>
  );
}

/** The house plain-English triplet: what it shows / what it means / what to do. */
export function InsightBox({ insight }: { insight: Insight | null | undefined }) {
  if (!insight) return null;
  return (
    <div className="mt-2 space-y-1 rounded-lg border border-[#e8ddb8] bg-[#fdf8ec] px-2.5 py-2 text-[11px] leading-relaxed">
      {insight.shows && (
        <p className="flex items-start gap-1.5 text-[#8a7350]">
          <Eye className="mt-0.5 h-3 w-3 flex-shrink-0 text-[#b39a76]" />
          <span><span className="font-semibold">Shows: </span>{insight.shows}</span>
        </p>
      )}
      {insight.means && (
        <p className="flex items-start gap-1.5 text-[#7c5a2e]">
          <Lightbulb className="mt-0.5 h-3 w-3 flex-shrink-0 text-[#c98a2e]" />
          <span><span className="font-semibold">Means: </span>{insight.means}</span>
        </p>
      )}
      {insight.action && (
        <p className="flex items-start gap-1.5 text-[#5c4327]">
          <Target className="mt-0.5 h-3 w-3 flex-shrink-0 text-[#3f8a6e]" />
          <span><span className="font-semibold">Do: </span>{insight.action}</span>
        </p>
      )}
    </div>
  );
}

export function Stat({ label, value, color, sub }: { label: string; value: React.ReactNode; color?: string; sub?: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-[#f0e4cc] bg-[#fffdf6] px-2 py-1.5">
      <p className="truncate text-[9px] uppercase tracking-wide text-[#b39a76]">{label}</p>
      <p className="font-mono text-sm font-semibold" style={{ color: color ?? '#5c4327' }}>{value}</p>
      {sub && <p className="truncate text-[9px] text-[#b39a76]">{sub}</p>}
    </div>
  );
}

export function signColor(v: number | null | undefined) {
  if (v === null || v === undefined) return C.muted;
  return v > 0 ? C.green : v < 0 ? C.red : C.amber;
}

export function fmtSigned(v: number | null | undefined, d = 1, suffix = '%') {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return `${v > 0 ? '+' : ''}${v.toFixed(d)}${suffix}`;
}

/** diverging green/red cell colour; `scale` = |value| that reaches full colour */
export function divergeStyle(v: number | null | undefined, scale: number): React.CSSProperties {
  if (v === null || v === undefined || Number.isNaN(v)) return { background: '#faf4e4', color: '#c9b591' };
  const x = Math.max(-1, Math.min(1, v / scale));
  if (x >= 0) return { background: `rgba(74,154,126,${0.08 + x * 0.6})`, color: x > 0.6 ? '#13352b' : '#22423a' };
  return { background: `rgba(207,91,84,${0.08 + -x * 0.6})`, color: -x > 0.6 ? '#4a1a15' : '#5c2620' };
}

/** sequential amber cell colour from 0..max */
export function seqStyle(v: number | null | undefined, max: number): React.CSSProperties {
  if (v === null || v === undefined || Number.isNaN(v)) return { background: '#faf4e4', color: '#c9b591' };
  const x = Math.max(0, Math.min(1, v / max));
  return { background: `rgba(201,138,46,${0.06 + x * 0.66})`, color: x > 0.65 ? '#3b2610' : '#6b4a22' };
}

export function SignalPill({ signal, small }: { signal: string; small?: boolean }) {
  const cls =
    signal === 'BUY' ? 'border-[#a8d8bf] bg-[#e2f3e9] text-[#2f7357]'
    : signal === 'SELL' ? 'border-[#ecc0b6] bg-[#f9e8e4] text-[#a14d3c]'
    : 'border-[#e3cf9f] bg-[#f7ecd4] text-[#8a6a3a]';
  return (
    <span className={`inline-block rounded border font-mono font-semibold ${small ? 'px-1 text-[9px]' : 'px-1.5 py-0.5 text-[10px]'} ${cls}`}>
      {signal}
    </span>
  );
}

/** Generic heat grid with sticky first column; scrolls horizontally on phones. */
export function HeatGrid({
  rows,
  cols,
  values,
  style,
  fmt,
  title,
  minWidth = 0,
  maxHeight,
  extraCol,
  footer,
}: {
  rows: (string | number)[];
  cols: string[];
  values: (number | null)[][];
  style: (v: number | null) => React.CSSProperties;
  fmt: (v: number | null) => string;
  title?: (r: string | number, c: string, v: number | null) => string;
  minWidth?: number;
  maxHeight?: number;
  extraCol?: { label: string; values: (number | null)[]; style: (v: number | null) => React.CSSProperties; fmt: (v: number | null) => string };
  footer?: { label: string; values: (number | null)[]; fmt: (v: number | null) => string; style?: (v: number | null) => React.CSSProperties }[];
}) {
  return (
    <div className="warm-scroll overflow-auto rounded-md" style={maxHeight ? { maxHeight } : undefined}>
      <table className="w-full border-separate border-spacing-0.5 text-center text-[10px]" style={{ minWidth }}>
        <thead className="sticky top-0 z-10 bg-[#fffaf0]">
          <tr>
            <th className="sticky left-0 z-20 bg-[#fffaf0]" />
            {cols.map((c) => (
              <th key={c} className="whitespace-nowrap px-0.5 font-medium text-[#b39a76]">{c}</th>
            ))}
            {extraCol && <th className="px-1 font-semibold text-[#97795a]">{extraCol.label}</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((rl, ri) => (
            <tr key={String(rl)}>
              <td className="sticky left-0 z-10 whitespace-nowrap bg-[#fffaf0] pr-1 text-right font-mono text-[#97795a]">
                <span className="block max-w-[34vw] truncate sm:max-w-none" title={String(rl)}>{rl}</span>
              </td>
              {values[ri].map((v, ci) => (
                <td key={ci} className="rounded font-mono" style={{ ...style(v), padding: '3px 2px' }}
                    title={title ? title(rl, cols[ci], v) : `${rl} · ${cols[ci]}: ${fmt(v)}`}>
                  {fmt(v)}
                </td>
              ))}
              {extraCol && (
                <td className="rounded font-mono font-semibold" style={{ ...extraCol.style(extraCol.values[ri]), padding: '3px 4px' }}>
                  {extraCol.fmt(extraCol.values[ri])}
                </td>
              )}
            </tr>
          ))}
        </tbody>
        {footer && (
          <tfoot>
            {footer.map((f) => (
              <tr key={f.label}>
                <td className="sticky left-0 whitespace-nowrap bg-[#fffaf0] pr-1 text-right text-[9px] font-semibold uppercase text-[#97795a]">{f.label}</td>
                {f.values.map((v, i) => (
                  <td key={i} className="rounded font-mono font-semibold" style={{ ...(f.style ? f.style(v) : { color: '#5c4327' }), padding: '3px 2px' }}>
                    {f.fmt(v)}
                  </td>
                ))}
                {extraCol && <td />}
              </tr>
            ))}
          </tfoot>
        )}
      </table>
    </div>
  );
}

/** Fetch-on-mount hook keyed by symbol (responses are memoised in api-quant). */
export function useQuant<T>(symbol: string, fetcher: (s: string) => Promise<T>) {
  const [state, setState] = useState<{ symbol: string; data?: T; error?: string } | null>(null);
  useEffect(() => {
    let alive = true;
    fetcher(symbol)
      .then((data) => alive && setState({ symbol, data }))
      .catch((e) => alive && setState({ symbol, error: String(e?.message ?? e) }));
    return () => {
      alive = false;
    };
  }, [symbol, fetcher]);
  const fresh = state?.symbol === symbol ? state : null;
  return { data: fresh?.data ?? null, error: fresh?.error ?? null, loading: !fresh };
}

export function LoadState({ loading, error, what }: { loading: boolean; error: string | null; what: string }) {
  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        <p className="text-[11px] text-[#b39a76]">Crunching {what} — first load can take a few seconds…</p>
        <Skeleton className="h-40 w-full bg-[#efdfbc]" />
        <Skeleton className="h-24 w-full bg-[#efdfbc]" />
      </div>
    );
  }
  if (error) {
    return <p className="rounded-md border border-[#eecfc7] bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">{what} unavailable — {error}</p>;
  }
  return null;
}

export function shortDate(d: string) {
  return d.length >= 7 ? `${d.slice(2, 4)}-${d.slice(5, 7)}` : d;
}
