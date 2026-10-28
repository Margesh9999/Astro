'use client';

import { useCallback, useState } from 'react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { modelsApi, type ModelBacktest } from '@/lib/astro/api-models';
import { FlaskConical, Lightbulb, Loader2, Play } from 'lucide-react';

const TOOLTIP_STYLE = {
  background: '#fffdf6',
  border: '1px solid #e8d5ae',
  borderRadius: 10,
  fontSize: 11,
  color: '#5c4327',
  boxShadow: '0 4px 16px rgba(140, 104, 50, 0.15)',
} as const;

const SELECT =
  'h-8 rounded-md border border-[#dcc08a] bg-[#fffdf6] px-2 text-[11px] text-[#7c4a12] focus:outline-none focus:ring-1 focus:ring-[#e8a04c]';

function Metric({ label, value, sub, good }: { label: string; value: string; sub?: string; good?: boolean }) {
  return (
    <div className="rounded-md border border-[#f0e4cc] bg-[#fdf8ec]/80 p-2">
      <p className="text-[10px] uppercase tracking-wide text-[#b39a76]">{label}</p>
      <p
        className={`mt-0.5 font-mono text-sm font-medium ${
          good === undefined ? 'text-[#5c4327]' : good ? 'text-[#3f8a6e]' : 'text-[#c9553f]'
        }`}
      >
        {value}
      </p>
      {sub && <p className="font-mono text-[9px] text-[#b39a76]">{sub}</p>}
    </div>
  );
}

const sgn = (v: number, nd = 1) => `${v >= 0 ? '+' : ''}${v.toFixed(nd)}%`;

/** Walk-forward backtest on the Model Zoo's out-of-sample predictions over the full history. */
export function BacktestCard({ symbol, vedic }: { symbol: string; vedic: boolean }) {
  // keyed so results reset when the instrument changes
  return <BacktestInner key={`${symbol}|${vedic}`} symbol={symbol} vedic={vedic} />;
}

