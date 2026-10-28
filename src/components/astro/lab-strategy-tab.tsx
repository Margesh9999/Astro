'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { labApi } from '@/lib/astro/api';
import type { OptionExpirationsResponse, StrategyAnalysis, StrategyMeta } from '@/lib/astro/types';
import { Loader2 } from 'lucide-react';

const VIEW_LABEL: Record<string, string> = {
  neutral: 'Rangebound',
  bullish: 'Bullish',
  bearish: 'Bearish',
  volatile: 'Volatility',
  bearish_hedge: 'Protection',
};

function money(n: number | null | undefined, d = 2): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return '∞';
  return n.toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d });
}

function MetricTile({ label, value, tone = 'neutral', sub }: { label: string; value: string; tone?: 'good' | 'bad' | 'neutral'; sub?: string }) {
  const toneCls =
    tone === 'good' ? 'text-[#3f8a6e]' : tone === 'bad' ? 'text-[#c9553f]' : 'text-[#5c4327]';
  return (
    <div className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6] px-2 py-1.5">
      <p className="text-[9px] uppercase tracking-wide text-[#b39a76]">{label}</p>
      <p className={`font-mono text-xs font-semibold ${toneCls}`}>{value}</p>
      {sub && <p className="text-[9px] text-[#b39a76]">{sub}</p>}
    </div>
  );
}

