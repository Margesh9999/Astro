'use client';

import { useCallback, useEffect, useState } from 'react';
import { Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { quantApi, labApi } from '@/lib/astro/api';
import { InstrumentPicker } from './instrument-picker';
import { LabChainTab } from './lab-chain-tab';
import { LabStrategyTab } from './lab-strategy-tab';
import { LabIncomeTab } from './lab-income-tab';
import type { OptionExpirationsResponse, OptionsPriceResponse, SabrResponse } from '@/lib/astro/types';
import { FlaskConical, Loader2 } from 'lucide-react';

const MODELS = [
  { id: 'bs', label: 'BSM' },
  { id: 'black76', label: 'Black-76' },
  { id: 'crr', label: 'CRR Tree' },
  { id: 'asian', label: 'Asian' },
  { id: 'mc', label: 'Monte-Carlo' },
  { id: 'heston', label: 'Heston' },
];

function num(n: number | undefined | null, d = 4) {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return n.toFixed(d);
}

function Field({
  label,
  value,
  onChange,
  step = 'any',
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: string;
}) {
  return (
    <label className="block">
      <span className="text-[10px] uppercase tracking-wide text-[#b39a76]">{label}</span>
      <Input
        type="number"
        step={step}
        value={Number.isFinite(value) ? value : ''}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="h-7 border-[#ecdec2] bg-[#fffdf6] px-2 font-mono text-xs"
      />
    </label>
  );
}

function PricerTab({ spot, currency }: { spot: number; currency: string }) {
  const [model, setModel] = useState('bs');
  const [cp, setCp] = useState<'call' | 'put'>('call');
  const [S, setS] = useState<number>(spot || 7700);
  const [K, setK] = useState<number>((spot || 7700) * 1.01);
  const [days, setDays] = useState<number>(30);
  const [r, setR] = useState<number>(0.04);
  const [sigma, setSigma] = useState<number>(0.15);
  const [american, setAmerican] = useState(false);
  const [rho, setRho] = useState(-0.3);
  const [nu, setNu] = useState(0.8);
  const [res, setRes] = useState<OptionsPriceResponse | null>(null);
  const [iv, setIv] = useState<number | null>(null);
  const [smile, setSmile] = useState<SabrResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (spot && spot > 0) {
      setS(Math.round(spot * 100) / 100);
      setK(Math.round(spot * 1.01 * 100) / 100);
    }
  }, [spot]);

  const compute = useCallback(async () => {
    if (!Number.isFinite(S) || !Number.isFinite(K) || S <= 0 || K <= 0) return;
    setBusy(true);
    setErr(null);
    const T = Math.max(1, days) / 365;
    try {
      const body = { model, cp, S, K, T, r, sigma, american, steps: 200, n_paths: 100000, rho, nu };
      const price = await quantApi.optionPrice(body);
      setRes(price);
      if (model === 'bs' || model === 'black76') {
        try {
          const ivRes = await quantApi.impliedVol({ price: price.price, S, K, T, r, cp });
          setIv(ivRes.implied_vol);
        } catch {
          setIv(null);
        }
      } else {
        setIv(null);
      }
      const smileRes = await quantApi.sabrSmile({ forward: S, T, atm_vol: sigma, beta: 1, rho, nu });
      setSmile(smileRes);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [S, K, days, r, sigma, model, cp, american, rho, nu]);

  useEffect(() => {
    compute();
  }, [model, cp]);

  const smileData = (smile?.smile ?? []).map((p) => ({ m: p.moneyness, vol: p.vol * 100 }));

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
      <div className="space-y-2.5 lg:col-span-2">
        <div className="flex flex-wrap gap-1">
          {MODELS.map((m) => (
            <button
              key={m.id}
              onClick={() => setModel(m.id)}
              className={`rounded-full border px-2.5 py-0.5 text-[11px] transition-colors ${
                model === m.id
                  ? 'border-[#d9a441] bg-[#fdf3dc] font-semibold text-[#8a6a3a]'
                  : 'border-[#ecdec2] bg-[#fffdf6] text-[#97795a] hover:bg-[#fdf8ec]'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {(['call', 'put'] as const).map((c) => (
            <button
              key={c}
              onClick={() => setCp(c)}
              className={`flex-1 rounded-full border px-2 py-0.5 text-[11px] capitalize ${
                cp === c
                  ? c === 'call'
                    ? 'border-[#8fc4ae] bg-[#e8f4ee] font-semibold text-[#3f8a6e]'
                    : 'border-[#e8b1a4] bg-[#fbeae4] font-semibold text-[#c9553f]'
                  : 'border-[#ecdec2] bg-[#fffdf6] text-[#97795a]'
              }`}
            >
              {c}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-2">
          <Field label="Spot" value={S} onChange={setS} />
          <Field label="Strike" value={K} onChange={setK} />
          <Field label="Days" value={days} onChange={setDays} step="1" />
          <Field label="Rate r" value={r} onChange={setR} />
          <Field label="Vol σ" value={sigma} onChange={setSigma} />
          <div className="flex items-end">
            <button
              onClick={() => setAmerican(!american)}
              disabled={model !== 'crr'}
              className={`h-7 w-full rounded border text-[10px] ${
                american
                  ? 'border-[#d9a441] bg-[#fdf3dc] font-semibold text-[#8a6a3a]'
                  : 'border-[#ecdec2] bg-[#fffdf6] text-[#b39a76]'
              } disabled:opacity-40`}
            >
              American
            </button>
          </div>
        </div>
        {(model === 'heston' || model === 'bs') && (
          <div className="grid grid-cols-2 gap-2">
            <Field label="SABR ρ" value={rho} onChange={setRho} />
            <Field label="SABR ν" value={nu} onChange={setNu} />
          </div>
        )}
        <Button
          onClick={compute}
          disabled={busy}
          className="h-8 w-full border border-[#d9a441]/50 bg-gradient-to-r from-[#fdf3dc] to-[#fbead0] font-display text-xs tracking-wide text-[#8a6a3a] hover:from-[#fbead0] hover:to-[#f6dcb4]"
        >
          {busy ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : '✦'} Price it
        </Button>
      </div>

      <div className="space-y-3 lg:col-span-3">
        {err && (
          <p className="rounded border border-[#eecfc7] bg-[#fbeae4] px-2 py-1.5 text-[11px] text-[#a14d3c]">{err}</p>
        )}
        {!res && !err && (
          <div className="space-y-2 py-4">
            <Skeleton className="h-10 w-48 bg-[#efdfbc]" />
            <Skeleton className="h-16 w-full bg-[#efdfbc]" />
          </div>
        )}
        {res && (
          <>
            <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
              <span className="font-mono text-3xl font-semibold text-[#4a3525]">{num(res.price, 2)}</span>
              <span className="rounded bg-[#f7ecd4] px-2 py-0.5 text-[10px] text-[#97795a]">{res.model}</span>
              <span className="text-[11px] text-[#97795a]">{currency}</span>
              {iv !== null && (
                <span className="text-[11px] text-[#97795a]">
                  IV round-trip: <span className="font-mono font-semibold text-[#8a6a3a]">{(iv * 100).toFixed(2)}%</span>
                </span>
              )}
              {res.stderr !== undefined && (
                <span className="text-[11px] text-[#97795a]">MC stderr ±{num(res.stderr, 3)}</span>
              )}
            </div>
            <div className="grid grid-cols-5 gap-2">
              {(
                [
                  ['Delta', res.delta],
                  ['Gamma', res.gamma],
                  ['Theta /d', res.theta],
                  ['Vega', res.vega],
                  ['Rho', res.rho],
                ] as Array<[string, number | undefined]>
              ).map(([label, v]) => (
                <div key={label} className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6] px-2 py-1.5 text-center">
                  <p className="text-[9px] uppercase tracking-wide text-[#b39a76]">{label}</p>
                  <p className="font-mono text-xs font-semibold text-[#5c4327]">{num(v, 4)}</p>
                </div>
              ))}
            </div>
          </>
        )}
        {smileData.length > 0 && (
          <div>
            <p className="mb-1 text-xs text-[#97795a]">
              SABR smile (Hagan) · ATM {((smile?.atm_vol ?? 0) * 100).toFixed(1)}% · ρ {smile?.rho} · ν {smile?.nu}
            </p>
            <div className="h-36 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={smileData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <XAxis
                    dataKey="m"
                    type="number"
                    domain={['dataMin', 'dataMax']}
                    tick={{ fontSize: 9, fill: '#b39a76' }}
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                  />
                  <YAxis tick={{ fontSize: 9, fill: '#b39a76' }} tickFormatter={(v) => `${v}%`} width={34} />
                  <Tooltip
                    contentStyle={{ background: '#fffdf6', border: '1px solid #ecdec2', borderRadius: 8, fontSize: 11 }}
                    labelFormatter={(l) => `Moneyness ${(Number(l) * 100).toFixed(0)}%`}
                    formatter={(v) => [`${Number(v).toFixed(2)}%`, 'Vol']}
                  />
                  <ReferenceLine x={1} stroke="#c9b28a" strokeDasharray="3 3" />
                  <Line
                    type="monotone"
                    dataKey="vol"
                    stroke="#b0763a"
                    strokeWidth={2}
                    dot={{ r: 2.5, fill: '#c98a2e' }}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function OptionsLabCard({ symbol, spot }: { symbol: string; spot?: number }) {
  const [override, setOverride] = useState<{ symbol: string; name: string } | null>(null);
  const labSymbol = override?.symbol ?? symbol;
  // expirations cache tagged with the symbol it was fetched for — loading is
  // derived (staleness pattern), never set synchronously inside an effect
  const [expState, setExpState] = useState<{
    symbol: string;
    data: OptionExpirationsResponse | null;
    err: string | null;
  }>({ symbol: '', data: null, err: null });

  const loadingExp = expState.symbol !== labSymbol;
  const exp = expState.symbol === labSymbol ? expState.data : null;
  const expErr = expState.symbol === labSymbol ? expState.err : null;

  useEffect(() => {
    let cancelled = false;
    labApi
      .expirations(labSymbol)
      .then((r) => {
        if (!cancelled) setExpState({ symbol: labSymbol, data: r, err: null });
      })
      .catch((e) => {
        if (!cancelled) setExpState({ symbol: labSymbol, data: null, err: String(e?.message ?? e) });
      });
    return () => {
      cancelled = true;
    };
  }, [labSymbol]);

  const labSpot = exp?.spot ?? spot ?? 0;
  const labName = override?.name ?? exp?.symbol ?? labSymbol;

  return (
    <Card className="vedic-card">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-[#c98a2e]" />
            <CardTitle className="font-display text-base tracking-wide">Options Lab — Institutional</CardTitle>
            <span className="rounded bg-[#f7ecd4] px-2 py-0.5 font-mono text-[10px] text-[#97795a]">
              {labName} {labSpot ? `· ${labSpot.toFixed(2)}` : ''}
            </span>
          </div>
          <InstrumentPicker value={labSymbol} onSelect={setOverride} compact />
        </div>
        <CardDescription className="text-[#97795a]">
          Live chains (Yahoo) with SABR-skewed synthetic fallback · delta-targeted structures · POP, greeks,
          scenario matrices · vollib / optlib / pysabr / TFF lineage
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="strategy" className="w-full">
          <TabsList className="h-8 w-full justify-start gap-1 overflow-x-auto rounded-lg border border-[#ecdec2] bg-[#fffdf6] p-1">
            {(
              [
                ['strategy', '⚔ Strategy Lab'],
                ['chain', '⛓ Option Chain'],
                ['pricer', '∑ Pricer'],
                ['income', '£ Income Planner'],
              ] as Array<[string, string]>
            ).map(([v, label]) => (
              <TabsTrigger
                key={v}
                value={v}
                className="h-6 whitespace-nowrap rounded-md px-2.5 text-[11px] font-medium text-[#97795a] data-[state=active]:bg-[#fdf3dc] data-[state=active]:font-semibold data-[state=active]:text-[#8a6a3a]"
              >
                {label}
              </TabsTrigger>
            ))}
          </TabsList>

          <TabsContent value="strategy" className="mt-3">
            {expErr ? (
              <p className="rounded border border-[#eecfc7] bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">
                {labSymbol}: {expErr} — try a ⚡ options-enabled symbol from the picker (e.g. SPY, AAPL, NIFTYBEES won&apos;t
                have chains).
              </p>
            ) : loadingExp || !exp ? (
              <div className="space-y-2 py-4">
                <Skeleton className="h-8 w-full bg-[#efdfbc]" />
                <Skeleton className="h-24 w-full bg-[#efdfbc]" />
              </div>
            ) : (
              <LabStrategyTab symbol={labSymbol} exp={exp} />
            )}
          </TabsContent>

          <TabsContent value="chain" className="mt-3">
            {expErr ? (
              <p className="rounded border border-[#eecfc7] bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">{expErr}</p>
            ) : loadingExp || !exp ? (
              <Skeleton className="h-40 w-full bg-[#efdfbc]" />
            ) : (
              <LabChainTab symbol={labSymbol} exp={exp} />
            )}
          </TabsContent>

          <TabsContent value="pricer" className="mt-3">
            <PricerTab spot={labSpot} currency={exp?.currency ?? 'USD'} />
          </TabsContent>

          <TabsContent value="income" className="mt-3">
            <LabIncomeTab />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
