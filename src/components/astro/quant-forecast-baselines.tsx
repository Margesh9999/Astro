'use client';

import { Area, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { quantDeskApi } from '@/lib/astro/api-quant';
import { AXIS_TICK, ChartTitle, InsightBox, LoadState, SectionTitle, TIP_STYLE, fmtSigned, shortDate, signColor, useQuant } from './quant-ui';

const MODEL_COLORS: Record<string, string> = {
  Naive: '#b39a76',
  Drift: '#6fa96f',
  SES: '#4fa8a0',
  'Holt (damped)': '#9b8ac4',
  'ARIMA(1,1,1)': '#d96f85',
  Theta: '#7a8fb8',
  Ensemble: '#b0763a',
};

/** OpenBB-style statistical forecasting baselines (rendered inside the Forecast tab). */
export function QuantForecastBaselines({ symbol }: { symbol: string }) {
  const { data, error, loading } = useQuant(symbol, quantDeskApi.forecast);
  if (!data) {
    return (
      <div className="flex flex-col gap-2">
        <SectionTitle>Statistical forecasting baselines</SectionTitle>
        <LoadState loading={loading} error={error} what="Forecast baselines" />
      </div>
    );
  }
  const s = data.series;
  const models = [...data.table.map((t) => t.model), 'Ensemble'];
  const rows = s.dates.map((d, i) => {
    const row: Record<string, number | string | null | [number, number]> = { date: d, close: s.close[i] as number | null };
    for (const m of models) row[m] = (s[m]?.[i] as number | null) ?? null;
    const lo = s.lo80?.[i] as number | null | undefined;
    const hi = s.hi80?.[i] as number | null | undefined;
    if (lo != null && hi != null) row.band = [lo, hi];
    return row;
  });
  return (
    <div className="flex flex-col gap-2">
      <SectionTitle>Statistical forecasting baselines (OpenBB forecast menu)</SectionTitle>
      <ChartTitle>Last 120 days + {data.horizon_days}-day projections · shaded = ARIMA 80% band · copper = error-weighted ensemble</ChartTitle>
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <XAxis dataKey="date" tick={AXIS_TICK} tickFormatter={shortDate} minTickGap={36} />
            <YAxis tick={AXIS_TICK} width={48} domain={['auto', 'auto']} tickFormatter={(v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 0 })} />
            <Tooltip contentStyle={TIP_STYLE} labelFormatter={(l) => String(l)}
              formatter={(v, n) => (Array.isArray(v) ? [`${Number(v[0]).toLocaleString()} – ${Number(v[1]).toLocaleString()}`, '80% band'] : [Number(v).toLocaleString(), String(n)])} />
            <Area dataKey="band" stroke="none" fill="rgba(217,111,133,0.14)" isAnimationActive={false} connectNulls={false} />
            <Line dataKey="close" stroke="#5c4327" strokeWidth={1.4} dot={false} isAnimationActive={false} name="Close" />
            {models.map((m) => (
              <Line key={m} dataKey={m} stroke={MODEL_COLORS[m] ?? '#999'} strokeWidth={m === 'Ensemble' ? 2 : 1}
                strokeDasharray={m === 'Ensemble' ? undefined : '4 2'} dot={false} isAnimationActive={false} />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="warm-scroll overflow-x-auto">
        <table className="w-full min-w-[560px] text-right text-[11px]">
          <thead className="text-[9px] uppercase text-[#b39a76]">
            <tr><th className="text-left">Model</th><th>Backtest error (MAPE)</th><th>Right direction</th><th>{data.horizon_days}d forecast</th><th>Change</th><th className="text-left pl-2">What it assumes</th></tr>
          </thead>
          <tbody className="text-[#5c4327]">
            {data.table.map((t, i) => (
              <tr key={t.model} className="border-t border-[#f4ead2]">
                <td className="py-1 text-left font-medium">
                  <span className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: MODEL_COLORS[t.model] }} />
                  {t.model}{i === 0 && <span className="ml-1 rounded bg-[#e2f3e9] px-1 text-[9px] text-[#2f7357]">best</span>}
                </td>
                <td className="font-mono">{t.mape.toFixed(2)}%</td>
                <td className="font-mono">{t.direction_hit !== null ? `${t.direction_hit}%` : 'n/a'}</td>
                <td className="font-mono">{t.forecast_end.toLocaleString()}</td>
                <td className="font-mono" style={{ color: signColor(t.change_pct) }}>{fmtSigned(t.change_pct, 2)}</td>
                <td className="pl-2 text-left text-[10px] text-[#7c5a2e]">{t.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <InsightBox insight={data.insight} />
    </div>
  );
}
