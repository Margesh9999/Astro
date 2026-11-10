'use client';

import { useEffect, useState } from 'react';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { FlaskConical, Info, Target } from 'lucide-react';
import { incomeLabApi } from '@/lib/astro/api-income-lab';
import type { IncomeLab, LabResult, LabStrategy } from '@/lib/astro/api-income-lab';

const UNDERLYINGS = [
  { v: '^NSEI', label: 'Nifty 50' },
  { v: '^NSEBANK', label: 'Bank Nifty' },
  { v: '^GSPC', label: 'S&P 500' },
];
const STRATS: { v: LabStrategy; label: string }[] = [
  { v: 'put_spread', label: 'Bull put spread' },
  { v: 'call_spread', label: 'Bear call spread' },
  { v: 'iron_condor', label: 'Iron condor' },
];
const RISKS = [0.02, 0.05, 0.1];
const LEG_LABEL: Record<string, string> = {
  short: 'Sell', long: 'Buy', short_put: 'Sell put', long_put: 'Buy put', short_call: 'Sell call', long_call: 'Buy call',
};

function verdictCls(v: string) {
  if (v === 'helped beyond chance') return 'border-[#bcd8ae] bg-[#e7f3df] text-[#3f6b30]';
  if (v === 'hurt beyond chance') return 'border-[#eec3b8] bg-[#fbe9e3] text-[#a14d3c]';
  if (v === 'baseline') return 'border-[#e3cfa4] bg-[#fbf2dc] text-[#7c5a2e]';
  return 'border-[#e5dccb] bg-[#f6f1e7] text-[#8c7a5e]';
}

const pct = (x: number | null | undefined, d = 1) => (x == null ? '—' : `${x > 0 ? '+' : ''}${x.toFixed(d)}%`);

