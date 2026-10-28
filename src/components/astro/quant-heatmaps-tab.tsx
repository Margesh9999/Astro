'use client';

import { quantDeskApi } from '@/lib/astro/api-quant';
import {
  ChartTitle, HeatGrid, InsightBox, LoadState, SectionTitle, divergeStyle, seqStyle, useQuant,
} from './quant-ui';

const sig = (v: number | null) => (v === null ? '·' : v > 0 ? 'BUY' : v < 0 ? 'SELL' : '—');

export function QuantHeatmapsTab({ symbol }: { symbol: string }) {
  const { data, error, loading } = useQuant(symbol, quantDeskApi.heatmaps);
  const sigs = useQuant(symbol, quantDeskApi.signals);
  if (!data) return <LoadState loading={loading} error={error} what="Heatmaps" />;
  const m = data.monthly;
  const dm = data.dow_month;
  const vm = data.vol_month;
  const dy = data.dist_year;
  const cr = data.correlation;
  const volMax = Math.max(20, (vm.median ?? 15) * 2.2);
  return (
    <div className="flex flex-col gap-4">
      <SectionTitle>Monthly returns · every year since {m.years[0]}</SectionTitle>
      <HeatGrid
        rows={[...m.years].reverse()}
        cols={m.months}
        values={[...m.values].reverse()}
        style={(v) => divergeStyle(v, 10)}
        fmt={(v) => (v === null ? '·' : v.toFixed(1))}
        title={(y, c, v) => `${c} ${y}: ${v === null ? 'n/a' : `${v.toFixed(2)}%`}`}
        minWidth={560}
        maxHeight={340}
        extraCol={{ label: 'Year', values: [...m.annual].reverse(), style: (v) => divergeStyle(v, 35), fmt: (v) => (v === null ? '·' : v.toFixed(0)) }}
        footer={[
          { label: 'avg', values: m.avg, fmt: (v) => (v === null ? '·' : v.toFixed(2)), style: (v) => divergeStyle(v, 3) },
          { label: '% up', values: m.pct_positive, fmt: (v) => (v === null ? '·' : v.toFixed(0)), style: (v) => divergeStyle(v === null ? null : v - 50, 25) },
        ]}
      />
      <InsightBox insight={m.insight} />

      <SectionTitle>Seasonality · weekday × month</SectionTitle>
      <HeatGrid
        rows={dm.rows}
        cols={dm.cols}
        values={dm.values}
        style={(v) => divergeStyle(v, 0.2)}
        fmt={(v) => (v === null ? '·' : (v * 100).toFixed(0))}
        title={(r, c, v) => `${r}s in ${c}: ${v === null ? 'n/a' : `${v.toFixed(3)}% avg day`}`}
        minWidth={520}
        extraCol={{ label: 't-stat', values: dm.t_stat, style: (v) => divergeStyle(v, 3), fmt: (v) => (v === null ? '·' : v.toFixed(1)) }}
      />
      <p className="text-[10px] text-[#b39a76]">Cells = average daily return in basis points (1 bp = 0.01%). |t| &gt; 2 on the right means that weekday&apos;s effect is statistically real.</p>
      <InsightBox insight={dm.insight} />

      <SectionTitle>Signal × timeframe</SectionTitle>
      {sigs.data ? (
        <>
          <HeatGrid
            rows={sigs.data.timeframe_heatmap.rows.map((r) => r.name)}
            cols={sigs.data.timeframe_heatmap.timeframes}
            values={sigs.data.timeframe_heatmap.rows.map((r) => r.values)}
            style={(v) => divergeStyle(v === null ? null : v * 0.7, 1)}
            fmt={sig}
            title={(r, c, v) => `${r} on ${c} bars: ${sig(v)}`}
          />
          <InsightBox insight={sigs.data.timeframe_heatmap.insight} />
        </>
      ) : (
        <LoadState loading={sigs.loading} error={sigs.error} what="Signal × timeframe heatmap" />
      )}

      <SectionTitle>Rolling correlation vs world markets</SectionTitle>
      {cr ? (
        <>
          <ChartTitle>63-day correlation of daily returns with {symbol}, one column per quarter</ChartTitle>
          <HeatGrid
            rows={cr.rows.map((r) => r.name)}
            cols={cr.periods}
            values={cr.rows.map((r) => r.values)}
            style={(v) => divergeStyle(v, 0.9)}
            fmt={(v) => (v === null ? '·' : v.toFixed(2).replace('0.', '.'))}
            minWidth={620}
          />
          <ChartTitle>Full 1-year correlation matrix</ChartTitle>
          <HeatGrid
            rows={cr.matrix.symbols}
            cols={cr.matrix.symbols}
            values={cr.matrix.values}
            style={(v) => divergeStyle(v, 0.9)}
            fmt={(v) => (v === null ? '·' : v.toFixed(2).replace('0.', '.'))}
            minWidth={620}
          />
          <InsightBox insight={cr.insight} />
          {data.benchmarks_missing.length > 0 && (
            <p className="text-[10px] text-[#b39a76]">Skipped (no data right now): {data.benchmarks_missing.join(', ')}.</p>
          )}
        </>
      ) : (
        <p className="text-xs text-[#97795a]">Benchmark data is unavailable right now, so the correlation heatmap is skipped (nothing is estimated in its place).</p>
      )}

      <SectionTitle>Return distribution by year</SectionTitle>
      <HeatGrid
        rows={[...dy.years].reverse()}
        cols={dy.bins}
        values={[...dy.values].reverse()}
        style={(v) => seqStyle(v, 30)}
        fmt={(v) => (v === null ? '·' : v.toFixed(0))}
        title={(y, c, v) => `${y}: ${v === null ? 'n/a' : `${v.toFixed(1)}%`} of days in ${c}`}
        minWidth={460}
        maxHeight={300}
      />
      <p className="text-[10px] text-[#b39a76]">Cells = % of that year&apos;s trading days whose return fell in the bucket. Heavier outer columns = a wilder year.</p>
      <InsightBox insight={dy.insight} />

      <SectionTitle>Volatility · year × month</SectionTitle>
      <HeatGrid
        rows={[...vm.years].reverse()}
        cols={vm.months}
        values={[...vm.values].reverse()}
        style={(v) => seqStyle(v, volMax)}
        fmt={(v) => (v === null ? '·' : v.toFixed(0))}
        title={(y, c, v) => `${c} ${y}: ${v === null ? 'n/a' : `${v.toFixed(1)}%`} annualised vol`}
        minWidth={520}
        maxHeight={300}
      />
      <InsightBox insight={vm.insight} />
    </div>
  );
}
