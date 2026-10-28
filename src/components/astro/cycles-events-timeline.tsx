'use client';

import { useEffect, useRef, useState } from 'react';
import type { StudiedEvent } from '@/lib/astro/api-cycles';
import { shortDate } from '@/lib/astro/api-cycles';

const VERDICT_ALPHA: Record<string, number> = { significant: 1, weak: 0.75, noise: 0.35, 'too few': 0.2 };
const IMP_W: Record<string, number> = { High: 7, Medium: 5, Low: 3 };

/**
 * 45-day event timeline: one marker per event on a date axis; bar height =
 * the stock's historical average excess return over the chosen horizon after
 * past occurrences (green up / red down), faded when statistically noise.
 */
export function CyclesEventsTimeline({
  events,
  days,
  horizon,
  start,
  onSelect,
  selected,
}: {
  events: StudiedEvent[];
  days: number;
  horizon: '1' | '5' | '20';
  start: string;
  onSelect?: (idx: number) => void;
  selected?: number | null;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(360);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => setW(Math.max(260, Math.floor(entries[0].contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const H = 150;
  const padL = 30;
  const padR = 8;
  const mid = 70;
  const amp = 52;
  const t0 = new Date(start + 'T00:00:00').getTime();
  const dayOf = (iso: string) => Math.round((new Date(iso + 'T00:00:00').getTime() - t0) / 86400000);
  const xOf = (d: number) => padL + (d / days) * (w - padL - padR);
  const vals = events.map((e) => e.study.h?.[horizon]?.excess_pct ?? 0);
  const maxAbs = Math.max(0.25, ...vals.map((v) => Math.abs(v)));
  // stack same-day markers side by side
  const seen: Record<number, number> = {};
  const ticks = Array.from({ length: Math.floor(days / 7) + 1 }, (_, i) => i * 7);

  return (
    <div ref={ref} className="w-full">
      <svg width={w} height={H} role="img" aria-label="Event timeline with historical expected move">
        <line x1={padL} x2={w - padR} y1={mid} y2={mid} stroke="#b39a76" strokeWidth="1" />
        {[1, -1].map((s) => (
          <text key={s} x={padL - 4} y={mid - s * amp + 3} textAnchor="end" fontSize="9" fill="#97795a">
            {s > 0 ? '+' : '−'}
            {maxAbs.toFixed(1)}%
          </text>
        ))}
        <text x={padL - 4} y={mid + 3} textAnchor="end" fontSize="9" fill="#97795a">0</text>
        {ticks.map((d) => {
          const iso = new Date(t0 + d * 86400000).toISOString().slice(0, 10);
          return (
            <g key={d}>
              <line x1={xOf(d)} x2={xOf(d)} y1={mid - amp - 4} y2={mid + amp + 4} stroke="#f0e4cc" strokeDasharray="2 3" />
              <text x={xOf(d)} y={H - 4} textAnchor="middle" fontSize="9" fill="#97795a">
                {d === 0 ? 'today' : shortDate(iso)}
              </text>
            </g>
          );
        })}
        {events.map((e, i) => {
          const d = dayOf(e.date);
          const k = seen[d] ?? 0;
          seen[d] = k + 1;
          const v = vals[i];
          const x = xOf(d) + (k % 2 === 0 ? 1 : -1) * Math.ceil(k / 2) * 5;
          const h = (Math.abs(v) / maxAbs) * amp;
          const pos = v >= 0;
          const alpha = VERDICT_ALPHA[e.study.verdict] ?? 0.3;
          const bw = IMP_W[e.importance] ?? 4;
          const fill = pos ? `rgba(74,154,126,${alpha})` : `rgba(207,91,84,${alpha})`;
          const sel = selected === i;
          return (
            <g key={i} onClick={() => onSelect?.(i)} style={{ cursor: 'pointer' }}>
              <title>
                {`${shortDate(e.date)} · ${e.title}\n${horizon}-session excess vs normal: ${v >= 0 ? '+' : ''}${v.toFixed(2)}% (${e.study.verdict}, n=${e.study.n})`}
              </title>
              <rect
                x={x - bw / 2}
                y={pos ? mid - Math.max(h, 1.5) : mid}
                width={bw}
                height={Math.max(h, 1.5)}
                rx={1.5}
                fill={fill}
                stroke={sel ? '#4a3525' : 'none'}
              />
              <circle
                cx={x}
                cy={pos ? mid + 7 : mid - 7}
                r={e.importance === 'High' ? 3.2 : 2.2}
                fill={e.touches_stock ? '#7e6bb0' : '#c98a2e'}
                opacity={e.importance === 'Low' ? 0.5 : 0.9}
              />
              {/* wide invisible hit-box for touch */}
              <rect x={x - 6} y={mid - amp - 4} width={12} height={2 * amp + 8} fill="transparent" />
            </g>
          );
        })}
      </svg>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-[#97795a]">
        <span>bar = avg {horizon}-session move vs normal after past occurrences</span>
        <span><span className="text-[#3f8a6e]">■</span> up <span className="text-[#c9553f]">■</span> down · faded = noise</span>
        <span><span className="text-[#7e6bb0]">●</span> touches this stock&apos;s sector ruler</span>
      </div>
    </div>
  );
}