function BacktestInner({ symbol, vedic }: { symbol: string; vedic: boolean }) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ModelBacktest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [model, setModel] = useState('ens_avg');
  const [mode, setMode] = useState('long_cash');
  const [cost, setCost] = useState(5);

  const run = useCallback(
    async (m = model, md = mode, c = cost) => {
      setRunning(true);
      setError(null);
      try {
        setResult(await modelsApi.backtest(symbol, vedic, m, c, md));
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setRunning(false);
      }
    },
    [symbol, vedic, model, mode, cost],
  );

  const s = result?.strategy;
  const b = result?.buy_hold;
  const beats = s && b ? s.annual_return > b.annual_return : undefined;
  const options = result?.options ?? [{ key: 'ens_avg', name: 'Ensemble (average of top models)' }];

  return (
    <Card className="vedic-card flex h-full flex-col">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-[#c98a2e]" />
            <CardTitle className="font-display text-base tracking-wide">Walk-Forward Backtest</CardTitle>
            <Badge variant="outline" className="border-[#dcc08a] bg-[#f9efd8] text-[10px] text-[#8a6a3a]">
              {symbol}
            </Badge>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <select
              aria-label="Model"
              className={`${SELECT} max-w-[220px]`}
              value={model}
              onChange={(e) => {
                setModel(e.target.value);
                if (result) run(e.target.value, mode, cost);
              }}
            >
              {options.map((o) => (
                <option key={o.key} value={o.key}>
                  {o.name}
                </option>
              ))}
            </select>
            <select
              aria-label="Mode"
              className={SELECT}
              value={mode}
              onChange={(e) => {
                setMode(e.target.value);
                if (result) run(model, e.target.value, cost);
              }}
            >
              <option value="long_cash">Long / cash</option>
              <option value="long_short">Long / short</option>
            </select>
            <select
              aria-label="Cost"
              className={SELECT}
              value={cost}
              onChange={(e) => {
                setCost(Number(e.target.value));
                if (result) run(model, mode, Number(e.target.value));
              }}
            >
              {[0, 5, 10, 25].map((c) => (
                <option key={c} value={c}>
                  {c} bp cost
                </option>
              ))}
            </select>
            <Button
              size="sm"
              variant="outline"
              className="h-8 border-[#dcc08a] bg-gradient-to-b from-[#fbe3bd] to-[#f6d194] text-[#7c4a12] hover:from-[#f9d9a4] hover:to-[#f0c47e]"
              onClick={() => run()}
              disabled={running}
            >
              {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              {running ? 'Running…' : 'Run backtest'}
            </Button>
          </div>
        </div>
        <CardDescription className="text-[#97795a]">
          Trades the Model Zoo&apos;s genuinely out-of-sample forecasts across the stock&apos;s full history (each
          day predicted by a model trained only on earlier data) — vs buy &amp; hold, after costs.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col">
        {running && !result && (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 py-12 text-sm text-[#97795a]">
            <Loader2 className="h-6 w-6 animate-spin text-[#d98324]" />
            Building the equity curve…
          </div>
        )}

        {!running && error && (
          <div className="rounded-md border border-[#eecfc7] bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">
            Backtest failed: {error}
          </div>
        )}

        {!running && !result && !error && (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 py-12 text-center">
            <FlaskConical className="h-8 w-8 text-[#dcc08a]" />
            <p className="text-sm text-[#97795a]">Test the zoo&apos;s best model or ensemble as a trading rule</p>
            <p className="text-xs text-[#b39a76]">Uses every model from the Model Lab once it has trained.</p>
          </div>
        )}

        {result && s && b && (
          <div className={`flex flex-1 flex-col gap-3 ${running ? 'opacity-60' : ''}`}>
            <div className="flex flex-wrap items-center gap-2 text-xs text-[#97795a]">
              <span>
                Test window <span className="font-mono text-[#7c5a2e]">{result.test_range}</span> ({result.test_years}y)
              </span>
              <Badge variant="outline" className="border-[#dcc08a] text-[10px] text-[#97795a]">
                {result.test_samples.toLocaleString()} out-of-sample sessions
              </Badge>
              <Badge
                variant="outline"
                className={`text-[10px] ${
                  beats ? 'border-[#a8d8bf] bg-[#e2f3e9] text-[#2f7357]' : 'border-[#e8b3a8] bg-[#fbe7e0] text-[#a34332]'
                }`}
              >
                {beats ? 'beats' : 'trails'} buy &amp; hold
              </Badge>
              <span className="text-[10px] text-[#b39a76]">{result.source}</span>
            </div>

            <div className="h-[240px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={result.equity_curve} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="#eedfc0" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: '#97795a', fontSize: 9 }}
                    tickFormatter={(d: string) => d.slice(0, 4)}
                    minTickGap={40}
                    axisLine={{ stroke: '#dcc08a' }}
                    tickLine={false}
                  />
                  <YAxis
                    scale="log"
                    domain={[(min: number) => min * 0.85, (max: number) => max * 1.15]}
                    tick={{ fill: '#97795a', fontSize: 9 }}
                    axisLine={false}
                    tickLine={false}
                    width={48}
                    tickFormatter={(v: number) => (v >= 10000 ? `${(v / 1000).toFixed(0)}k` : v.toFixed(0))}
                  />
                  <Tooltip
                    contentStyle={TOOLTIP_STYLE}
                    formatter={(v: number, name: string) => [v.toFixed(1), name === 'strategy' ? result.model_name : 'Buy & hold']}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: 10 }}
                    formatter={(v: string) => (v === 'strategy' ? result.model_name : 'Buy & hold')}
                  />
                  <Line type="monotone" dataKey="strategy" stroke="#d98324" strokeWidth={1.8} dot={false} isAnimationActive={false} />
                  <Line
                    type="monotone"
                    dataKey="buy_hold"
                    stroke="#45a79a"
                    strokeWidth={1.4}
                    strokeDasharray="5 3"
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="text-center text-[10px] text-[#b39a76]">Equity index, start = 100 (log scale) · rule: {result.rule}</p>

            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
              <Metric label="CAGR" value={sgn(s.annual_return)} sub={`B&H ${sgn(b.annual_return)}`} good={s.annual_return > b.annual_return} />
              <Metric label="Sharpe" value={s.sharpe.toFixed(2)} sub={`B&H ${b.sharpe.toFixed(2)}`} good={s.sharpe > b.sharpe} />
              <Metric label="Max drawdown" value={`${s.max_drawdown.toFixed(1)}%`} sub={`B&H ${b.max_drawdown.toFixed(1)}%`} good={s.max_drawdown > b.max_drawdown} />
              <Metric label="Invested" value={`${s.exposure.toFixed(0)}%`} sub={`${s.trades.toLocaleString()} switches`} />
              <Metric label="Win rate*" value={s.win_rate == null ? '—' : `${s.win_rate.toFixed(1)}%`} />
              <Metric label="Years beat B&H" value={`${result.years_beat}/${result.years_total}`} good={result.years_beat > result.years_total / 2} />
            </div>

            <div className="flex items-start gap-1.5 rounded-lg border border-[#e8ddb8] bg-[#fdf8ec] px-2.5 py-2">
              <Lightbulb className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-[#c98a2e]" />
              <p className="text-[11px] leading-relaxed text-[#7c5a2e]">{result.verdict}</p>
            </div>
            <p className="text-[10px] text-[#b39a76]">
              *Share of profitable invested sessions. {result.cost_bps} bp charged per position switch. {result.disclaimer}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
