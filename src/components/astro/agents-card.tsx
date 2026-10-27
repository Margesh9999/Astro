'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { enhanceApi } from '@/lib/astro/api';
import type { AgentsAnalysis } from '@/lib/astro/types';
import { Bot, Gavel } from 'lucide-react';

const STANCE_STYLE: Record<string, string> = {
  bullish: 'border-[#a8d8bf] bg-[#e2f3e9] text-[#2f7357]',
  'bullish-cautious': 'border-[#a8d8bf] bg-[#e2f3e9] text-[#2f7357]',
  'contrarian-bullish': 'border-[#a8d8bf] bg-[#e2f3e9] text-[#2f7357]',
  constructive: 'border-[#a8d8bf] bg-[#e2f3e9] text-[#2f7357]',
  bearish: 'border-[#e8b3a8] bg-[#fbe7e0] text-[#a34332]',
  neutral: 'border-[#dcc08a] bg-[#f9efd8] text-[#8a6a3a]',
  guarded: 'border-[#eecfc7] bg-[#fdeaea] text-[#a14d3c]',
  selective: 'border-[#dcc08a] bg-[#f9efd8] text-[#8a6a3a]',
};

const VERDICT_STYLE: Record<string, string> = {
  ACCUMULATE: 'border-[#a8d8bf] bg-[#e2f3e9] text-[#2f7357]',
  'HOLD & HARVEST': 'border-[#dcc08a] bg-[#f9efd8] text-[#8a6a3a]',
  DEFEND: 'border-[#e8b3a8] bg-[#fbe7e0] text-[#a34332]',
};

export function AgentsCard({ symbol }: { symbol: string }) {
  const [state, setState] = useState<{ data?: AgentsAnalysis; error?: string } | null>(null);

  useEffect(() => {
    let alive = true;
    enhanceApi
      .agents(symbol)
      .then((d) => alive && setState({ data: d }))
      .catch((e) => alive && setState((prev) => (prev?.data?.symbol === symbol ? prev : { error: String(e?.message ?? e) })));
    return () => {
      alive = false;
    };
  }, [symbol]);

  const stale = !!state?.data && state.data.symbol !== symbol;
  const loading = !state || stale;
  const error = state?.error ?? null;
  const data = stale ? null : (state?.data ?? null);

  return (
    <Card className="vedic-card">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 text-[#c98a2e]" />
            <CardTitle className="font-display text-base tracking-wide">
              AI Trading Agents — Debate Room
            </CardTitle>
          </div>
          {data && (
            <span className={`rounded border px-2 py-0.5 text-[11px] font-bold ${VERDICT_STYLE[data.manager.verdict] ?? ''}`}>
              <Gavel className="mr-1 inline h-3 w-3" />{data.manager.verdict} · {data.manager.score > 0 ? '+' : ''}{data.manager.score}
            </span>
          )}
        </div>
        <CardDescription className="text-[#97795a]">
          {data ? `${data.symbol_name} — six specialists argue, the fund manager decides` : 'TradingAgents-style multi-agent analysis of the selected stock'}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {loading && (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full bg-[#efdfbc]" />
            ))}
          </div>
        )}
        {error && !data && (
          <div className="rounded-md border border-[#eecfc7] bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">
            Agents unavailable — {error}
          </div>
        )}
        {data && (
          <>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {data.agents.map((a) => (
                <div key={a.agent} className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6]/80 px-3 py-2">
                  <div className="flex flex-wrap items-center justify-between gap-1">
                    <p className="text-xs font-semibold text-[#5c4327]">{a.agent}</p>
                    <span className={`rounded border px-1.5 py-px text-[9px] uppercase ${STANCE_STYLE[a.stance] ?? STANCE_STYLE.neutral}`}>
                      {a.stance}
                    </span>
                  </div>
                  <p className="text-[10px] uppercase tracking-wide text-[#b39a76]">{a.role}</p>
                  <p className="mt-1 text-[11px] leading-relaxed text-[#7c5a2e]">{a.view}</p>
                </div>
              ))}
            </div>

            <div className="rounded-xl border border-[#d9b46a] bg-gradient-to-r from-[#fdf3dc] via-[#fffdf6] to-[#e2f3e9] p-4">
              <p className="font-display text-sm font-semibold text-[#8a6a3a]">Fund Manager&apos;s verdict</p>
              <p className="mt-1 text-xs leading-relaxed text-[#5c4327]">{data.manager.view}</p>
            </div>
            <p className="text-[10px] text-[#b39a76]">{data.disclaimer}</p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
