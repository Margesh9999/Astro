'use client';

import { useEffect, useRef, useState } from 'react';
import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Skeleton } from '@/components/ui/skeleton';
import { jatakaApi, type BirthInput, type StockKundli } from '@/lib/astro/api-jataka';
import { PLANET_META } from './planet-meta';
import { FitBar, Note, Pill, TOOLTIP_STYLE, pct } from './jataka-ui';
import { AlertTriangle, CalendarRange, Link2, Orbit, Target, TrendingUp } from 'lucide-react';

const G = ({ p }: { p: string }) => (
  <span className="mr-0.5" style={{ color: PLANET_META[p]?.color }}>{PLANET_META[p]?.glyph}</span>
);

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/80 p-3">
      <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-[#5c4327]">{icon}{title}</p>
      {children}
    </div>
  );
}

/** "Stock × Kundli" tab — data-backed fit between the selected stock and the jataka. */
export function JatakaStockTab({ symbol, symbolName, birth }: { symbol: string; symbolName?: string; birth: BirthInput }) {
  const reqKey = `${symbol}|${JSON.stringify(birth)}`;
  const [res, setRes] = useState<{ key: string; data: StockKundli | null; err: string | null } | null>(null);
  const seq = useRef(0);

  useEffect(() => {
    const s = ++seq.current;
    jatakaApi
      .stockCorrelation(symbol, birth)
      .then((r) => { if (s === seq.current) setRes({ key: reqKey, data: r, err: null }); })
      .catch((e) => { if (s === seq.current) setRes({ key: reqKey, data: null, err: String((e as Error)?.message ?? e) }); });
  }, [symbol, birth, reqKey]);

  const loading = res?.key !== reqKey;
  const data = loading ? null : res?.data ?? null;
  const err = loading ? null : res?.err ?? null;

  if (loading && !data) {
    return (
      <div className="space-y-2">
        <p className="text-[11px] text-[#97795a]">Scanning {symbolName || symbol}&apos;s full price history against your chart…</p>
        <Skeleton className="h-40 w-full bg-[#efdfbc]" />
        <Skeleton className="h-56 w-full bg-[#efdfbc]" />
      </div>
    );
  }
  if (err || !data) return <Note text={`Stock × Kundli unavailable — ${err ?? 'no data'}`} />;
  if (!data.success) return <Note text={data.error ?? 'No price history available for this symbol.'} />;

  const v = data.verdict;
  const per = data.periods;
  const tr = data.transits;
  const syn = data.synastry;
  const base = per.baseline?.ann_return ?? 0;
  const adChart = per.ad_by_lord.map((r) => ({ lord: r.lord, ret: Math.round((r.ann_return ?? 0) * 1000) / 10, n: r.periods }));
  const pdChart = per.pd_by_lord.map((r) => ({ lord: r.lord, ret: Math.round((r.ann_return ?? 0) * 1000) / 10, n: r.periods }));
  const name = data.symbol_name || symbolName || symbol;
  const toneCls = v.tone === 'favourable' ? 'green' : v.tone === 'neutral' ? 'gold' : 'rose';

  return (
    <div className="flex flex-col gap-3">
      {data.data_note.startsWith('Prices are SYNTHETIC') && (
        <div className="flex items-start gap-1.5 rounded-md border border-[#eecfc7] bg-[#fbeae4] px-2.5 py-1.5 text-[11px] text-[#a14d3c]">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" /> {data.data_note}
        </div>
      )}

      {/* ── verdict ── */}
      <div className="rounded-xl border border-[#d9b46a] bg-gradient-to-r from-[#fdf3dc] via-[#fffdf6] to-[#f2f5ec] p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="flex items-center gap-1.5 font-display text-sm font-semibold text-[#8a6a3a]">
            <Target className="h-4 w-4" /> {name} × {data.native}&apos;s kundli
          </p>
          <Pill tone={toneCls}>{v.tone} · {v.score}/100</Pill>
        </div>
        <p className="mt-1 text-xs leading-relaxed text-[#5c4327]">{v.plain}</p>
        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
          {([['Your dasha history with it', v.components.dasha_history], ['Transits active now', v.components.transits], ['Chart affinity (synastry)', v.components.synastry]] as const).map(([l, val]) => (
            <div key={l}>
              <div className="flex justify-between text-[10px] text-[#97795a]"><span>{l}</span><span className="font-mono">{val}</span></div>
              <FitBar value={val} />
            </div>
          ))}
        </div>
        <ul className="mt-2 space-y-1">
          {v.actions.map((a, i) => (
            <li key={i} className="text-[11px] leading-snug text-[#5c4327]">• {a}</li>
          ))}
        </ul>
        {v.windows.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {v.windows.map((w, i) => (
              <Pill key={i} tone={w.kind === 'favourable' ? 'green' : 'rose'}>
                <CalendarRange className="mr-0.5 inline h-3 w-3" />{w.from} → {w.to} · {w.label} ({w.edge_pct != null && w.edge_pct > 0 ? '+' : ''}{w.edge_pct}%/mo)
              </Pill>
            ))}
          </div>
        )}
        <p className="mt-2 text-[10px] text-[#b39a76]">{v.disclaimer}</p>
      </div>

      {/* ── dasha periods ── */}
      <Section icon={<TrendingUp className="h-3.5 w-3.5 text-[#c98a2e]" />} title={`${name} during your Vimshottari periods (since birth)`}>
        <Note text={per.plain || 'Not enough overlap between the price history and your dasha periods.'} />
        <div className="mt-2 grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div>
            <p className="mb-1 text-[10px] uppercase tracking-wide text-[#b39a76]">Annualised return by antardasha lord</p>
            <div className="h-44 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={adChart} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
                  <XAxis dataKey="lord" tick={{ fontSize: 9, fill: '#97795a' }} interval={0} />
                  <YAxis tick={{ fontSize: 9, fill: '#97795a' }} unit="%" />
                  <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(val, _n, item) => [`${val}%/yr · ${(item?.payload as { n?: number })?.n ?? 0} period(s)`, 'return']} />
                  <ReferenceLine y={Math.round(base * 1000) / 10} stroke="#8b7bb8" strokeDasharray="4 3" />
                  <Bar dataKey="ret" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                    {adChart.map((d, i) => <Cell key={i} fill={d.ret >= base * 100 ? '#4a9a7e' : '#c9553f'} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="text-[10px] text-[#b39a76]">Dashed line = the stock&apos;s overall {pct(base)}/yr since your birth.</p>
          </div>
          <div>
            <p className="mb-1 text-[10px] uppercase tracking-wide text-[#b39a76]">By pratyantardasha lord (weeks-long PDs)</p>
            <div className="h-44 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={pdChart} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
                  <XAxis dataKey="lord" tick={{ fontSize: 9, fill: '#97795a' }} interval={0} />
                  <YAxis tick={{ fontSize: 9, fill: '#97795a' }} unit="%" />
                  <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(val, _n, item) => [`${val}%/yr · ${(item?.payload as { n?: number })?.n ?? 0} PDs`, 'return']} />
                  <ReferenceLine y={Math.round(base * 1000) / 10} stroke="#8b7bb8" strokeDasharray="4 3" />
                  <Bar dataKey="ret" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                    {pdChart.map((d, i) => <Cell key={i} fill={d.ret >= base * 100 ? '#86a69d' : '#e8a090'} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
        <div className="warm-scroll mt-2 max-h-64 overflow-auto">
          <table className="w-full min-w-[460px] text-left text-[10px]">
            <thead className="sticky top-0 bg-[#fffdf6]">
              <tr className="text-[#b39a76]"><th className="py-1 pr-2">Period (MD/AD)</th><th className="pr-2">Dates</th><th className="pr-2 text-right">Ann. return</th><th className="pr-2 text-right">Up-weeks</th><th className="text-right">Vol</th></tr>
            </thead>
            <tbody>
              {per.antardashas.slice().reverse().map((r) => (
                <tr key={r.label + r.start} className={`border-t border-[#f4ead2] ${r.running ? 'bg-[#fbe7e0]/60 font-medium' : ''}`}>
                  <td className="py-1 pr-2 text-[#5c4327]"><G p={r.md} /><G p={r.lord} />{r.label}{r.running ? ' (now)' : ''}</td>
                  <td className="pr-2 font-mono text-[#97795a]">{r.from.slice(0, 7)} → {r.to.slice(0, 7)}</td>
                  <td className={`pr-2 text-right font-mono ${(r.ann_return ?? 0) >= base ? 'text-[#2f7357]' : 'text-[#a34332]'}`}>{pct(r.ann_return)}</td>
                  <td className="pr-2 text-right font-mono text-[#7c5a2e]">{r.hit_rate != null ? `${Math.round(r.hit_rate * 100)}%` : '—'}</td>
                  <td className="text-right font-mono text-[#7c5a2e]">{pct(r.vol, 0, false)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-1 text-[10px] text-[#b39a76]">{per.note}</p>
      </Section>

      {/* ── transits ── */}
      <Section icon={<Orbit className="h-3.5 w-3.5 text-[#c98a2e]" />} title={`Transits to your chart × ${name}'s full history (${data.history.start} → ${data.history.end})`}>
        <Note text={tr.plain} />
        {(tr.active_now.length > 0 || tr.upcoming.length > 0) && (
          <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
            <div className="rounded-lg border border-[#e8ddb8] bg-[#fdf8ec] p-2">
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-[#a8701a]">Active now</p>
              {tr.active_now.length === 0 ? <p className="text-[11px] text-[#97795a]">None of the studied contacts.</p> :
                tr.active_now.map((r) => (
                  <p key={r.label} className="text-[11px] leading-snug text-[#5c4327]">
                    <G p={r.transit} />{r.label}{' '}
                    <span className={`font-mono ${(r.edge_pct ?? 0) >= 0 ? 'text-[#2f7357]' : 'text-[#a34332]'}`}>{(r.edge_pct ?? 0) > 0 ? '+' : ''}{r.edge_pct}%/mo</span>
                    {r.window_90d && <span className="text-[10px] text-[#97795a]"> · until {r.window_90d.until_after_window ? 'beyond 90 days' : r.window_90d.to}</span>}
                  </p>
                ))}
            </div>
            <div className="rounded-lg border border-[#e8ddb8] bg-[#fdf8ec] p-2">
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-[#a8701a]">Starting in the next 90 days</p>
              {tr.upcoming.length === 0 ? <p className="text-[11px] text-[#97795a]">No new contacts begin.</p> :
                tr.upcoming.map((r) => (
                  <p key={r.label} className="text-[11px] leading-snug text-[#5c4327]">
                    <G p={r.transit} />{r.label} from <span className="font-mono">{r.window_90d?.from}</span>{' '}
                    <span className={`font-mono ${(r.edge_pct ?? 0) >= 0 ? 'text-[#2f7357]' : 'text-[#a34332]'}`}>{(r.edge_pct ?? 0) > 0 ? '+' : ''}{r.edge_pct}%/mo</span>
                  </p>
                ))}
            </div>
          </div>
        )}
        <div className="warm-scroll mt-2 max-h-72 overflow-auto">
          <table className="w-full min-w-[520px] text-left text-[10px]">
            <thead className="sticky top-0 bg-[#fffdf6]">
              <tr className="text-[#b39a76]"><th className="py-1 pr-2">Transit contact</th><th className="pr-2 text-right">Days</th><th className="pr-2 text-right">1-mo fwd</th><th className="pr-2 text-right">Edge vs all days</th><th className="pr-2 text-right">Up %</th><th>Read</th></tr>
            </thead>
            <tbody>
              {tr.rows.map((r) => (
                <tr key={r.label} className={`border-t border-[#f4ead2] ${r.active_now ? 'bg-[#fdf3dc]' : ''}`}>
                  <td className="py-1 pr-2 text-[#5c4327]"><G p={r.transit} />{r.label}{r.active_now && <span className="ml-1 rounded bg-[#e8a04c] px-1 text-[9px] text-white">now</span>}</td>
                  <td className="pr-2 text-right font-mono text-[#97795a]">{r.days.toLocaleString()}</td>
                  <td className="pr-2 text-right font-mono text-[#7c5a2e]">{r.fwd_mean_pct}%</td>
                  <td className={`pr-2 text-right font-mono ${(r.edge_pct ?? 0) >= 0 ? 'text-[#2f7357]' : 'text-[#a34332]'}`}>{(r.edge_pct ?? 0) > 0 ? '+' : ''}{r.edge_pct} pts</td>
                  <td className="pr-2 text-right font-mono text-[#7c5a2e]">{r.hit_rate != null ? Math.round(r.hit_rate * 100) : '—'}%</td>
                  <td><Pill tone={r.verdict === 'better' ? 'green' : r.verdict === 'worse' ? 'rose' : 'gold'}>{r.verdict}</Pill></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-1 text-[10px] leading-snug text-[#b39a76]">
          Baseline: {tr.baseline.fwd_mean_pct}% average 1-month forward return over {tr.baseline.days.toLocaleString()} days. {tr.method}
        </p>
      </Section>

      {/* ── synastry ── */}
      <Section icon={<Link2 className="h-3.5 w-3.5 text-[#c98a2e]" />} title={`Synastry — ${name}'s "birth chart" × yours`}>
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone={syn.score >= 62 ? 'green' : syn.score >= 42 ? 'gold' : 'rose'}>affinity {syn.score}/100</Pill>
          <Pill tone="lav">{syn.stock_birth.date} · {syn.stock_birth.note}</Pill>
        </div>
        <div className="mt-1.5"><FitBar value={syn.score} /></div>
        <p className="mt-2 text-[11px] leading-relaxed text-[#7c5a2e]">{syn.plain}</p>
        <div className="mt-2 flex flex-wrap gap-1">
          {Object.entries(syn.stock_birth.positions).map(([p, x]) => (
            <span key={p} className="rounded border border-[#f0e4cc] bg-[#fdf8ec] px-1.5 py-0.5 text-[10px] text-[#5c4327]">
              <G p={p} />{p} {x.sign} {x.degree != null ? Math.floor(x.degree) : ''}°
            </span>
          ))}
        </div>
        <div className="mt-2 grid grid-cols-1 gap-1.5 md:grid-cols-2">
          {syn.contacts.slice(0, 8).map((c, i) => (
            <div key={i} className={`rounded border px-2 py-1 text-[10px] leading-snug ${c.tone === 'supportive' ? 'border-[#a8d8bf] bg-[#e2f3e9]/60' : c.tone === 'challenging' ? 'border-[#e8b3a8] bg-[#fbe7e0]/60' : 'border-[#f0e4cc] bg-[#fdf8ec]'}`}>
              <span className="font-semibold text-[#5c4327]"><G p={c.stock} />{c.stock} {c.aspect} <G p={c.native} />{c.native}</span>
              <span className="ml-1 font-mono text-[#97795a]">orb {c.orb}°</span>
              <p className="text-[#7c5a2e]">{c.meaning}</p>
            </div>
          ))}
        </div>
        <ul className="mt-2 space-y-0.5">
          {syn.house_overlay.map((h) => <li key={h.stock} className="text-[10px] text-[#7c5a2e]">• {h.meaning}</li>)}
        </ul>
        <p className="mt-1 text-[10px] text-[#b39a76]">{syn.note}</p>
      </Section>
    </div>
  );
}
