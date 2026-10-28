'use client';

import type { ZooResult } from '@/lib/astro/api-models';

const fmt = (v: number | null | undefined, nd = 2) => (v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(nd)}%`);

/** Ensemble forecast tiles for the next 1 / 5 / 20 sessions with direction odds and a 90% band. */
export function ModelForecast({ fc }: { fc: ZooResult['forecast'] }) {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
      {fc.horizons.map((h) => {
        const pUp = h.p_up ?? 0.5;
        const base = h.hist_up_share ?? 0.5;
        const diff = pUp - base;
        const tone = diff > 0.02 ? 'text-[#2f7357]' : diff < -0.02 ? 'text-[#a34332]' : 'text-[#7c5a2e]';
        const lo = h.band_low_pct ?? 0;
        const hi = h.band_high_pct ?? 0;
        const mid = h.expected_return_pct ?? 0;
        const span = Math.max(hi - lo, 1e-6);
        const midPos = Math.min(100, Math.max(0, ((mid - lo) / span) * 100));
        const zeroPos = Math.min(100, Math.max(0, ((0 - lo) / span) * 100));
        return (
          <div key={h.horizon} className="rounded-md border border-[#f0e4cc] bg-[#fdf8ec]/80 p-2.5">
            <div className="flex items-baseline justify-between">
              <p className="text-[10px] uppercase tracking-wide text-[#b39a76]">
                Next {h.horizon} session{h.horizon > 1 ? 's' : ''}
              </p>
              <p className={`text-[10px] font-medium ${tone}`}>P(up) {(pUp * 100).toFixed(0)}%</p>
            </div>
            <p className={`mt-0.5 font-mono text-lg ${mid >= 0 ? 'text-[#2f7357]' : 'text-[#a34332]'}`}>{fmt(mid)}</p>
            <div className="relative mt-1.5 h-2 rounded-full bg-gradient-to-r from-[#f6c9c0] via-[#f4ead4] to-[#bfe3d1]">
              <span className="absolute top-[-2px] h-3 w-px bg-[#97795a]" style={{ left: `${zeroPos}%` }} />
              <span
                className="absolute top-[-3px] h-3.5 w-1.5 -translate-x-1/2 rounded-sm bg-[#d98324]"
                style={{ left: `${midPos}%` }}
              />
            </div>
            <div className="mt-0.5 flex justify-between font-mono text-[9px] text-[#97795a]">
              <span>{fmt(lo, 1)}</span>
              <span>90% band</span>
              <span>{fmt(hi, 1)}</span>
            </div>
            <p className="mt-1 text-[10px] leading-snug text-[#97795a]">
              {diff > 0.02
                ? `Odds of a rise are ${((diff) * 100).toFixed(0)} pts above this stock's usual ${(base * 100).toFixed(0)}% — a mild bullish tilt.`
                : diff < -0.02
                  ? `Odds of a rise are ${((-diff) * 100).toFixed(0)} pts below the usual ${(base * 100).toFixed(0)}% — a mild bearish tilt.`
                  : `Odds are in line with the usual ${(base * 100).toFixed(0)}% — no tilt.`}{' '}
              The band dwarfs the forecast, so expect the outcome to be driven by noise.
            </p>
            <p className="mt-0.5 text-[9px] text-[#b39a76]">{h.p_up_source}</p>
          </div>
        );
      })}
    </div>
  );
}
