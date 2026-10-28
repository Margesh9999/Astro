'use client';

import {
  Area, AreaChart, Bar, ComposedChart, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { quantDeskApi, type RegimeResponse } from '@/lib/astro/api-quant';
import {
  AXIS_TICK, C, ChartTitle, InsightBox, LoadState, SectionTitle, Stat, TIP_STYLE, fmtSigned, shortDate, signColor, useQuant,
} from './quant-ui';

type R = RegimeResponse;

function zip<T extends Record<string, unknown>>(dates: string[], cols: Record<string, (number | null)[]>): T[] {
  return dates.map((d, i) => {
    const row: Record<string, unknown> = { date: d };
    for (const [k, v] of Object.entries(cols)) row[k] = v[i];
    return row as T;
  });
}

function RegimeBlock({ g }: { g: NonNullable<R['regime']> }) {
  const data = zip(g.series.dates, { p: g.series.p_stress, close: g.series.close });
  const stressed = g.current === 'Stressed';
  return (
    <div>
      <div className="mb-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Regime now" value={g.current} color={stressed ? C.red : C.green} sub={`${g.p_stress}% stress prob.`} />
        {g.states.map((s) => (
          <Stat key={s.name} label={`${s.name} days`} value={`${fmtSigned(s.ann_return_pct, 1)}/yr`}
            color={signColor(s.ann_return_pct)} sub={`vol ${s.ann_vol_pct}% · ${s.share_pct}% of time · ~${s.avg_duration_days}d spells`} />
        ))}
        <Stat label="Stay probability" value={`${g.stay_prob.calm}% / ${g.stay_prob.stressed}%`} sub="calm → calm / stress → stress" />
      </div>
      <ChartTitle>Probability of the Stressed state (shaded, left) vs price (line) · 3 years</ChartTitle>
      <div className="h-44 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <XAxis dataKey="date" tick={AXIS_TICK} tickFormatter={shortDate} minTickGap={40} />
            <YAxis yAxisId="p" domain={[0, 100]} tick={AXIS_TICK} width={28} />
            <YAxis yAxisId="c" orientation="right" hide domain={['auto', 'auto']} />
            <Tooltip contentStyle={TIP_STYLE} formatter={(v, n) => (n === 'p' ? [`${Number(v).toFixed(0)}%`, 'Stress prob.'] : [Number(v).toLocaleString(), 'Close'])} />
            <ReferenceLine yAxisId="p" y={50} stroke="#d9c9a4" strokeDasharray="3 3" />
            <Area yAxisId="p" type="stepAfter" dataKey="p" stroke="#cf5b54" strokeWidth={0.8} fill="rgba(207,91,84,0.2)" isAnimationActive={false} />
            <Line yAxisId="c" type="monotone" dataKey="close" stroke={C.copper} strokeWidth={1.3} dot={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <InsightBox insight={g.insight} />
    </div>
  );
}

function RollingBlock({ g }: { g: NonNullable<R['rolling']> }) {
  const data = zip(g.dates, { v21: g.vol21, v63: g.vol63, sh: g.sharpe252 });
  return (
    <div>
      <div className="mb-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="21d vol now" value={`${g.vol_now}%`} sub={`median ${g.vol_median}%`} />
        <Stat label="Vol percentile" value={`${g.vol_pctile}%`} sub="of all days" color={g.vol_pctile > 75 ? C.red : g.vol_pctile < 25 ? C.green : C.brown} />
        <Stat label="1y Sharpe now" value={g.sharpe_now.toFixed(2)} color={signColor(g.sharpe_now)} />
        <Stat label="Sharpe median" value={g.sharpe_median.toFixed(2)} />
      </div>
      <ChartTitle>Rolling volatility (21d copper, 63d teal, % — left) and 1-year Sharpe (lilac — right) · full history</ChartTitle>
      <div className="h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
            <XAxis dataKey="date" tick={AXIS_TICK} tickFormatter={(d: string) => d.slice(0, 4)} minTickGap={40} />
            <YAxis yAxisId="v" tick={AXIS_TICK} width={28} />
            <YAxis yAxisId="s" orientation="right" tick={AXIS_TICK} width={26} />
            <Tooltip contentStyle={TIP_STYLE} formatter={(v, n) => [Number(v).toFixed(2), n === 'v21' ? '21d vol %' : n === 'v63' ? '63d vol %' : '1y Sharpe']} />
            <ReferenceLine yAxisId="s" y={0} stroke="#d9c9a4" />
            <Line yAxisId="v" type="monotone" dataKey="v21" stroke={C.copper} strokeWidth={0.9} dot={false} isAnimationActive={false} />
            <Line yAxisId="v" type="monotone" dataKey="v63" stroke={C.teal} strokeWidth={1.1} dot={false} isAnimationActive={false} />
            <Line yAxisId="s" type="monotone" dataKey="sh" stroke={C.lilac} strokeWidth={1.1} dot={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <InsightBox insight={g.insight} />
    </div>
  );
}

function GarchBlock({ g }: { g: NonNullable<R['garch']> }) {
  const hist = zip(g.history.dates, { garch: g.history.garch, real: g.history.realised });
  const tv = [...g.term.map((t) => t.vol), g.vol_long_run];
  const termDomain: [number, number] = [Math.floor(Math.min(...tv) * 0.85), Math.ceil(Math.max(...tv) * 1.15)];
  return (
    <div>
      <div className="mb-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Next-day vol" value={`${g.vol_next_day}%`} sub="annualised" />
        <Stat label="1m / 3m forecast" value={`${g.vol_1m}% / ${g.vol_3m}%`} />
        <Stat label="Long-run vol" value={`${g.vol_long_run}%`} />
        <Stat label="α / β · half-life" value={`${g.alpha.toFixed(3)} / ${g.beta.toFixed(3)}`} sub={g.half_life_days ? `${g.half_life_days} trading days` : 'n/a'} />
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-[2fr_1fr]">
        <div className="min-w-0">
          <ChartTitle>GARCH conditional vol (copper) vs realised 21d (teal) · 2 years, %</ChartTitle>
          <div className="h-40 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={hist} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                <XAxis dataKey="date" tick={AXIS_TICK} tickFormatter={shortDate} minTickGap={40} />
                <YAxis tick={AXIS_TICK} width={28} />
                <Tooltip contentStyle={TIP_STYLE} formatter={(v, n) => [`${Number(v).toFixed(1)}%`, n === 'garch' ? 'GARCH' : 'Realised']} />
                <Line type="monotone" dataKey="real" stroke={C.teal} strokeWidth={1} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="garch" stroke={C.copper} strokeWidth={1.4} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="min-w-0">
          <ChartTitle>Forecast term structure (avg vol to day h)</ChartTitle>
          <div className="h-40 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={g.term} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                <XAxis dataKey="h" tick={AXIS_TICK} />
                <YAxis tick={AXIS_TICK} width={28} domain={termDomain} tickFormatter={(v: number) => v.toFixed(0)} />
                <Tooltip contentStyle={TIP_STYLE} labelFormatter={(l) => `${l} days`} formatter={(v) => [`${Number(v).toFixed(2)}%`, 'Vol']} />
                <ReferenceLine y={g.vol_long_run} stroke="#d9c9a4" strokeDasharray="3 3" />
                <Line type="monotone" dataKey="vol" stroke={C.rose} strokeWidth={1.6} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
      <InsightBox insight={g.insight} />
    </div>
  );
}

function HurstBlock({ g }: { g: NonNullable<R['hurst']> }) {
  const data = zip(g.series.dates, { h: g.series.hurst });
  return (
    <div>
      <ChartTitle>Rolling 2-year Hurst exponent — now {g.now.toFixed(2)} ({g.regime}); 0.5 = random walk</ChartTitle>
      <div className="h-36 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <XAxis dataKey="date" tick={AXIS_TICK} tickFormatter={(d: string) => d.slice(0, 4)} minTickGap={40} />
            <YAxis tick={AXIS_TICK} width={28} domain={[0.3, 0.75]} />
            <Tooltip contentStyle={TIP_STYLE} formatter={(v) => [Number(v).toFixed(3), 'Hurst']} />
            <ReferenceLine y={0.5} stroke="#d9c9a4" />
            <ReferenceLine y={0.55} stroke={C.green} strokeDasharray="3 3" strokeWidth={0.7} />
            <ReferenceLine y={0.45} stroke={C.red} strokeDasharray="3 3" strokeWidth={0.7} />
            <Line type="monotone" dataKey="h" stroke={C.lilac} strokeWidth={1.5} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <InsightBox insight={g.insight} />
    </div>
  );
}

function ConeBlock({ g }: { g: NonNullable<R['mc_cone']> }) {
  const data = g.cone.map((p) => ({ day: p.day, base: p.p5, outer: p.p95 - p.p5, inner_base: p.p25, inner: p.p75 - p.p25, p50: p.p50 }));
  const lo = Math.min(g.last, ...g.cone.map((p) => p.p5));
  const hi = Math.max(g.last, ...g.cone.map((p) => p.p95));
  const pad = (hi - lo) * 0.05;
  const coneDomain: [number, number] = [Math.max(0, lo - pad), hi + pad];
  return (
    <div>
      <ChartTitle>Monte-Carlo price cone — next 252 trading days (outer 5–95%, inner 25–75%, median line)</ChartTitle>
      <div className="h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <XAxis dataKey="day" tick={AXIS_TICK} />
            <YAxis tick={AXIS_TICK} width={48} domain={coneDomain} allowDataOverflow tickFormatter={(v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 0 })} />
            <Tooltip contentStyle={TIP_STYLE} labelFormatter={(l) => `Day ${l}`}
              formatter={(v, n) => (n === 'p50' ? [Number(v).toLocaleString(), 'Median'] : null)} />
            <ReferenceLine y={g.last} stroke="#d9c9a4" strokeDasharray="3 3" />
            <Area type="monotone" dataKey="base" stackId="o" stroke="none" fill="none" isAnimationActive={false} />
            <Area type="monotone" dataKey="outer" stackId="o" stroke="none" fill="rgba(176,118,58,0.14)" isAnimationActive={false} />
            <Area type="monotone" dataKey="inner_base" stackId="i" stroke="none" fill="none" isAnimationActive={false} />
            <Area type="monotone" dataKey="inner" stackId="i" stroke="none" fill="rgba(176,118,58,0.24)" isAnimationActive={false} />
            <Line type="monotone" dataKey="p50" stroke={C.copper} strokeWidth={1.6} dot={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="warm-scroll mt-2 overflow-x-auto">
        <table className="w-full min-w-[520px] text-right text-[11px]">
          <thead className="text-[9px] uppercase text-[#b39a76]">
            <tr><th className="text-left">Horizon</th><th>5%</th><th>25%</th><th>Median</th><th>75%</th><th>95%</th><th>P(up)</th><th>P(−10% dip)</th></tr>
          </thead>
          <tbody className="font-mono text-[#5c4327]">
            {g.horizons.map((h) => (
              <tr key={h.label} className="border-t border-[#f4ead2]">
                <td className="py-1 text-left font-sans">{h.label}</td>
                <td className="text-[#c9553f]">{h.p5.toLocaleString()}</td><td>{h.p25.toLocaleString()}</td>
                <td className="font-semibold">{h.p50.toLocaleString()}</td><td>{h.p75.toLocaleString()}</td>
                <td className="text-[#3f8a6e]">{h.p95.toLocaleString()}</td>
                <td>{h.prob_up}%</td><td>{h.prob_dd10}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <InsightBox insight={g.insight} />
    </div>
  );
}

function VarBlock({ g }: { g: NonNullable<R['var']> }) {
  return (
    <div>
      <ChartTitle>VaR / CVaR (% loss) · last {g.obs.toLocaleString()} days · skew {g.skew}, excess kurtosis {g.excess_kurtosis}</ChartTitle>
      <div className="warm-scroll overflow-x-auto">
        <table className="w-full min-w-[540px] text-right text-[11px]">
          <thead className="text-[9px] uppercase text-[#b39a76]">
            <tr><th className="text-left">Level · horizon</th><th>Historical VaR</th><th>Hist. CVaR</th><th>Normal VaR</th><th>Normal CVaR</th><th>Cornish-Fisher VaR</th><th>per 10,000</th></tr>
          </thead>
          <tbody className="font-mono text-[#5c4327]">
            {g.rows.map((r) => (
              <tr key={`${r.conf}-${r.horizon_days}`} className="border-t border-[#f4ead2]">
                <td className="py-1 text-left font-sans">{r.conf}% · {r.horizon_days}d</td>
                <td>{r.hist_var.toFixed(2)}</td><td className="text-[#c9553f]">{r.hist_cvar.toFixed(2)}</td>
                <td>{r.param_var.toFixed(2)}</td><td>{r.param_cvar.toFixed(2)}</td>
                <td className="font-semibold">{r.cf_var.toFixed(2)}</td><td>{r.hist_var_amt.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <InsightBox insight={g.insight} />
    </div>
  );
}

function VolConeBlock({ g }: { g: NonNullable<R['vol_cone']> }) {
  const data = g.rows.map((r) => ({ w: `${r.window}d`, min: r.min, p25: r.p25, median: r.median, p75: r.p75, max: r.max, now: r.now }));
  return (
    <div>
      <ChartTitle>Realised-volatility cone (10 years): min / 25% / median / 75% / max by look-back, today as bars</ChartTitle>
      <div className="h-44 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <XAxis dataKey="w" tick={AXIS_TICK} />
            <YAxis tick={AXIS_TICK} width={28} />
            <Tooltip contentStyle={TIP_STYLE} formatter={(v, n) => [`${Number(v).toFixed(1)}%`, String(n)]} />
            <Bar dataKey="now" fill="rgba(79,168,160,0.45)" isAnimationActive={false} barSize={18} />
            <Line dataKey="max" stroke={C.red} strokeDasharray="3 3" strokeWidth={1} dot={false} isAnimationActive={false} />
            <Line dataKey="p75" stroke={C.rose} strokeWidth={1} dot={false} isAnimationActive={false} />
            <Line dataKey="median" stroke={C.copper} strokeWidth={1.6} dot={false} isAnimationActive={false} />
            <Line dataKey="p25" stroke={C.teal} strokeWidth={1} dot={false} isAnimationActive={false} />
            <Line dataKey="min" stroke={C.green} strokeDasharray="3 3" strokeWidth={1} dot={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <InsightBox insight={g.insight} />
    </div>
  );
}

function BetaBlock({ g }: { g: NonNullable<R['beta']> }) {
  const data = zip(g.series.dates, { beta: g.series.beta, corr: g.series.corr });
  return (
    <div>
      <div className="mb-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label={`Beta vs ${g.benchmark}`} value={g.beta_now.toFixed(2)} />
        <Stat label="Correlation" value={g.corr_now.toFixed(2)} />
        <Stat label="Alpha (1y)" value={fmtSigned(g.alpha_ann_pct, 1)} color={signColor(g.alpha_ann_pct)} />
        <Stat label="Up / down capture" value={`${g.up_capture ?? '—'}% / ${g.down_capture ?? '—'}%`} />
      </div>
      <ChartTitle>Rolling 1-year beta (copper) and correlation (teal) vs {g.benchmark_name} · 5 years</ChartTitle>
      <div className="h-40 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <XAxis dataKey="date" tick={AXIS_TICK} tickFormatter={shortDate} minTickGap={40} />
            <YAxis tick={AXIS_TICK} width={28} domain={['auto', 'auto']} />
            <Tooltip contentStyle={TIP_STYLE} formatter={(v, n) => [Number(v).toFixed(2), n === 'beta' ? 'Beta' : 'Correlation']} />
            <ReferenceLine y={0} stroke="#d9c9a4" />
            <ReferenceLine y={1} stroke="#e3cfa4" strokeDasharray="3 3" />
            <Line type="monotone" dataKey="beta" stroke={C.copper} strokeWidth={1.5} dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="corr" stroke={C.teal} strokeWidth={1} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <InsightBox insight={g.insight} />
    </div>
  );
}

function DrawdownBlock({ g }: { g: NonNullable<R['drawdowns']> }) {
  return (
    <div>
      <ChartTitle>Top 5 drawdowns · now {g.current_pct}% below peak</ChartTitle>
      <div className="warm-scroll overflow-x-auto">
        <table className="w-full min-w-[520px] text-right text-[11px]">
          <thead className="text-[9px] uppercase text-[#b39a76]">
            <tr><th className="text-left">#</th><th className="text-left">Peak</th><th className="text-left">Trough</th><th className="text-left">Recovered</th><th>Depth</th><th>Days down</th><th>Days to heal</th></tr>
          </thead>
          <tbody className="font-mono text-[#5c4327]">
            {g.rows.map((r, i) => (
              <tr key={r.peak} className="border-t border-[#f4ead2]">
                <td className="py-1 text-left">{i + 1}</td>
                <td className="text-left">{r.peak}</td><td className="text-left">{r.trough}</td>
                <td className="text-left">{r.recovery ?? <span className="text-[#c9553f]">not yet</span>}</td>
                <td className="font-semibold text-[#c9553f]">{r.depth_pct}%</td>
                <td>{r.days_to_trough}</td><td>{r.days_to_recover ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <InsightBox insight={g.insight} />
    </div>
  );
}

function TestsBlock({ g }: { g: NonNullable<R['tests']> }) {
  return (
    <div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {g.tests.map((t) => (
          <div key={t.test} className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6] p-2">
            <div className="flex flex-wrap items-baseline justify-between gap-1">
              <p className="text-[11px] font-semibold text-[#5c4327]">{t.test}</p>
              <p className="font-mono text-[10px] text-[#97795a]">stat {t.stat ?? '—'} · p {t.p !== null ? t.p.toFixed(3) : '—'}</p>
            </div>
            <p className="text-[11px] font-medium text-[#8a6a3a]">{t.verdict}</p>
            <p className="text-[10px] leading-snug text-[#7c5a2e]">{t.meaning}</p>
          </div>
        ))}
      </div>
      <InsightBox insight={g.insight} />
    </div>
  );
}

export function QuantRegimeTab({ symbol }: { symbol: string }) {
  const { data, error, loading } = useQuant(symbol, quantDeskApi.regime);
  if (!data) return <LoadState loading={loading} error={error} what="Risk & regime analytics" />;
  return (
    <div className="flex flex-col gap-4">
      {data.regime && (<><SectionTitle>Volatility regime (2-state mixture)</SectionTitle><RegimeBlock g={data.regime} /></>)}
      {data.rolling && (<><SectionTitle>Rolling volatility &amp; Sharpe</SectionTitle><RollingBlock g={data.rolling} /></>)}
      {data.garch && (<><SectionTitle>GARCH(1,1) volatility forecast</SectionTitle><GarchBlock g={data.garch} /></>)}
      {data.vol_cone && (<><SectionTitle>Volatility cone</SectionTitle><VolConeBlock g={data.vol_cone} /></>)}
      {data.hurst && (<><SectionTitle>Trend memory (Hurst)</SectionTitle><HurstBlock g={data.hurst} /></>)}
      {data.mc_cone && (<><SectionTitle>Monte-Carlo price cone</SectionTitle><ConeBlock g={data.mc_cone} /></>)}
      {data.var && (<><SectionTitle>Value-at-Risk &amp; expected shortfall</SectionTitle><VarBlock g={data.var} /></>)}
      {data.beta ? (<><SectionTitle>Market sensitivity (beta)</SectionTitle><BetaBlock g={data.beta} /></>)
        : <p className="text-xs text-[#97795a]">Benchmark history unavailable — beta skipped.</p>}
      {data.drawdowns && (<><SectionTitle>Drawdown history</SectionTitle><DrawdownBlock g={data.drawdowns} /></>)}
      {data.tests && (<><SectionTitle>Statistical health checks</SectionTitle><TestsBlock g={data.tests} /></>)}
    </div>
  );
}