export function IncomeLabCard() {
  const [symbol, setSymbol] = useState('^NSEI');
  const [strategy, setStrategy] = useState<LabStrategy>('put_spread');
  const [risk, setRisk] = useState(0.05);
  const [capital, setCapital] = useState(500000);
  const key = `${symbol}|${strategy}|${risk}`;
  const [res, setRes] = useState<{ key: string; data?: IncomeLab; err?: string } | null>(null);

  useEffect(() => {
    let live = true;
    incomeLabApi
      .run(symbol, strategy, risk)
      .then((data) => live && setRes({ key, data }))
      .catch((e) => live && setRes({ key, err: String(e?.message ?? e) }));
    return () => {
      live = false;
    };
  }, [symbol, strategy, risk, key]);

  const lab = res?.key === key ? (res.data ?? null) : null;
  const err = res?.key === key ? (res.err ?? lab?.error ?? null) : null;
  const ok = lab?.success ? lab : null;
  const base = ok?.results[0];
  const best = ok?.results.slice(1).reduce<LabResult | null>((b, r) => (!b || r.cagr_pct > b.cagr_pct ? r : b), null);
  const ccy = symbol === '^GSPC' ? '$' : '₹';
  const money = (n: number) => `${ccy}${Math.round(n).toLocaleString(ccy === '₹' ? 'en-IN' : 'en-US')}`;
  const chart =
    base && best
      ? base.equity.map((p, i) => ({ d: p.d, base: p.v, best: best.equity[i]?.v ?? null }))
      : [];

  return (
    <Card className="border-[#ecdec2] bg-[#fffdf6]/90 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="font-display flex items-center gap-2 text-base text-[#5c4327]">
          <FlaskConical className="h-4 w-4 text-[#c98a2e]" /> Income Strategy Lab
        </CardTitle>
        <CardDescription className="text-xs text-[#97795a]">
          The honest test of &ldquo;consistent income&rdquo;: sell the same defined-risk weekly option spread every week
          since 2009, then switch on each astrological filter and check whether it beats skipping the same number of
          random weeks.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2 text-xs text-[#7c5a2e]">
          <select aria-label="Underlying" value={symbol} onChange={(e) => setSymbol(e.target.value)}
            className="rounded-md border border-[#ecdec2] bg-[#fffdf6] px-2 py-1">
            {UNDERLYINGS.map((u) => <option key={u.v} value={u.v}>{u.label}</option>)}
          </select>
          <select aria-label="Strategy" value={strategy} onChange={(e) => setStrategy(e.target.value as LabStrategy)}
            className="rounded-md border border-[#ecdec2] bg-[#fffdf6] px-2 py-1">
            {STRATS.map((s) => <option key={s.v} value={s.v}>{s.label}</option>)}
          </select>
          <span className="ml-1">Risk a week</span>
          {RISKS.map((r) => (
            <button key={r} onClick={() => setRisk(r)}
              className={`rounded-full border px-2.5 py-0.5 ${risk === r ? 'border-[#c98a2e] bg-[#fbead0] font-semibold text-[#7c4a12]' : 'border-[#ecdec2] bg-[#fffdf6]'}`}>
              {r * 100}%
            </button>
          ))}
          <label className="ml-auto flex items-center gap-1.5">
            Capital {ccy}
            <input inputMode="numeric" value={capital}
              onChange={(e) => setCapital(Number(e.target.value.replace(/[^0-9]/g, '')) || 0)}
              className="w-24 rounded-md border border-[#ecdec2] bg-[#fffdf6] px-2 py-1 font-mono" />
          </label>
        </div>

        {err && <p className="rounded-md bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">Lab unavailable: {err}</p>}
        {!ok && !err && <Skeleton className="h-72 w-full bg-[#f3e6cc]" />}

        {ok && base && (
          <>
            <div className="rounded-md border border-[#eed9b4] bg-gradient-to-r from-[#fdf3dc] to-[#fbead0] px-3 py-2 text-xs leading-relaxed text-[#6b4f2e]">
              {ok.summary}
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
              {[
                ['Typical week', money((capital * ok.risk_pct * (base.avg_week_on_margin_pct ?? 0)) / 10000), 'average, all weeks'],
                ['Worst week', money((capital * ok.risk_pct * (base.worst_week_on_margin_pct ?? 0)) / 10000), 'the risk you accept'],
                ['Positive months', `${base.positive_months_pct ?? '—'}%`, `worst month ${pct(base.worst_month_pct)}`],
                ['Yearly growth', pct(base.cagr_pct), `deepest fall ${pct(base.max_drawdown_pct)}`],
              ].map(([k, v, s]) => (
                <div key={k} className="rounded-md border border-[#f0e4cc] bg-[#fffdf6] px-2.5 py-2">
                  <p className="text-[10px] uppercase tracking-wider text-[#b39a76]">{k}</p>
                  <p className="font-mono text-sm font-semibold text-[#5c4327]">{v}</p>
                  <p className="text-[10.5px] text-[#97795a]">{s}</p>
                </div>
              ))}
            </div>

            <div className="rounded-md border border-[#e3d6ee] bg-[#f8f1fb] px-3 py-2 text-xs text-[#5e3f7f]">
              <p className="mb-1 flex items-center gap-1.5 font-semibold">
                <Target className="h-3.5 w-3.5" /> This week&apos;s setup (from the {ok.this_week.as_of} close, illustrative)
              </p>
              <p>
                Spot {ok.this_week.spot.toLocaleString()} · implied vol {ok.this_week.iv_pct}% ·{' '}
                {Object.entries(ok.this_week.legs).map(([k, v]) => `${LEG_LABEL[k] ?? k} ~${Math.round(v).toLocaleString()}`).join(' · ')}{' '}
                · est. credit {ok.this_week.credit_pts} pts, max loss {ok.this_week.max_loss_pts} pts per unit.
              </p>
              <p className="mt-1 leading-relaxed">{ok.this_week.advice}</p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-xs">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-wider text-[#b39a76]">
                    <th className="py-1 pr-2 font-medium">Rule</th>
                    <th className="px-1 text-right font-medium">Weeks</th>
                    <th className="px-1 text-right font-medium">Win</th>
                    <th className="px-1 text-right font-medium">Avg / wk</th>
                    <th className="px-1 text-right font-medium">Worst wk</th>
                    <th className="px-1 text-right font-medium">Per year</th>
                    <th className="px-1 text-right font-medium">Max fall</th>
                    <th className="px-1 text-right font-medium">+ months</th>
                    <th className="pl-2 font-medium">vs random skipping</th>
                  </tr>
                </thead>
                <tbody>
                  {ok.results.map((r) => (
                    <tr key={r.key} className="border-t border-[#f0e4cc] text-[#5c4327]">
                      <td className="py-1.5 pr-2">{r.label}</td>
                      <td className="px-1 text-right font-mono">{r.weeks_traded}</td>
                      <td className="px-1 text-right font-mono">{r.win_rate_pct ?? '—'}%</td>
                      <td className="px-1 text-right font-mono">{pct(r.avg_week_on_margin_pct, 2)}</td>
                      <td className="px-1 text-right font-mono">{pct(r.worst_week_on_margin_pct, 0)}</td>
                      <td className="px-1 text-right font-mono">{pct(r.cagr_pct)}</td>
                      <td className="px-1 text-right font-mono">{pct(r.max_drawdown_pct)}</td>
                      <td className="px-1 text-right font-mono">{r.positive_months_pct ?? '—'}%</td>
                      <td className="pl-2">
                        <span className={`whitespace-nowrap rounded border px-1.5 py-px text-[9px] uppercase ${verdictCls(r.verdict)}`}>
                          {r.verdict}
                          {r.vs_random_pct != null ? ` · beat ${Math.round(r.vs_random_pct)}% of draws` : ''}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-1 text-[10.5px] text-[#97795a]">
                Avg and worst week are returns on the margin at risk. Per year, max fall and months are for the whole account
                risking {ok.risk_pct}% of capital a week.
              </p>
            </div>

            {chart.length > 1 && best && (
              <div>
                <p className="mb-1 text-[11px] text-[#97795a]">
                  Growth of 1 unit of capital: <span className="font-medium text-[#7c4a12]">every week</span> versus{' '}
                  <span className="font-medium text-[#5e3f7f]">{best.label}</span>
                </p>
                <div className="h-44 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chart} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                      <XAxis dataKey="d" tick={{ fontSize: 10, fill: '#97795a' }} tickFormatter={(d: string) => d.slice(0, 4)} minTickGap={40} />
                      <YAxis tick={{ fontSize: 10, fill: '#97795a' }} width={36} domain={['auto', 'auto']} />
                      <Tooltip contentStyle={{ fontSize: 11 }} formatter={(v: number) => v.toFixed(2)} />
                      <Line type="monotone" dataKey="base" name="every week" stroke="#c98a2e" dot={false} strokeWidth={1.6} />
                      <Line type="monotone" dataKey="best" name={best.label} stroke="#8a5fb0" dot={false} strokeWidth={1.3} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            <details className="rounded-md border border-[#f0e4cc] bg-[#fffdf6] px-3 py-2 text-xs text-[#6b4f2e]">
              <summary className="flex cursor-pointer list-none items-center gap-1.5 font-semibold text-[#7c5a2e]">
                <Info className="h-3.5 w-3.5" /> How this works
              </summary>
              <p className="mt-1 whitespace-pre-line leading-relaxed">{ok.method}</p>
              <p className="mt-1">
                Volatility source: {Object.entries(ok.vol_source).map(([k, v]) => `${k} ${v} days`).join(', ')}
                {ok.vol_index ? ` (${ok.vol_index})` : ''}. Period {ok.from} to {ok.to}.
              </p>
            </details>
            <p className="rounded-md bg-[#fbeae4] px-3 py-2 text-[11px] leading-relaxed text-[#a14d3c]">{ok.disclaimer}</p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