export function LabStrategyTab({ symbol, exp }: { symbol: string; exp: OptionExpirationsResponse }) {
  const [catalog, setCatalog] = useState<StrategyMeta[]>([]);
  const [key, setKey] = useState('iron_condor');
  const [qty, setQty] = useState(1);
  const [dteTarget, setDteTarget] = useState(35);
  const [exitDte, setExitDte] = useState(21);
  const [putDelta, setPutDelta] = useState<number | ''>('');
  const [callDelta, setCallDelta] = useState<number | ''>('');
  const [res, setRes] = useState<StrategyAnalysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    labApi
      .strategies()
      .then((r) => setCatalog(r.strategies))
      .catch(() => undefined);
  }, []);

  const meta = catalog.find((s) => s.key === key);

  const analyze = useCallback(async () => {
    setBusy(true);
    setErr(null);
    try {
      const params: Record<string, number> = {};
      if (putDelta !== '') params.put_delta = Number(putDelta);
      if (callDelta !== '') params.call_delta = Number(callDelta);
      const r = await labApi.analyzeStrategy({
        symbol,
        strategy: key,
        dte_target: dteTarget,
        qty,
        exit_dte: exitDte,
        params: Object.keys(params).length ? params : undefined,
      });
      setRes(r);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [symbol, key, dteTarget, qty, exitDte, putDelta, callDelta]);

  // first analysis as soon as the catalogue is ready
  useEffect(() => {
    if (catalog.length && !res && !err) analyze();
  }, [catalog.length, key]);

  const payoff = useMemo(
    () => (res?.payoff_curve ?? []).map((p) => ({ spot: p.spot, pl: p.pl })),
    [res],
  );

  const ivCols = ['iv-5', 'iv-2', 'iv+0', 'iv+2', 'iv+5'];

  return (
    <div className="space-y-3">
      {/* controls */}
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-6">
        <label className="col-span-2">
          <span className="text-[10px] uppercase tracking-wide text-[#b39a76]">Strategy</span>
          <select
            value={key}
            onChange={(e) => {
              setRes(null);
              setErr(null);
              setKey(e.target.value);
            }}
            className="h-8 w-full rounded-md border border-[#ecdec2] bg-[#fffdf6] px-2 text-xs text-[#5c4327]"
          >
            {Object.entries(VIEW_LABEL).map(([view, label]) => (
              <optgroup key={view} label={label}>
                {catalog
                  .filter((s) => s.view === view)
                  .map((s) => (
                    <option key={s.key} value={s.key}>
                      {s.name}
                    </option>
                  ))}
              </optgroup>
            ))}
          </select>
        </label>
        {(
          [
            ['Qty (contracts)', qty, setQty, 1],
            ['DTE target', dteTarget, setDteTarget, 1],
            ['Exit @ DTE', exitDte, setExitDte, 1],
          ] as Array<[string, number, (v: number) => void, number]>
        ).map(([label, v, set, step]) => (
          <label key={label}>
            <span className="text-[10px] uppercase tracking-wide text-[#b39a76]">{label}</span>
            <Input
              type="number"
              min={1}
              step={step}
              value={v}
              onChange={(e) => set(Math.max(1, parseInt(e.target.value || '1', 10)))}
              className="h-8 border-[#ecdec2] bg-[#fffdf6] px-2 font-mono text-xs"
            />
          </label>
        ))}
        <label>
          <span className="text-[10px] uppercase tracking-wide text-[#b39a76]">Put Δ override</span>
          <Input
            type="number"
            step="0.05"
            min="0.05"
            max="0.95"
            placeholder="default"
            value={putDelta}
            onChange={(e) => setPutDelta(e.target.value === '' ? '' : parseFloat(e.target.value))}
            className="h-8 border-[#ecdec2] bg-[#fffdf6] px-2 font-mono text-xs"
          />
        </label>
        <label>
          <span className="text-[10px] uppercase tracking-wide text-[#b39a76]">Call Δ override</span>
          <Input
            type="number"
            step="0.05"
            min="0.05"
            max="0.95"
            placeholder="default"
            value={callDelta}
            onChange={(e) => setCallDelta(e.target.value === '' ? '' : parseFloat(e.target.value))}
            className="h-8 border-[#ecdec2] bg-[#fffdf6] px-2 font-mono text-xs"
          />
        </label>
      </div>

      {meta && (
        <p className="text-[11px] leading-relaxed text-[#97795a]">
          {meta.desc}{' '}
          <span className="ml-1 inline-flex gap-1">
            <Badge variant="outline" className="h-4 px-1 text-[9px] text-[#8a6a3a]">
              {VIEW_LABEL[meta.view] ?? meta.view}
            </Badge>
            <Badge variant="outline" className="h-4 px-1 text-[9px] text-[#8a6a3a]">
              {meta.risk} risk
            </Badge>
            {meta.two_expiries && (
              <Badge variant="outline" className="h-4 px-1 text-[9px] text-[#8a6a3a]">
                2 expiries
              </Badge>
            )}
          </span>
        </p>
      )}

      <div className="flex items-center gap-2">
        <Button
          onClick={analyze}
          disabled={busy}
          className="h-8 border border-[#d9a441]/50 bg-gradient-to-r from-[#fdf3dc] to-[#fbead0] px-4 font-display text-xs tracking-wide text-[#8a6a3a] hover:from-[#fbead0] hover:to-[#f6dcb4]"
        >
          {busy ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : '✦'} Build & analyse
        </Button>
        {res && (
          <span className="text-[11px] text-[#97795a]">
            {res.expiry}
            {res.expiry_far ? ` / ${res.expiry_far}` : ''} · {res.dte.toFixed(0)} DTE ·{' '}
            <span className={res.chain_source === 'live' ? 'text-[#3f8a6e]' : 'text-[#8a4a62]'}>
              {res.chain_source === 'live' ? 'live chain' : 'modelled chain'}
            </span>
          </span>
        )}
      </div>

      {err && (
        <p className="rounded border border-[#eecfc7] bg-[#fbeae4] px-2 py-1.5 text-[11px] text-[#a14d3c]">{err}</p>
      )}

      {!res && busy && <Skeleton className="h-40 w-full bg-[#efdfbc]" />}

      {res && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* left: legs + metrics */}
          <div className="space-y-3">
            <div className="overflow-hidden rounded-lg border border-[#f0e4cc]">
              <table className="w-full text-[11px]">
                <thead className="bg-[#fdf8ec] text-[9px] uppercase tracking-wide text-[#b39a76]">
                  <tr>
                    <th className="px-2 py-1 text-left font-medium">Leg</th>
                    <th className="px-2 py-1 text-right font-medium">Strike</th>
                    <th className="px-2 py-1 text-right font-medium">Entry</th>
                    <th className="px-2 py-1 text-right font-medium">IV</th>
                    <th className="px-2 py-1 text-right font-medium">Δ</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {res.legs.map((l, i) => (
                    <tr key={i} className="border-t border-[#f7ecd4]">
                      <td className="px-2 py-1">
                        <span
                          className={`mr-1.5 rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase ${
                            l.action === 'buy' ? 'bg-[#e8f4ee] text-[#3f8a6e]' : 'bg-[#fbeae4] text-[#c9553f]'
                          }`}
                        >
                          {l.action}
                        </span>
                        <span className="text-[#5c4327]">
                          {l.cp === 'stock' ? `${l.qty} sh` : `${l.cp} ×${l.qty}`}
                        </span>
                      </td>
                      <td className="px-2 py-1 text-right text-[#5c4327]">
                        {l.cp === 'stock' ? '—' : l.strike}
                      </td>
                      <td className="px-2 py-1 text-right text-[#5c4327]">{money(l.entry)}</td>
                      <td className="px-2 py-1 text-right text-[#97795a]">
                        {l.cp === 'stock' ? '—' : `${(l.iv * 100).toFixed(1)}%`}
                      </td>
                      <td className="px-2 py-1 text-right text-[#97795a]">
                        {l.cp === 'stock' ? '+1.00' : l.delta.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="grid grid-cols-4 gap-2">
              <MetricTile
                label={res.net_credit > 0 ? 'Net credit' : 'Net debit'}
                value={money(res.net_credit > 0 ? res.net_credit : res.net_debit)}
                tone={res.net_credit > 0 ? 'good' : 'neutral'}
              />
              <MetricTile
                label="Capital / margin"
                value={money(res.capital_required, 0)}
                sub={res.margin_basis.replace(/_/g, ' ')}
              />
              <MetricTile
                label="Max profit"
                value={res.max_profit === null ? 'unlimited' : money(res.max_profit, 0)}
                tone="good"
              />
              <MetricTile
                label="Max loss"
                value={res.max_loss === null ? 'unlimited' : money(res.max_loss, 0)}
                tone="bad"
              />
              <MetricTile label="POP" value={`${(res.pop * 100).toFixed(1)}%`} tone="good" />
              <MetricTile label="Expected P/L" value={money(res.expected_pl, 0)} />
              <MetricTile
                label="Breakevens"
                value={res.breakevens.length ? res.breakevens.map((b) => money(b, 1)).join(' / ') : '—'}
              />
              <MetricTile
                label="Premium / wk"
                value={res.premium_per_week > 0 ? money(res.premium_per_week, 0) : '—'}
                sub={res.theta_per_day ? `θ ${money(res.theta_per_day, 0)}/d` : undefined}
              />
            </div>

            <div className="grid grid-cols-4 gap-2">
              {(
                [
                  ['Net Δ', res.net_greeks.delta],
                  ['Net Γ', res.net_greeks.gamma],
                  ['Net Θ /d', res.net_greeks.theta],
                  ['Net Vega', res.net_greeks.vega],
                ] as Array<[string, number]>
              ).map(([label, v]) => (
                <MetricTile key={label} label={label} value={v.toFixed(2)} />
              ))}
            </div>

            {res.roc_annualised !== null && (
              <p className="text-[10px] text-[#b39a76]">
                Max annualised return-on-risk if every cycle hits max profit: {(res.roc_annualised * 100).toFixed(0)}%
                — an upper bound, not an expectation.
              </p>
            )}
          </div>

          {/* right: payoff + scenarios */}
          <div className="space-y-3">
            <div>
              <p className="mb-1 text-xs text-[#97795a]">
                Payoff at {res.expiry_far ? 'short-leg expiry (far legs marked to model)' : 'expiry'} · {res.currency}
              </p>
              <div className="h-44 w-full rounded-lg border border-[#f0e4cc] bg-[#fffdf6] p-1">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={payoff} margin={{ top: 6, right: 10, bottom: 0, left: 0 }}>
                    <defs>
                      <linearGradient id="payoffFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#8fc4ae" stopOpacity={0.45} />
                        <stop offset="50%" stopColor="#f7ecd4" stopOpacity={0.15} />
                        <stop offset="100%" stopColor="#e8b1a4" stopOpacity={0.45} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="#f0e4cc" strokeDasharray="2 4" />
                    <XAxis
                      dataKey="spot"
                      type="number"
                      domain={['dataMin', 'dataMax']}
                      tick={{ fontSize: 9, fill: '#b39a76' }}
                      tickFormatter={(v) => Number(v).toFixed(0)}
                    />
                    <YAxis tick={{ fontSize: 9, fill: '#b39a76' }} width={52} tickFormatter={(v) => v.toFixed(0)} />
                    <Tooltip
                      contentStyle={{ background: '#fffdf6', border: '1px solid #ecdec2', borderRadius: 8, fontSize: 11 }}
                      labelFormatter={(l) => `Spot ${Number(l).toFixed(2)}`}
                      formatter={(v) => [`${Number(v).toFixed(2)}`, 'P/L']}
                    />
                    <ReferenceLine y={0} stroke="#c9b28a" strokeDasharray="4 3" />
                    <ReferenceLine x={res.spot} stroke="#d98324" strokeDasharray="3 3" label={{ value: 'spot', fontSize: 9, fill: '#b0763a' }} />
                    {res.breakevens.map((b) => (
                      <ReferenceLine key={b} x={b} stroke="#8fc4ae" strokeDasharray="2 3" />
                    ))}
                    <Area type="monotone" dataKey="pl" stroke="#b0763a" strokeWidth={2} fill="url(#payoffFill)" isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div>
              <p className="mb-1 text-xs text-[#97795a]">
                Scenario matrix — P/L at {res.exit_dte} DTE for spot × IV shifts ({res.currency})
              </p>
              <div className="overflow-hidden rounded-lg border border-[#f0e4cc]">
                <table className="w-full text-[11px]">
                  <thead className="bg-[#fdf8ec] text-[9px] uppercase tracking-wide text-[#b39a76]">
                    <tr>
                      <th className="px-2 py-1 text-left font-medium">Spot \\ IV</th>
                      {ivCols.map((c) => (
                        <th key={c} className="px-2 py-1 text-right font-medium">
                          {c.replace('iv', '').replace('+', '+').replace('-', '−')} pts
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="font-mono">
                    {res.scenarios.map((row) => (
                      <tr key={row.spot_pct} className="border-t border-[#f7ecd4]">
                        <td className="px-2 py-1 font-semibold text-[#5c4327]">
                          {row.spot_pct > 0 ? '+' : ''}
                          {row.spot_pct}%
                        </td>
                        {ivCols.map((c) => {
                          const v = row[c];
                          return (
                            <td
                              key={c}
                              className={`px-2 py-1 text-right ${
                                v > 0 ? 'bg-[#e8f4ee]/60 text-[#3f8a6e]' : v < 0 ? 'bg-[#fbeae4]/60 text-[#c9553f]' : 'text-[#97795a]'
                              }`}
                            >
                              {v.toFixed(0)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}
      {res && <p className="text-[10px] text-[#b39a76]">{res.disclaimer}</p>}
    </div>
  );
}
