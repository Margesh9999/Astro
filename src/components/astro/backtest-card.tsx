'use client';

import { useCallback, useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { astroApi } from '@/lib/astro/api';
import type { BacktestResult } from '@/lib/astro/types';
import { FlaskConical, Loader2, Play } from 'lucide-react';

const TOOLTIP_STYLE = {
  background: '#fffdf6',
  border: '1px solid #e8d5ae',
  borderRadius: 10,
  fontSize: 11,
  color: '#5c4327',
  boxShadow: '0 4px 16px rgba(140, 104, 50, 0.15)',
} as const;

function Metric({
  label,
  value,
  good,
}: {
  label: string;
  value: string;
  good?: boolean;
}) {
  return (
    <div className="rounded-md border border-[#f0e4cc] bg-[#fdf8ec]/80 p-2">
      <p className="text-[10px] uppercase tracking-wide text-[#b39a76]">{label}</p>
      <p className={`mt-0.5 font-mono text-sm font-medium ${good === undefined ? 'text-[#5c4327]' : good ? 'text-[#3f8a6e]' : 'text-[#c9553f]'}`}>
        {value}
      </p>
    </div>
  );
}

export function BacktestCard({ symbol, vedic }: { symbol: string; vedic: boolean }) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const res = await astroApi.backtest(symbol, 6, vedic);
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }, [symbol, vedic]);

  const s = result?.strategy;
  const b = result?.buy_hold;
  const beats = s && b ? s.total_return > b.total_return : undefined;

  return (
    <Card className="vedic-card flex h-full flex-col">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-[#c98a2e]" />
            <CardTitle className="font-display text-base tracking-wide">Walk-Forward Backtest</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="border-[#dcc08a] bg-[#f9efd8] text-[10px] text-[#8a6a3a]">
              {symbol}
            </Badge>
            <Button
              size="sm"
              variant="outline"
              className="h-8 border-[#dcc08a] bg-gradient-to-b from-[#fbe3bd] to-[#f6d194] text-[#7c4a12] hover:from-[#f9d9a4] hover:to-[#f0c47e]"
              onClick={run}
              disabled={running}
            >
              {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              {running ? 'Running…' : 'Run backtest'}
            </Button>
          </div>
        </div>
        <CardDescription className="text-[#97795a]">
          Trains on 75% of 6y history, trades the remaining 25%: long when predicted return &gt; 0, cash
          otherwise — vs buy &amp; hold
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col">
        {running && (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 py-12 text-sm text-[#97795a]">
            <Loader2 className="h-6 w-6 animate-spin text-[#d98324]" />
            Computing planetary features for every session… this can take ~10-20s
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
            <p className="text-sm text-[#97795a]">Run a walk-forward test of the astro strategy</p>
            <p className="text-xs text-[#b39a76]">
              Real ephemeris features, real yfinance prices, honest out-of-sample numbers.
            </p>
          </div>
        )}

        {!running && result && (
          <div className="flex flex-1 flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2 text-xs text-[#97795a]">
              <span>
                Test window <span className="font-mono text-[#7c5a2e]">{result.test_range}</span>
              </span>
              <Badge variant="outline" className="border-[#dcc08a] text-[10px] text-[#97795a]">
                {result.train_samples} train / {result.test_samples} test sessions
              </Badge>
              {beats !== undefined && (
                <Badge
                  variant="outline"
                  className={`text-[10px] ${
                    beats
                      ? 'border-[#a8d8bf] bg-[#e2f3e9] text-[#2f7357]'
                      : 'border-[#e8b3a8] bg-[#fbe7e0] text-[#a34332]'
                  }`}
                >
                  {beats ? 'beats' : 'trails'} buy & hold
                </Badge>
              )}
            </div>

            <div className="h-[220px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={result.equity_curve} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="#eedfc0" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: '#97795a', fontSize: 9 }}
                    tickFormatter={(d: string) => d.slice(2, 7)}
                    minTickGap={40}
                    axisLine={{ stroke: '#dcc08a' }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: '#97795a', fontSize: 9 }}
                    axisLine={false}
                    tickLine={false}
                    width={44}
                    domain={['auto', 'auto']}
                    tickFormatter={(v: number) => `${v.toFixed(0)}`}
                  />
                  <Tooltip
                    contentStyle={TOOLTIP_STYLE}
                    formatter={(v: number, name: string) => [`${v.toFixed(1)}`, name === 'strategy' ? 'Astro strategy' : 'Buy & hold']}
                    labelFormatter={(d) => String(d)}
                  />
                  <Line
                    type="monotone"
                    dataKey="strategy"
                    stroke="#d98324"
                    strokeWidth={1.8}
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="buy_hold"
                    stroke="#b39a76"
                    strokeWidth={1.4}
                    strokeDasharray="5 3"
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="text-center text-[10px] text-[#b39a76]">Equity index (start = 100)</p>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              <Metric label="Total return" value={`${s!.total_return >= 0 ? '+' : ''}${s!.total_return.toFixed(1)}%`} good={s!.total_return > 0} />
              <Metric label="Annualised" value={`${s!.annual_return >= 0 ? '+' : ''}${s!.annual_return.toFixed(1)}%`} good={s!.annual_return > 0} />
              <Metric label="Sharpe" value={s!.sharpe.toFixed(2)} good={s!.sharpe > 0} />
              <Metric label="Max DD" value={`${s!.max_drawdown.toFixed(1)}%`} />
              <Metric label="Win rate*" value={`${s!.win_rate?.toFixed(0) ?? '—'}%`} />
            </div>
            <p className="text-[10px] text-[#b39a76]">
              *Share of profitable active sessions. Buy &amp; hold over same window:{' '}
              <span className="font-mono">
                {b!.total_return >= 0 ? '+' : ''}
                {b!.total_return.toFixed(1)}%
              </span>{' '}
              total, Sharpe {b!.sharpe.toFixed(2)}, max DD {b!.max_drawdown.toFixed(1)}%. Out-of-sample
              results shown honestly — expect them to be humbling.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
