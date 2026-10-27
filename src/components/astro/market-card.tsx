'use client';

import { Area, AreaChart, ResponsiveContainer, YAxis } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import type { MarketQuote } from '@/lib/astro/types';
import { ArrowDownRight, ArrowUpRight, Activity, TrendingUp } from 'lucide-react';

function fmt(n: number | undefined, digits = 2) {
  if (n === undefined || Number.isNaN(n)) return '—';
  return n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function fmtVol(v: number | undefined) {
  if (v === undefined) return '—';
  if (v >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return String(v);
}

export function MarketCard({ quote, loading }: { quote: MarketQuote | null; loading: boolean }) {
  const up = (quote?.change ?? 0) >= 0;
  const color = up ? 'text-[#3f8a6e]' : 'text-[#c9553f]';
  const stroke = up ? '#4a9a7e' : '#cf5b54';
  const sparkUp =
    quote && quote.sparkline.length > 1
      ? quote.sparkline[quote.sparkline.length - 1].close >= quote.sparkline[0].close
      : true;

  return (
    <Card className="vedic-card flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-[#c98a2e]" />
            <CardTitle className="font-display text-base tracking-wide">Market Pulse</CardTitle>
          </div>
          {quote && (
            <span className="rounded bg-[#f7ecd4] px-2 py-0.5 font-mono text-[10px] text-[#97795a]">
              {quote.symbol}
            </span>
          )}
        </div>
        <CardDescription className="text-[#97795a]">Live quote via yfinance (delayed)</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col">
        {loading && !quote ? (
          <div className="space-y-3">
            <Skeleton className="h-9 w-40 bg-[#efdfbc]" />
            <Skeleton className="h-4 w-24 bg-[#efdfbc]" />
            <Skeleton className="mt-2 h-20 w-full bg-[#efdfbc]" />
          </div>
        ) : !quote ? (
          <div className="flex flex-1 items-center justify-center py-10 text-sm text-[#97795a]">
            Market data unavailable — Yahoo Finance may be rate-limiting. Try refreshing.
          </div>
        ) : (
          <>
            <div className="flex items-baseline gap-3">
              <span className="font-mono text-3xl font-semibold tracking-tight text-[#4a3525]">
                {fmt(quote.price)}
              </span>
              <span className={`flex items-center gap-1 text-sm font-medium ${color}`}>
                {up ? <ArrowUpRight className="h-4 w-4" /> : <ArrowDownRight className="h-4 w-4" />}
                {up ? '+' : ''}
                {fmt(quote.change)} ({up ? '+' : ''}
                {fmt(quote.change_percent)}%)
              </span>
            </div>
            <p className="mt-1 text-xs text-[#97795a]">
              {quote.name} · {quote.currency}
            </p>

            <div className="mt-3 h-24 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={quote.sparkline} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={stroke} stopOpacity={0.30} />
                      <stop offset="100%" stopColor={stroke} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <YAxis hide domain={['dataMin * 0.999', 'dataMax * 1.001']} />
                  <Area
                    type="monotone"
                    dataKey="close"
                    stroke={stroke}
                    strokeWidth={1.6}
                    fill="url(#sparkFill)"
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-[#97795a]">Open</span>
                <span className="font-mono text-[#5c4327]">{fmt(quote.open)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#97795a]">Prev close</span>
                <span className="font-mono text-[#5c4327]">{fmt(quote.previous_close)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#97795a]">Day high</span>
                <span className="font-mono text-[#3f8a6e]">{fmt(quote.day_high)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#97795a]">Day low</span>
                <span className="font-mono text-[#c9553f]">{fmt(quote.day_low)}</span>
              </div>
              <div className="col-span-2 flex justify-between border-t border-[#f0e4cc] pt-1.5">
                <span className="flex items-center gap-1 text-[#97795a]">
                  <TrendingUp className="h-3 w-3" /> Volume
                </span>
                <span className="font-mono text-[#5c4327]">{fmtVol(quote.volume)}</span>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
