'use client';

import type { ClockItem, CycleClock } from '@/lib/astro/api-cycles';
import { shortDate } from '@/lib/astro/api-cycles';

const RING_COLOUR: Record<string, string> = {
  lunar: '#7e6bb0',
  solar: '#c98a2e',
  mercury: '#3f8a6e',
  venus: '#c76b8f',
  mars: '#cf5b54',
  jupiter: '#b8862a',
  saturn: '#5f6f8a',
  jupsat: '#8a6a3a',
};

/** Lunar dial: the Moon's position on the 30-tithi circle with new/full marks. */
function LunarDial({ progress }: { progress: number }) {
  const R = 22;
  const c = 28;
  const a = progress * 2 * Math.PI - Math.PI / 2; // 0 = top (New Moon)
  const x = c + R * Math.cos(a);
  const y = c + R * Math.sin(a);
  const waxing = progress < 0.5;
  return (
    <svg width="56" height="56" viewBox="0 0 56 56" aria-hidden>
      <circle cx={c} cy={c} r={R} fill="none" stroke="#efe7f8" strokeWidth="6" />
      <path
        d={`M ${c} ${c - R} A ${R} ${R} 0 0 1 ${c} ${c + R}`}
        fill="none"
        stroke="#d9cdee"
        strokeWidth="6"
      />
      <text x={c} y={6} textAnchor="middle" fontSize="6" className="fill-[#97795a]">New</text>
      <text x={c} y={55} textAnchor="middle" fontSize="6" className="fill-[#97795a]">Full</text>
      <circle cx={x} cy={y} r="5" fill={waxing ? '#f3dfae' : '#c9bfe0'} stroke="#7e6bb0" strokeWidth="1.5" />
    </svg>
  );
}

function Ring({ progress, colour, retro }: { progress: number; colour: string; retro?: boolean }) {
  const R = 22;
  const C = 2 * Math.PI * R;
  const p = Math.max(0, Math.min(1, progress));
  return (
    <svg width="56" height="56" viewBox="0 0 56 56" aria-hidden>
      <circle cx="28" cy="28" r={R} fill="none" stroke="#f0e4cc" strokeWidth="6" />
      <circle
        cx="28"
        cy="28"
        r={R}
        fill="none"
        stroke={colour}
        strokeWidth="6"
        strokeDasharray={`${C * p} ${C}`}
        strokeLinecap="round"
        transform="rotate(-90 28 28)"
        opacity={retro ? 0.9 : 0.75}
      />
      <text x="28" y="31" textAnchor="middle" fontSize="10" className="fill-[#5c4327] font-mono">
        {retro ? '℞' : `${Math.round(p * 100)}%`}
      </text>
    </svg>
  );
}

function ClockTile({ it }: { it: ClockItem }) {
  const colour = RING_COLOUR[it.id] ?? '#c98a2e';
  const soon = it.days_to_next != null && it.days_to_next <= 7;
  return (
    <div className="flex gap-2.5 rounded-lg border border-[#f0e4cc] bg-[#fffdf6] p-2.5">
      <div className="flex-shrink-0">
        {it.id === 'lunar' ? <LunarDial progress={it.progress} /> : <Ring progress={it.progress} colour={colour} retro={it.retro} />}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-semibold text-[#5c4327]">{it.label}</p>
        <p className="text-[11px] text-[#7c5a2e]">{it.state}</p>
        {it.next_date && (
          <p className="mt-0.5 text-[11px]">
            <span className="text-[#97795a]">Next: </span>
            <span className="font-medium text-[#5c4327]">{it.next_label}</span>
            <span className="text-[#97795a]"> · {shortDate(it.next_date)}{it.id === 'jupsat' ? ` ${it.next_date.slice(0, 4)}` : ''} · </span>
            <span className={`font-mono font-semibold ${soon ? 'text-[#c9553f]' : 'text-[#3f8a6e]'}`}>
              {it.days_to_next != null ? `${it.days_to_next}d` : '—'}
            </span>
          </p>
        )}
        <p className="mt-1 text-[10.5px] leading-snug text-[#97795a]">{it.meaning}</p>
      </div>
    </div>
  );
}

export function CyclesClock({ clock }: { clock: CycleClock }) {
  const turning = clock.items
    .filter((i) => i.days_to_next != null && i.id !== 'jupsat')
    .sort((a, b) => (a.days_to_next ?? 9e9) - (b.days_to_next ?? 9e9));
  const nextTurn = turning[0];
  return (
    <div className="space-y-2">
      {nextTurn && (
        <p className="rounded-md border border-[#e8ddb8] bg-[#fdf8ec] px-2.5 py-1.5 text-[11px] leading-snug text-[#7c5a2e]">
          <span className="font-semibold">Nearest turning point:</span> {nextTurn.next_label} on{' '}
          {shortDate(nextTurn.next_date)} ({nextTurn.days_to_next} days).{' '}
          {turning.filter((t) => (t.days_to_next ?? 99) <= 21).length > 2
            ? 'Several cycles turn within three weeks — a classically "busy" sky; keep position sizes modest.'
            : 'Few cycles turn in the next three weeks — a classically calm sky.'}
        </p>
      )}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {clock.items.map((it) => (
          <ClockTile key={it.id} it={it} />
        ))}
      </div>
      <p className="text-[10px] text-[#b39a76]">
        Rings show how far each cycle has progressed (retrograde ℞ rings: progress between the last and next station).
        Sidereal (Lahiri) positions at noon UT.
      </p>
    </div>
  );
}
