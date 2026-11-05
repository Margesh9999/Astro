'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowDownRight, ArrowRight, ArrowUpRight, Compass, Info, Landmark, Sparkles } from 'lucide-react';
import { loadBirth } from '@/lib/astro/api-jataka';
import { outlookApi } from '@/lib/astro/api-outlook';
import type { Horizon, MarketOutlook, OutlookDirection, SectorCall } from '@/lib/astro/api-outlook';

const H_LABEL: Record<Horizon, string> = { week: 'This week', month: 'Next month', year: 'Next year' };

const DIR: Record<OutlookDirection, { label: string; cls: string; bar: string; Icon: typeof ArrowUpRight }> = {
  up: { label: 'Upward', cls: 'border-[#cfe0c2] bg-[#eef5e8] text-[#4f7a3f]', bar: 'bg-[#6f9e5b]', Icon: ArrowUpRight },
  down: { label: 'Downward', cls: 'border-[#eec3b8] bg-[#fbe9e3] text-[#a14d3c]', bar: 'bg-[#c9553f]', Icon: ArrowDownRight },
  range: { label: 'Range-bound', cls: 'border-[#ecd9a8] bg-[#fbf2dc] text-[#8a6a2a]', bar: 'bg-[#d9a23a]', Icon: ArrowRight },
};

function EdgeBadge({ verdict }: { verdict: string }) {
  const cls =
    verdict === 'significant edge'
      ? 'border-[#bcd8ae] bg-[#e7f3df] text-[#3f6b30]'
      : verdict === 'weak hint'
        ? 'border-[#e6d39c] bg-[#faf1d6] text-[#7c6020]'
        : 'border-[#e5dccb] bg-[#f6f1e7] text-[#8c7a5e]';
  return <span className={`whitespace-nowrap rounded border px-1.5 py-px text-[9px] uppercase ${cls}`}>history: {verdict}</span>;
}

