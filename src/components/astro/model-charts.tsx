'use client';

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Lightbulb } from 'lucide-react';
import type { ZooResult, ZooRow } from '@/lib/astro/api-models';

export const TOOLTIP_STYLE = {
  background: '#fffdf6',
  border: '1px solid #e8d5ae',
  borderRadius: 10,
  fontSize: 11,
  color: '#5c4327',
  boxShadow: '0 4px 16px rgba(140, 104, 50, 0.15)',
} as const;

const TEAL = '#45a79a';
const ROSE = '#e8788a';
const MARIGOLD = '#e8a04c';
const LAVENDER = '#9b8ac4';
const GROUP_COLOR: Record<string, string> = { technical: MARIGOLD, astro: LAVENDER, calendar: TEAL };

export function Takeaway({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-1.5 rounded-lg border border-[#e8ddb8] bg-[#fdf8ec] px-2.5 py-2">
      <Lightbulb className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-[#c98a2e]" />
      <div className="space-y-1 text-[11px] leading-relaxed text-[#7c5a2e]">{children}</div>
    </div>
  );
}

const pct = (v: number | null | undefined, nd = 1) => (v == null ? '—' : `${(v * 100).toFixed(nd)}%`);

/* ── 1. walk-forward score bars ─────────────────────────────────────────── */
export function ScoreChart({ rows }: { rows: ZooRow[] }) {
  const ok = rows.filter((r) => r.status === 'ok' && r.r2_os != null && r.kind !== 'naive');
  const FLOOR = -3;
  const data = ok.slice(0, 24).map((r) => {
    const v = (r.r2_os ?? 0) * 100;
    return { name: r.name, value: Math.max(FLOOR, v), raw: v, clipped: v < FLOOR };
  });
  const beat = ok.filter((r) => (r.r2_os ?? 0) > 0);
  const best = ok[0];
  return (
    <div className="flex flex-col gap-2">
      <div style={{ height: Math.max(220, data.length * 17) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 0, right: 12, top: 4, bottom: 0 }}>
            <CartesianGrid stroke="#eedfc0" strokeDasharray="3 3" horizontal={false} />
            <XAxis
              type="number"
              domain={[FLOOR, 'auto']}
              tick={{ fill: '#97795a', fontSize: 9 }}
              tickFormatter={(v: number) => `${v.toFixed(1)}%`}
              axisLine={{ stroke: '#dcc08a' }}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={128}
              tick={{ fill: '#7c5a2e', fontSize: 9 }}
              axisLine={false}
              tickLine={false}
              interval={0}
            />
            <ReferenceLine x={0} stroke="#7c5a2e" strokeWidth={1} label={{ value: 'naive', fill: '#97795a', fontSize: 9, position: 'top' }} />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              formatter={(_v, _n, item) => {
                const p = item.payload as { raw: number; clipped: boolean };
                return [`${p.raw.toFixed(3)}%${p.clipped ? ' (bar clipped)' : ''}`, 'R² out-of-sample vs naive'];
              }}
            />
            <Bar dataKey="value" radius={[0, 3, 3, 0]} isAnimationActive={false}>
              {data.map((d, i) => (
                <Cell key={i} fill={d.raw > 0 ? TEAL : ROSE} fillOpacity={d.clipped ? 0.45 : 0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <Takeaway>
        <p>
          Bars show how much each model reduced forecast error versus simply assuming the average return (0 = no
          better than naive). {beat.length === 0
            ? `Every bar is left of zero: no model beat naive on unseen data — the best, ${best?.name ?? '—'}, was only "least bad".`
            : `${beat.length} model${beat.length > 1 ? 's' : ''} crossed zero; the best, ${best?.name}, improved error by ${((best?.r2_os ?? 0) * 100).toFixed(3)}%.`}
        </p>
        <p>
          What to do: {beat.length === 0
            ? 'treat any forecast below as context, not a trade signal.'
            : 'even a winning bar this small is a slight tilt at most — size positions accordingly.'}
        </p>
      </Takeaway>
    </div>
  );
}

/* ── 2. feature importance ──────────────────────────────────────────────── */
export function ImportanceChart({ imp }: { imp: ZooResult['feature_importance'] }) {
  const data = (imp.features ?? []).map((f) => ({
    name: f.feature.replace(/_/g, ' '),
    value: f.importance ?? 0,
    sd: f.importance_sd ?? 0,
    group: f.group,
    real: f.real,
    meaning: f.meaning,
  }));
  const gs = imp.group_share ?? {};
  const realOnes = data.filter((d) => d.real);
  const topAstro = data.find((d) => d.group === 'astro');
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2 text-[10px] text-[#97795a]">
        {Object.entries(GROUP_COLOR).map(([g, c]) => (
          <span key={g} className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-sm" style={{ background: c }} />
            {g} {gs[g] != null ? `· ${pct(gs[g], 0)} of signal` : ''}
          </span>
        ))}
        <span className="text-[#b39a76]">faded = within noise</span>
      </div>
      <div style={{ height: Math.max(200, data.length * 18) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 0, right: 12, top: 0, bottom: 0 }}>
            <XAxis type="number" tick={{ fill: '#97795a', fontSize: 9 }} axisLine={{ stroke: '#dcc08a' }} tickLine={false} />
            <YAxis
              type="category"
              dataKey="name"
              width={118}
              tick={{ fill: '#7c5a2e', fontSize: 9 }}
              axisLine={false}
              tickLine={false}
              interval={0}
            />
            <ReferenceLine x={0} stroke="#cfa96a" />
            <Tooltip
              contentStyle={{ ...TOOLTIP_STYLE, maxWidth: 260, whiteSpace: 'normal' }}
              formatter={(v: number, _n, item) => {
                const p = item.payload as { sd: number; meaning: string };
                return [`${v.toFixed(4)} ± ${p.sd.toFixed(4)} — ${p.meaning}`, 'error increase %'];
              }}
            />
            <Bar dataKey="value" radius={[0, 3, 3, 0]} isAnimationActive={false}>
              {data.map((d, i) => (
                <Cell key={i} fill={GROUP_COLOR[d.group] ?? MARIGOLD} fillOpacity={d.real ? 0.95 : 0.35} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ul className="grid gap-x-4 gap-y-0.5 text-[10px] leading-snug text-[#97795a] sm:grid-cols-2">
        {(imp.features ?? []).slice(0, 8).map((f) => (
          <li key={f.feature}>
            <span className="font-mono text-[#7c5a2e]">{f.feature}</span> — {f.meaning}
          </li>
        ))}
      </ul>
      <Takeaway>
        <p>
          Shuffling a feature and measuring how much worse {imp.model_name ?? 'the model'} gets on unseen data shows
          what it really uses. {realOnes.length === 0
            ? 'No feature clears the noise bar — the model has nothing dependable to lean on.'
            : `${realOnes.length} feature${realOnes.length > 1 ? 's' : ''} clear the noise bar (${realOnes
                .slice(0, 3)
                .map((d) => d.name)
                .join(', ')}).`}
        </p>
        <p>
          {topAstro
            ? `Top astro input: ${topAstro.name} (${topAstro.meaning})${topAstro.real ? ' — it does carry measurable information here.' : ' — but its effect is within noise, so do not trade on it alone.'}`
            : 'No astro input made the top 15.'}
        </p>
      </Takeaway>
    </div>
  );
}

/* ── 3. predicted vs actual ─────────────────────────────────────────────── */
export function PredVsActualChart({ pva, modelName }: { pva: ZooResult['pred_vs_actual']; modelName: string }) {
  const series = pva.series ?? [];
  const dec = pva.deciles ?? [];
  const top = dec[dec.length - 1];
  const bottom = dec[0];
  const spread = top && bottom ? (top.avg_actual ?? 0) - (bottom.avg_actual ?? 0) : 0;
  // how consistently actual returns rise with the forecast decile (Spearman-style, -1..1)
  const ranked = [...dec].sort((a, b) => (a.avg_actual ?? 0) - (b.avg_actual ?? 0)).map((d) => d.decile);
  const n = dec.length;
  const mono =
    n > 2
      ? 1 - (6 * dec.reduce((acc, d) => acc + (d.decile - (ranked.indexOf(d.decile) + 1)) ** 2, 0)) / (n * (n * n - 1))
      : 0;
  return (
    <div className="flex flex-col gap-3">
      <div>
        <p className="mb-1 text-[10px] uppercase tracking-wide text-[#b39a76]">Last 250 out-of-sample sessions (daily %)</p>
        <div className="h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={series} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#eedfc0" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: '#97795a', fontSize: 9 }} tickFormatter={(d: string) => d.slice(2, 7)} minTickGap={40} axisLine={{ stroke: '#dcc08a' }} tickLine={false} />
              <YAxis yAxisId="a" tick={{ fill: '#97795a', fontSize: 9 }} width={34} axisLine={false} tickLine={false} tickFormatter={(v: number) => `${v.toFixed(0)}%`} />
              <YAxis yAxisId="p" orientation="right" tick={{ fill: '#c98a2e', fontSize: 9 }} width={40} axisLine={false} tickLine={false} tickFormatter={(v: number) => `${v.toFixed(2)}%`} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number, n: string) => [`${v?.toFixed(3)}%`, n === 'actual' ? 'actual' : 'predicted']} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <Bar yAxisId="a" dataKey="actual" fill={TEAL} isAnimationActive={false}>
                {series.map((d, i) => (
                  <Cell key={i} fill={(d.actual ?? 0) >= 0 ? TEAL : ROSE} fillOpacity={0.55} />
                ))}
              </Bar>
              <Line yAxisId="p" dataKey="predicted" stroke="#d98324" strokeWidth={1.5} dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div>
        <p className="mb-1 text-[10px] uppercase tracking-wide text-[#b39a76]">
          Average actual next-day return by forecast decile (whole out-of-sample period)
        </p>
        <div className="h-[150px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={dec} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#eedfc0" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="decile" tick={{ fill: '#97795a', fontSize: 9 }} tickFormatter={(d: number) => (d === 1 ? 'most bearish' : d === 10 ? 'most bullish' : String(d))} axisLine={{ stroke: '#dcc08a' }} tickLine={false} interval={0} />
              <YAxis tick={{ fill: '#97795a', fontSize: 9 }} width={44} axisLine={false} tickLine={false} tickFormatter={(v: number) => `${v.toFixed(2)}%`} />
              <ReferenceLine y={0} stroke="#cfa96a" />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number, n: string) => [`${v?.toFixed(3)}%`, n === 'avg_actual' ? 'avg actual' : n]} />
              <Bar dataKey="avg_actual" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                {dec.map((d, i) => (
                  <Cell key={i} fill={(d.avg_actual ?? 0) >= 0 ? TEAL : ROSE} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <Takeaway>
        <p>
          The {modelName} forecast (orange line, right axis) moves in hundredths of a percent while real days swing by
          whole percents — that gap is why R² is near zero. Correlation with reality: {pva.corr?.toFixed(3) ?? '—'}.
        </p>
        <p>
          {spread > 0.02 && mono > 0.6
            ? `Actual returns climb fairly steadily from the most bearish to the most bullish decile (${bottom?.avg_actual?.toFixed(3)}% → ${top?.avg_actual?.toFixed(3)}% a day, consistency ${mono.toFixed(2)}) — a usable ordering; lean slightly with the extreme deciles only.`
            : `Actual returns do not rise steadily with the forecast (most bearish ${bottom?.avg_actual?.toFixed(3) ?? '—'}% vs most bullish ${top?.avg_actual?.toFixed(3) ?? '—'}% a day, consistency ${mono.toFixed(2)} on a −1…1 scale) — the forecast does not sort good days from bad ones, so don't act on it.`}
        </p>
      </Takeaway>
    </div>
  );
}

/* ── 4. direction classifiers ───────────────────────────────────────────── */
export function DirectionChart({ rows }: { rows: ZooRow[] }) {
  const ok = rows.filter((r) => r.status === 'ok');
  const horizons = [1, 5];
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {horizons.map((h) => {
        const hr = ok.filter((r) => r.horizon === h);
        if (!hr.length) return null;
        const base = (hr[0].base_rate ?? 0.5) * 100;
        const data = hr.map((r) => ({
          name: r.name.replace(' classifier', '').replace('Logistic regression', 'Logistic'),
          accuracy: (r.accuracy ?? 0) * 100,
          balanced: (r.balanced_accuracy ?? 0) * 100,
          auc: (r.auc ?? 0.5) * 100,
        }));
        const best = [...hr].sort((a, b) => (b.auc ?? 0) - (a.auc ?? 0))[0];
        const edge = ((best.accuracy ?? 0) - (best.base_rate ?? 0)) * 100;
        const vals = data.flatMap((d) => [d.accuracy, d.balanced, d.auc]).concat(base);
        const lo = Math.floor(Math.min(...vals) - 1);
        const hi = Math.ceil(Math.max(...vals) + 1);
        return (
          <div key={h} className="flex flex-col gap-2">
            <p className="text-[10px] uppercase tracking-wide text-[#b39a76]">
              {h}-day direction · base rate {base.toFixed(1)}%
            </p>
            <div className="h-[190px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="#eedfc0" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: '#7c5a2e', fontSize: 8 }} interval={0} angle={-25} textAnchor="end" height={44} axisLine={{ stroke: '#dcc08a' }} tickLine={false} />
                  <YAxis domain={[lo, hi]} tick={{ fill: '#97795a', fontSize: 9 }} width={30} axisLine={false} tickLine={false} tickFormatter={(v: number) => `${v}`} />
                  <ReferenceLine y={base} stroke="#c9553f" strokeDasharray="4 3" label={{ value: 'base', fill: '#c9553f', fontSize: 9, position: 'insideTopRight' }} />
                  <ReferenceLine y={50} stroke="#b39a76" strokeDasharray="2 3" />
                  <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number, n: string) => [`${v.toFixed(1)}${n === 'auc' ? ' (×100)' : '%'}`, n]} />
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                  <Bar dataKey="accuracy" fill={MARIGOLD} isAnimationActive={false} />
                  <Bar dataKey="balanced" fill={LAVENDER} isAnimationActive={false} />
                  <Bar dataKey="auc" fill={TEAL} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <Takeaway>
              <p>
                Best: {best.name} — right {pct(best.accuracy)} of the time vs {base.toFixed(1)}% for always guessing the
                majority; AUC {best.auc?.toFixed(3)} (0.500 = coin flip).{' '}
                {edge > 1 && (best.auc ?? 0) > 0.52
                  ? 'A small edge: use it only to tilt position size, never to go all-in.'
                  : 'No reliable edge over the base rate — direction calls here are not tradeable.'}
              </p>
            </Takeaway>
          </div>
        );
      })}
    </div>
  );
}
