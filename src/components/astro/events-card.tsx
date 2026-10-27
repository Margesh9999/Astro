'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { enhanceApi } from '@/lib/astro/api';
import type { EventsForecast, ForecastEvent } from '@/lib/astro/types';
import { CalendarDays, Lightbulb } from 'lucide-react';

const TYPE_STYLES: Record<string, { badge: string; label: string }> = {
  conjunction: { badge: 'border-[#e3c68f] bg-[#fbeecb] text-[#96660f]', label: 'conj' },
  opposition: { badge: 'border-[#e8b3a8] bg-[#fbe7e0] text-[#a34332]', label: 'opp' },
  trine: { badge: 'border-[#a8d8bf] bg-[#e2f3e9] text-[#2f7357]', label: 'trine' },
  square: { badge: 'border-[#eec3a3] bg-[#fbeadd] text-[#a35a22]', label: 'square' },
  sextile: { badge: 'border-[#a3d0c8] bg-[#e0f1ee] text-[#2e6e64]', label: 'sextile' },
  ingress: { badge: 'border-[#cbb8dd] bg-[#efe7f8] text-[#6b4e93]', label: 'ingress' },
  lunar_phase: { badge: 'border-[#d9c9b2] bg-[#f4ecdd] text-[#7a6248]', label: 'moon' },
};

export function EventsCard({ symbol }: { symbol: string }) {
  const [state, setState] = useState<{ data?: EventsForecast; error?: string } | null>(null);

  useEffect(() => {
    let alive = true;
    enhanceApi
      .eventsForecast(symbol, 45)
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
  const events: ForecastEvent[] = data?.events ?? [];

  return (
    <Card className="vedic-card flex h-full flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CalendarDays className="h-4 w-4 text-[#c98a2e]" />
            <CardTitle className="font-display text-base tracking-wide">
              Sky Events × Your Stock — 45 Days
            </CardTitle>
          </div>
          {data && (
            <Badge variant="outline" className="border-[#dcc08a] bg-[#f9efd8] text-[10px] text-[#8a6a3a]">
              {data.count} events
            </Badge>
          )}
        </div>
        <CardDescription className="text-[#97795a]">
          {data
            ? `${data.symbol_name} · trend ${data.trend} · vol ${data.vol_state} — every event carries its meaning for this stock`
            : 'Exact aspects, phases & ingresses with actionable stock-specific guidance'}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col">
        {loading && (
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full bg-[#efdfbc]" />
            ))}
          </div>
        )}
        {error && !data && (
          <div className="rounded-md border border-[#eecfc7] bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">
            Could not load events: {error}
          </div>
        )}
        {data && events.length === 0 && (
          <p className="py-8 text-center text-xs text-[#97795a]">No major events in the window.</p>
        )}
        {data && events.length > 0 && (
          <ScrollArea className="warm-scroll h-[420px] pr-2">
            <div className="space-y-2">
              {events.map((e, i) => {
                const style = TYPE_STYLES[e.type] ?? TYPE_STYLES.lunar_phase;
                const d = new Date(e.date + 'T00:00:00');
                const day = d.getDate();
                const month = d.toLocaleString('en-US', { month: 'short' });
                return (
                  <div
                    key={i}
                    className="flex items-start gap-3 rounded-md border border-[#f0e4cc] bg-[#fdf8ec]/80 px-3 py-2"
                  >
                    <div className="flex h-10 w-10 flex-shrink-0 flex-col items-center justify-center rounded-md border border-[#e8d5ae] bg-gradient-to-b from-[#fffdf6] to-[#f9efd8]">
                      <span className="text-[9px] uppercase text-[#b39a76]">{month}</span>
                      <span className="font-mono text-sm font-semibold text-[#7c5a2e]">{day}</span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <p className="text-xs font-medium text-[#5c4327]">{e.event}</p>
                        <span className={`rounded border px-1.5 py-px text-[9px] uppercase ${style.badge}`}>
                          {style.label}
                        </span>
                        {e.significance === 'High' && (
                          <span className="rounded bg-[#f6ddad] px-1.5 py-px text-[9px] font-medium text-[#8a5a12]">
                            high
                          </span>
                        )}
                      </div>
                      <p className="mt-0.5 text-[11px] text-[#97795a]">{e.description}</p>
                      {e.meaning && (
                        <div className="mt-1.5 flex items-start gap-1.5 rounded border border-[#e8ddb8] bg-[#fffdf6] px-2 py-1.5">
                          <Lightbulb className="mt-0.5 h-3 w-3 flex-shrink-0 text-[#c98a2e]" />
                          <p className="text-[11px] leading-snug text-[#7c5a2e]">{e.meaning}</p>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}