function SectorRow({ s }: { s: SectorCall }) {
  const d = DIR[s.direction];
  const bt = s.backtest;
  return (
    <details className="group rounded-md border border-[#f0e4cc] bg-[#fffdf6] px-3 py-2 open:bg-[#fdf8ec]">
      <summary className="flex cursor-pointer list-none flex-wrap items-center gap-2 text-xs">
        <span className="min-w-[10rem] flex-1 font-medium text-[#5c4327]">{s.sector}</span>
        <span className={`flex items-center gap-1 rounded-full border px-2 py-0.5 ${d.cls}`}>
          <d.Icon className="h-3 w-3" /> {d.label}
        </span>
        <span className="hidden h-1.5 w-24 overflow-hidden rounded-full bg-[#f0e4cc] sm:block" title={`strength ${s.strength_pct}/100`}>
          <span className={`block h-full ${d.bar}`} style={{ width: `${s.strength_pct}%` }} />
        </span>
        <EdgeBadge verdict={bt.verdict} />
      </summary>
      <div className="mt-2 space-y-2 text-xs leading-relaxed text-[#6b4f2e]">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-[#b39a76]">Why (ruling planets)</p>
          <ul className="mt-0.5 space-y-0.5">
            {s.drivers.map((x) => (
              <li key={x.planet}>
                <span className={x.effect === '+' ? 'text-[#4f7a3f]' : x.effect === '−' ? 'text-[#a14d3c]' : 'text-[#97795a]'}>
                  {x.effect === '+' ? '▲' : x.effect === '−' ? '▼' : '•'}
                </span>{' '}
                <span className="font-medium">{x.planet}</span> {x.state}
              </li>
            ))}
          </ul>
          {s.changes.length > 0 && <p className="mt-1 text-[#97795a]">Shifts ahead: {s.changes.join(' · ')}</p>}
        </div>
        <div className="rounded border border-[#eed9b4] bg-[#fdf3dc] px-2 py-1.5">
          <p className="text-[10px] uppercase tracking-wider text-[#b38a4a]">Options idea</p>
          <p>
            <span className="font-medium">Income:</span> {s.options.income}
          </p>
          <p>
            <span className="font-medium">Directional:</span> {s.options.directional}
          </p>
          <p className="mt-0.5 italic text-[#8a6a3a]">{s.options.trust}</p>
        </div>
        <p className="text-[11px] text-[#97795a]">
          {bt.hit_pct != null ? (
            <>
              Back-test on {s.proxy} since {bt.since}: the rule made {bt.n} calls and was right {bt.hit_pct}% of the time versus{' '}
              {bt.expected_pct}% expected by chance (z {bt.z}).
              {bt.avg_ret_up_calls_pct != null && ` Average move after "up" calls ${bt.avg_ret_up_calls_pct}%`}
              {bt.avg_ret_down_calls_pct != null && `, after "down" calls ${bt.avg_ret_down_calls_pct}%`}.
            </>
          ) : (
            <>Back-test on {s.proxy}: {bt.verdict}.</>
          )}{' '}
          F&amp;O names: {s.fno.join(', ')}
          {s.etf ? ` · ETF: ${s.etf}` : ''}.
        </p>
      </div>
    </details>
  );
}

export function MarketOutlookCard() {
  const [h, setH] = useState<Horizon>('month');
  const [capital, setCapital] = useState(500000);
  const [draft, setDraft] = useState('500000');
  const [res, setRes] = useState<{ key: number; data?: MarketOutlook; err?: string } | null>(null);

  useEffect(() => {
    let live = true;
    outlookApi
      .get(loadBirth(), capital)
      .then((data) => live && setRes({ key: capital, data }))
      .catch((e) => live && setRes({ key: capital, err: String(e?.message ?? e) }));
    return () => {
      live = false;
    };
  }, [capital]);

  const o = res?.key === capital ? (res.data ?? null) : null;
  const err = res?.key === capital ? (res.err ?? null) : null;
  const view = o?.horizons[h];
  const plan = o?.income_plan;
  const inr = (n: number) => `₹${n.toLocaleString('en-IN')}`;

  return (
    <Card className="border-[#ecdec2] bg-[#fffdf6]/90 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="font-display flex items-center gap-2 text-base text-[#5c4327]">
          <Compass className="h-4 w-4 text-[#c98a2e]" /> Market Outlook &amp; Income Plan
        </CardTitle>
        <CardDescription className="text-xs text-[#97795a]">
          Which sectors the planets favour for the week, month and year ahead, how to express that with defined-risk
          options, and which kinds of funds suit steady weekly, monthly and yearly income for your chart. Every call is
          checked against the sector&apos;s real price history.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          {(Object.keys(H_LABEL) as Horizon[]).map((k) => (
            <button
              key={k}
              onClick={() => setH(k)}
              className={`rounded-full border px-3 py-1 text-xs ${
                h === k ? 'border-[#c98a2e] bg-[#fbead0] font-semibold text-[#7c4a12]' : 'border-[#ecdec2] bg-[#fffdf6] text-[#7c5a2e]'
              }`}
            >
              {H_LABEL[k]}
            </button>
          ))}
          <form
            className="ml-auto flex items-center gap-1.5 text-xs text-[#7c5a2e]"
            onSubmit={(e) => {
              e.preventDefault();
              const n = Number(draft.replace(/[^0-9.]/g, ''));
              if (n > 0) setCapital(Math.round(n));
            }}
          >
            <label htmlFor="outlook-capital">Capital ₹</label>
            <input
              id="outlook-capital"
              inputMode="numeric"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              className="w-24 rounded-md border border-[#ecdec2] bg-[#fffdf6] px-2 py-1 font-mono"
            />
            <button className="rounded-md border border-[#d9b46a] bg-[#fbead0] px-2 py-1 text-[#7c4a12]">Plan</button>
          </form>
        </div>

        {err && <p className="rounded-md bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">Outlook unavailable: {err}</p>}
        {!o && !err && <Skeleton className="h-64 w-full bg-[#f3e6cc]" />}

        {o && view && plan && (
          <>
            <div className="rounded-md border border-[#eed9b4] bg-gradient-to-r from-[#fdf3dc] to-[#fbead0] px-3 py-2">
              <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-[#7c4a12]">
                <Sparkles className="h-3.5 w-3.5" /> {H_LABEL[h]} in plain English
              </p>
              <p className="text-xs leading-relaxed text-[#6b4f2e]">{view.summary}</p>
            </div>

            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-[#97795a]">
                Sector forecast · strongest first · tap a sector for the why and an options idea
              </p>
              <div className="space-y-1.5">
                {view.sectors.map((s) => (
                  <SectorRow key={s.sector} s={s} />
                ))}
              </div>
            </div>

            <div>
              <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-[#97795a]">
                <Landmark className="h-3.5 w-3.5" /> Income plan for {inr(capital)}
                <span className="font-normal normal-case tracking-normal">
                  · split by {plan.split_source}
                  {o.jataka.used && o.jataka.name ? ` (${o.jataka.name})` : ''}
                </span>
              </p>
              <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                {plan.buckets.map((b) => (
                  <div
                    key={b.horizon}
                    className={`rounded-md border px-3 py-2 text-xs ${
                      b.horizon === h ? 'border-[#d9b46a] bg-[#fdf3dc]' : 'border-[#f0e4cc] bg-[#fffdf6]'
                    }`}
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="font-semibold text-[#5c4327]">{b.label}</p>
                      <p className="font-mono text-[#7c4a12]">
                        {b.allocation_pct}% · {inr(b.amount)}
                      </p>
                    </div>
                    {b.chart_fit != null && <p className="text-[10.5px] text-[#97795a]">chart fit {b.chart_fit}/100</p>}
                    {b.market_bias && (
                      <p className="text-[10.5px] text-[#97795a]">
                        market lean: <span className="font-medium">{DIR[b.market_bias].label.toLowerCase()}</span>
                      </p>
                    )}
                    <p className="mt-1 leading-relaxed text-[#6b4f2e]">{b.how}</p>
                    <ul className="mt-1 space-y-0.5">
                      {b.ideas.map((i) => (
                        <li key={i.name} className="leading-snug">
                          <span className="font-medium text-[#5c4327]">{i.name}</span>
                          <span className="text-[#97795a]"> · {i.yield}</span>
                        </li>
                      ))}
                    </ul>
                    <p className="mt-1 text-[10.5px] text-[#a35a22]">{b.risk}</p>
                  </div>
                ))}
              </div>
              {plan.personal_picks.length > 0 && (
                <p className="mt-2 text-xs text-[#5e3f7f]">
                  Where your chart and the transits agree:{' '}
                  {plan.personal_picks.map((p) => `${p.sector} (${H_LABEL[p.horizon].toLowerCase()})`).join(', ')}.
                </p>
              )}
              <p className="mt-1 text-[11px] text-[#97795a]">
                Yields are typical historical ranges for the category, not promises. Choose large, low-cost direct plans,
                and check each fund&apos;s factsheet. Birth details come from the Janma Kundli section below.
              </p>
            </div>

            <details className="rounded-md border border-[#f0e4cc] bg-[#fffdf6] px-3 py-2 text-xs text-[#6b4f2e]">
              <summary className="flex cursor-pointer list-none items-center gap-1.5 font-semibold text-[#7c5a2e]">
                <Info className="h-3.5 w-3.5" /> How this works
              </summary>
              <p className="mt-1 whitespace-pre-line leading-relaxed">{o.method}</p>
            </details>
            <p className="rounded-md bg-[#fbeae4] px-3 py-2 text-[11px] leading-relaxed text-[#a14d3c]">{o.disclaimer}</p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
