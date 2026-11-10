'use client';

import { useEffect, useState } from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowDownRight, ArrowRight, ArrowUpRight, CalendarCheck, Clock, Coins } from 'lucide-react';

interface Brief {
  success: boolean;
  date: string;
  place: string;
  day: null | {
    tone: 'favourable' | 'mixed' | 'caution';
    vara: { name: string; weekday: string; lord: string };
    tithi: string;
    nakshatra: string;
    rahu_kaal: { start: string; end: string };
    abhijit: { start: string; end: string };
    flags: string[];
  };
  week: null | {
    lean: 'up' | 'down' | 'range';
    lean_z: number;
    strongest: string;
    weakest: string;
    backed: { sector: string; direction: string; verdict: string }[];
  };
  trade: null | {
    strategy: string;
    spot: number;
    legs: Record<string, number>;
    credit_pts: number;
    max_loss_pts: number;
    advice: string;
    win_rate_pct: number;
    worst_week_on_margin_pct: number;
    positive_months_pct: number;
  };
  disclaimer: string;
}

const TONE = {
  favourable: { label: 'Clear day', cls: 'text-[#4f7a3f]' },
  mixed: { label: 'Mixed day', cls: 'text-[#8a6a2a]' },
  caution: { label: 'Stand-aside day', cls: 'text-[#a14d3c]' },
};
const LEAN = {
  up: { label: 'Leans up', Icon: ArrowUpRight, cls: 'text-[#4f7a3f]' },
  down: { label: 'Leans down', Icon: ArrowDownRight, cls: 'text-[#a14d3c]' },
  range: { label: 'Range-bound', Icon: ArrowRight, cls: 'text-[#8a6a2a]' },
};

function Tile({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-[#ecdec2] bg-[#fffdf6]/90 px-3 py-2.5 shadow-sm">
      <p className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-[#b39a76]">
        {icon} {title}
      </p>
      <div className="text-xs leading-relaxed text-[#6b4f2e]">{children}</div>
    </div>
  );
}

export function TodayBriefCard() {
  const [b, setB] = useState<Brief | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    fetch('/api/astro/brief', { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((j: Brief) => live && setB(j))
      .catch((e) => live && setErr(String(e?.message ?? e)));
    return () => {
      live = false;
    };
  }, []);

  if (err) return null; // the detailed sections below still work on their own
  if (!b) return <Skeleton className="h-24 w-full bg-[#f3e6cc]" />;
  const short = b.trade && Object.entries(b.trade.legs).find(([k]) => k.startsWith('short'));
  return (
    <section aria-label="Today's brief">
      <div className="mb-2 flex items-center gap-3">
        <h2 className="font-display text-sm font-semibold uppercase tracking-[0.2em] text-[#97795a]">✦ Today&apos;s Brief</h2>
        <span className="text-[11px] text-[#b39a76]">{b.date} · {b.place}</span>
        <div className="h-px flex-1 bg-gradient-to-r from-[#e3cfa4] to-transparent" />
      </div>
      <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
        <Tile icon={<CalendarCheck className="h-3.5 w-3.5" />} title="The day">
          {b.day ? (
            <>
              <p className={`text-sm font-semibold ${TONE[b.day.tone].cls}`}>{TONE[b.day.tone].label}</p>
              <p>{b.day.vara.weekday} · {b.day.tithi} · Moon in {b.day.nakshatra}</p>
              <p className="flex items-center gap-1">
                <Clock className="h-3 w-3" /> Rahu Kaal {b.day.rahu_kaal.start}–{b.day.rahu_kaal.end} · Abhijit {b.day.abhijit.start}–{b.day.abhijit.end}
              </p>
            </>
          ) : (
            <p>Panchang unavailable right now.</p>
          )}
        </Tile>
        <Tile icon={<ArrowUpRight className="h-3.5 w-3.5" />} title="This week's market lean">
          {b.week ? (
            (() => {
              const L = LEAN[b.week.lean];
              return (
                <>
                  <p className={`flex items-center gap-1 text-sm font-semibold ${L.cls}`}>
                    <L.Icon className="h-4 w-4" /> {L.label}
                  </p>
                  <p>Strongest: {b.week.strongest} · weakest: {b.week.weakest}</p>
                  <p className="text-[#97795a]">
                    {b.week.backed.length
                      ? `History gives some support to: ${b.week.backed.map((x) => `${x.sector} ${x.direction}`).join(', ')}.`
                      : 'No sector call this week has support in past prices.'}
                  </p>
                </>
              );
            })()
          ) : (
            <p>Outlook unavailable right now.</p>
          )}
        </Tile>
        <Tile icon={<Coins className="h-3.5 w-3.5" />} title="This week's income trade">
          {b.trade ? (
            <>
              <p className="text-sm font-semibold text-[#7c4a12]">
                Nifty {b.trade.strategy.split(' (')[0].toLowerCase()}
                {short ? `, short ~${Math.round(short[1]).toLocaleString()}` : ''}
              </p>
              <p>
                Credit ~{b.trade.credit_pts} pts, max loss {b.trade.max_loss_pts} pts. Since 2009 it won {b.trade.win_rate_pct}% of
                weeks;{' '}
                {b.trade.worst_week_on_margin_pct <= -99
                  ? 'the worst week lost the full max loss.'
                  : `the worst week lost ${Math.abs(b.trade.worst_week_on_margin_pct)}% of the margin.`}
              </p>
              <p className="text-[#97795a]">{b.trade.advice}</p>
            </>
          ) : (
            <p>Back-test unavailable right now.</p>
          )}
        </Tile>
      </div>
      <p className="mt-1 text-[10.5px] text-[#b39a76]">{b.disclaimer} Details are in the sections below.</p>
    </section>
  );
}
