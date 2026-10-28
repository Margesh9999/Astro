'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { modelsApi, type ZooResult, type ZooStatus } from '@/lib/astro/api-models';
import { BrainCircuit, Compass, Loader2, RefreshCw, ShieldAlert } from 'lucide-react';
import { ModelLeaderboard } from './model-leaderboard';
import { ModelForecast } from './model-forecast';
import { DirectionChart, ImportanceChart, PredVsActualChart, ScoreChart, Takeaway } from './model-charts';

type Running = { stage: string; progress: number; done?: number; total?: number; rows?: number; elapsed?: number };

/**
 * Model Lab (v1.3): ~45 models across 9 families trained on the stock's ENTIRE
 * price history with per-day sidereal planetary + technical features, ranked
 * by honest walk-forward validation, explained in plain English.
 */
export function ModelLab({ symbol, vedic }: { symbol: string; vedic: boolean }) {
  // keyed so all state resets cleanly when the instrument or zodiac changes
  return <ModelLabInner key={`${symbol}|${vedic}`} symbol={symbol} vedic={vedic} />;
}

function ModelLabInner({ symbol, vedic }: { symbol: string; vedic: boolean }) {
  const [res, setRes] = useState<ZooResult | null>(null);
  const [running, setRunning] = useState<Running | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const alive = useRef(true);

  const apply = useCallback((s: ZooStatus) => {
    if (!alive.current) return;
    if (s.status === 'done') {
      setRes(s);
      setRunning(null);
    } else if (s.status === 'failed') {
      setErr(s.error);
      setRunning(null);
    } else if (s.status === 'running' || s.status === 'started') {
      setRunning(s);
    }
  }, []);

  const start = useCallback(
    async (force: boolean) => {
      setErr(null);
      setRunning({ stage: 'starting…', progress: 1 });
      try {
        apply(await modelsApi.zooTrain(symbol, vedic, force));
      } catch (e) {
        setRunning(null);
        setErr(e instanceof Error ? e.message : String(e));
      }
    },
    [symbol, vedic, apply],
  );

  // On mount: show the cached run, or start one automatically.
  useEffect(() => {
    alive.current = true;
    modelsApi
      .zooStatus(symbol, vedic)
      .then((s) => (s.status === 'idle' ? start(false) : apply(s)))
      .catch((e) => alive.current && setErr(e instanceof Error ? e.message : String(e)));
    return () => {
      alive.current = false;
    };
  }, [symbol, vedic, apply, start]);

  // Poll while a run is in progress.
  const isRunning = running !== null;
  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(async () => {
      try {
        const s = await modelsApi.zooStatus(symbol, vedic);
        // backend restarted mid-run → restart (features are disk-cached, so this is cheap)
        apply(s.status === 'idle' ? await modelsApi.zooTrain(symbol, vedic) : s);
      } catch {
        /* transient poll errors are fine */
      }
    }, 3000);
    return () => clearInterval(id);
  }, [isRunning, symbol, vedic, apply]);

  const ins = res?.insights;
  const okCount = res ? res.leaderboard.filter((r) => r.status === 'ok').length + res.classifiers.filter((r) => r.status === 'ok').length : 0;
  const bestRow = res?.leaderboard.find((r) => r.key === res.best_model);
  const pvaName = res?.leaderboard.find((r) => r.key === res.pred_vs_actual.model)?.name ?? 'ensemble';

  return (
    <Card className="vedic-card flex h-full flex-col">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <BrainCircuit className="h-4 w-4 text-[#c98a2e]" />
            <CardTitle className="font-display text-base tracking-wide">Model Lab</CardTitle>
            <Badge variant="outline" className="border-[#dcc08a] bg-[#f9efd8] text-[10px] text-[#8a6a3a]">
              {symbol} · {vedic ? 'Vedic (sidereal)' : 'Tropical'}
            </Badge>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="h-8 border-[#dcc08a] bg-gradient-to-b from-[#fbe3bd] to-[#f6d194] text-[#7c4a12] hover:from-[#f9d9a4] hover:to-[#f0c47e]"
            onClick={() => start(true)}
            disabled={!!running}
          >
            {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            {res ? 'Retrain all models' : 'Train all models'}
          </Button>
        </div>
        <CardDescription className="text-[#97795a]">
          {res
            ? `${okCount} models across ${res.families.length} families · trained on ${res.data.rows.toLocaleString()} sessions since ${res.data.start} (${res.data.years} years, full history) · ${res.data.features} planetary + technical features`
            : 'Every model family — linear, kernel, trees & boosting, neural, time-series, probabilistic, ensembles and direction classifiers — trained on the stock’s entire history with daily planetary positions.'}
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-3">
        {running && (
          <div className="rounded-md border border-[#eed9b4] bg-[#fdf3dc] px-3 py-2 text-xs text-[#8a6a3a]">
            <span className="flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 flex-shrink-0 animate-spin text-[#d98324]" />
              <span className="min-w-0 truncate">
                Training: {running.stage}
                {running.total ? ` (${running.done}/${running.total})` : ''}
                {running.rows ? ` · ${running.rows.toLocaleString()} sessions` : ''}
              </span>
            </span>
            <Progress value={running.progress} className="mt-2 h-1" />
            <p className="mt-1 text-[10px] text-[#b39a76]">
              Full-history walk-forward training takes about 3–5 minutes; this panel updates by itself.
              {running.elapsed ? ` Elapsed ${Math.round(running.elapsed)}s.` : ''}
            </p>
          </div>
        )}

        {err && (
          <div className="rounded-md border border-[#eecfc7] bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">
            Training failed: {err}
          </div>
        )}

        {res && ins && (
          <>
            {/* verdict */}
            <div
              className={`rounded-lg border px-3 py-2.5 ${
                ins.significant
                  ? 'border-[#a8d8bf] bg-[#e2f3e9]/70'
                  : ins.beats_naive
                    ? 'border-[#eed9b4] bg-[#fdf3dc]'
                    : 'border-[#eecfc7] bg-[#fbeee9]'
              }`}
            >
              <div className="flex items-start gap-2">
                <ShieldAlert className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#c98a2e]" />
                <div className="min-w-0 space-y-1 text-[12px] leading-relaxed text-[#5c4327]">
                  <p className="font-medium">{ins.headline}</p>
                  {ins.overall.slice(1).map((l, i) => (
                    <p key={i} className="text-[11px] text-[#7c5a2e]">
                      {l}
                    </p>
                  ))}
                </div>
              </div>
              <div className="mt-2 flex items-start gap-2 rounded-md bg-[#fffdf6]/80 px-2.5 py-1.5">
                <Compass className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-[#45a79a]" />
                <p className="text-[11px] leading-relaxed text-[#2f5f55]">
                  <span className="font-semibold">What to do: </span>
                  {ins.what_to_do}
                </p>
              </div>
            </div>

            {/* forecast */}
            <div>
              <p className="mb-1.5 text-[10px] uppercase tracking-wide text-[#b39a76]">
                Ensemble forecast from {res.forecast.last_close?.toLocaleString('en-US', { maximumFractionDigits: 2 })} ·
                members: {res.forecast.members.join(', ')}
              </p>
              <ModelForecast fc={res.forecast} />
            </div>

            <Tabs defaultValue="board" className="mt-1">
              <TabsList className="grid h-auto w-full grid-cols-3 gap-0.5 bg-[#f4ead4] p-0.5 sm:grid-cols-6">
                {[
                  ['board', 'Leaderboard'],
                  ['scores', 'CV scores'],
                  ['features', 'Features'],
                  ['pva', 'Pred vs actual'],
                  ['direction', 'Direction'],
                  ['method', 'Method'],
                ].map(([v, l]) => (
                  <TabsTrigger key={v} value={v} className="h-6 text-[10px] data-[state=active]:bg-[#fffdf6]">
                    {l}
                  </TabsTrigger>
                ))}
              </TabsList>

              <TabsContent value="board" className="mt-2">
                <ModelLeaderboard rows={res.leaderboard} families={res.families} bestKey={res.best_model} />
              </TabsContent>

              <TabsContent value="scores" className="mt-2">
                <ScoreChart rows={res.leaderboard} />
              </TabsContent>

              <TabsContent value="features" className="mt-2 flex flex-col gap-2">
                <ImportanceChart imp={res.feature_importance} />
                {ins.features.length > 0 && (
                  <Takeaway>
                    {ins.features.map((l, i) => (
                      <p key={i}>{l}</p>
                    ))}
                  </Takeaway>
                )}
              </TabsContent>

              <TabsContent value="pva" className="mt-2">
                <PredVsActualChart pva={res.pred_vs_actual} modelName={pvaName} />
              </TabsContent>

              <TabsContent value="direction" className="mt-2 flex flex-col gap-2">
                <DirectionChart rows={res.classifiers} />
                <div className="grid gap-1 text-[10px] leading-snug text-[#97795a] sm:grid-cols-2">
                  {res.classifiers
                    .filter((c) => c.status === 'ok')
                    .map((c) => (
                      <p key={`${c.key}-${c.horizon}`}>
                        <span className="text-[#7c5a2e]">{c.name}</span> ({c.horizon}d): {c.insight}
                      </p>
                    ))}
                </div>
              </TabsContent>

              <TabsContent value="method" className="mt-2 space-y-2 text-[11px] leading-relaxed text-[#7c5a2e]">
                <p>{res.method}</p>
                <p>
                  Data: {res.data.rows.toLocaleString()} trading sessions from {res.data.start} to {res.data.end} (
                  {res.data.years} years — the maximum available), zodiac {res.zodiac}. Out-of-sample test:{' '}
                  {res.data.oos_days.toLocaleString()} sessions since {res.data.oos_start} ({res.data.oos_years} years, {res.data.folds}{' '}
                  blocks).
                </p>
                <p>
                  Features: daily positions (sign, longitude, speed, retrograde) of the Sun, Moon, Mercury, Venus, Mars,
                  Jupiter, Saturn, Rahu, Uranus, Neptune and Pluto; Moon nakshatra/pada/lord, tithi, paksha, lunar phase,
                  aspect scores, Jupiter–Saturn and Mars–Saturn separations, retrograde count, eclipse season, weekday and
                  month; plus lagged returns, momentum, volatility, RSI, moving-average distance, drawdown and volume —
                  technical inputs only use data up to the previous close.
                </p>
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-[#b39a76]">Speed caps (most recent rows per fold)</p>
                  <p className="text-[10px] text-[#97795a]">
                    {res.caps.map((c) => `${c.model}: ${c.max_train_rows.toLocaleString()}`).join(' · ')}
                  </p>
                </div>
                <p className="text-[10px] text-[#97795a]">
                  {res.counts.trained} trained · {res.counts.skipped} skipped ·{' '}
                  {res.counts.failed} failed · {res.runtime_seconds}s.{' '}
                  {res.leaderboard
                    .filter((r) => r.status !== 'ok')
                    .map((r) => `${r.name}: ${r.reason}`)
                    .join(' ')}
                </p>
                {bestRow && <p className="text-[10px] text-[#97795a]">Winner detail: {bestRow.insight}</p>}
                <p className="text-[10px] italic text-[#b39a76]">{res.disclaimer}</p>
              </TabsContent>
            </Tabs>
          </>
        )}
      </CardContent>
    </Card>
  );
}
