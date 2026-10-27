'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { astroApi, enhanceApi } from '@/lib/astro/api';
import type { PredictResult, TrainResult, ZooTrainResult } from '@/lib/astro/types';
import { BrainCircuit, Loader2, Play, Trophy, Lightbulb } from 'lucide-react';

const FEATURE_COLORS = ['#e8a04c', '#db8a3a', '#cf7a3f', '#c96f4a', '#b0763a', '#9b8ac4', '#8b7bb8', '#e8788a', '#45a79a', '#7a6a58'];

const TOOLTIP_STYLE = {
  background: '#fffdf6',
  border: '1px solid #e8d5ae',
  borderRadius: 10,
  fontSize: 11,
  color: '#5c4327',
  boxShadow: '0 4px 16px rgba(140, 104, 50, 0.15)',
} as const;

function prettyFeature(name: string) {
  return name
    .replace(/_/g, ' ')
    .replace(/\bsign (\d+)\b/, (_, d) => `sign ${['Ar', 'Ta', 'Ge', 'Cn', 'Le', 'Vi', 'Li', 'Sc', 'Sg', 'Cp', 'Aq', 'Pi'][Number(d)]}`)
    .replace(' aspect score', 'aspect');
}

export function ModelLab({ symbol, vedic }: { symbol: string; vedic: boolean }) {
  const [training, setTraining] = useState(false);
  const [trainRes, setTrainRes] = useState<TrainResult | null>(null);
  const [trainErr, setTrainErr] = useState<string | null>(null);
  const [predicting, setPredicting] = useState(false);
  const [predRes, setPredRes] = useState<PredictResult | null>(null);
  const [predErr, setPredErr] = useState<string | null>(null);

  // T5/T7 model zoo state
  const [zoo, setZoo] = useState<ZooTrainResult | null>(null);
  const [zooBusy, setZooBusy] = useState(false);
  const [zooStage, setZooStage] = useState<string>('');
  const [zooErr, setZooErr] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const runTrain = useCallback(async () => {
    setTraining(true);
    setTrainErr(null);
    setTrainRes(null);
    try {
      const res = await astroApi.train(symbol, 5, vedic);
      setTrainRes(res);
    } catch (e) {
      setTrainErr(e instanceof Error ? e.message : String(e));
    } finally {
      setTraining(false);
    }
  }, [symbol, vedic]);

  const runPredict = useCallback(async () => {
    setPredicting(true);
    setPredErr(null);
    setPredRes(null);
    try {
      const res = await astroApi.predict(symbol, 30, vedic);
      setPredRes(res);
    } catch (e) {
      setPredErr(e instanceof Error ? e.message : String(e));
    } finally {
      setPredicting(false);
    }
  }, [symbol, vedic]);

  // Auto-train the 5y baseline on mount / symbol change
  useEffect(() => {
    let cancelled = false;
    const autoRun = async () => {
      setTraining(true);
      setTrainErr(null);
      try {
        const res = await astroApi.train(symbol, 5, vedic);
        if (!cancelled) setTrainRes(res);
      } catch (e) {
        if (!cancelled) setTrainErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setTraining(false);
      }
    };
    autoRun();
    return () => {
      cancelled = true;
    };
  }, [symbol, vedic]);

  // T7: check for a cached full-history zoo result for this symbol
  useEffect(() => {
    let alive = true;
    setZoo(null);
    setZooErr(null);
    enhanceApi
      .trainZooStatus(symbol, vedic)
      .then((r) => {
        if (alive && r.status === 'done' && r.zoo) setZoo(r);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [symbol, vedic]);

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const runZoo = useCallback(async () => {
    setZooBusy(true);
    setZooErr(null);
    setZooStage('starting…');
    try {
      await enhanceApi.trainZoo({ symbol, use_vedic: vedic, full_history: true });
      stopPoll();
      pollRef.current = setInterval(async () => {
        try {
          const r = await enhanceApi.trainZooStatus(symbol, vedic);
          if (r.status === 'running') {
            setZooStage(r.stage ?? 'training…');
          } else {
            stopPoll();
            setZooBusy(false);
            if (r.status === 'done' && r.zoo) {
              setZoo(r);
              setZooStage('');
            } else if (r.status === 'failed') {
              setZooErr(r.error ?? 'training failed');
            }
          }
        } catch {
          /* transient poll errors are fine */
        }
      }, 4000);
    } catch (e) {
      setZooBusy(false);
      setZooErr(e instanceof Error ? e.message : String(e));
    }
  }, [symbol, vedic, stopPoll]);

  useEffect(() => stopPoll, [stopPoll]);

  const importance = trainRes
    ? Object.entries(trainRes.feature_importance)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10)
        .map(([name, imp]) => ({ name: prettyFeature(name), importance: Number((imp * 100).toFixed(2)) }))
    : [];

  const predData = predRes
    ? predRes.dates.map((d, i) => ({
        date: d.slice(5),
        price: predRes.projected_prices[i],
        cum: predRes.cumulative_returns[i] * 100,
      }))
    : [];
  const last = predData[predData.length - 1];
  const totalChange = predRes && predRes.current_price ? ((last?.price - predRes.current_price) / predRes.current_price) * 100 : 0;

  return (
    <Card className="vedic-card flex h-full flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BrainCircuit className="h-4 w-4 text-[#c98a2e]" />
            <CardTitle className="font-display text-base tracking-wide">Model Lab</CardTitle>
          </div>
          <Badge variant="outline" className="border-[#dcc08a] bg-[#f9efd8] text-[10px] text-[#8a6a3a]">
            {symbol} · {vedic ? 'Vedic' : 'Tropical'}
          </Badge>
        </div>
        <CardDescription className="text-[#97795a]">
          13-model leaderboard with walk-forward validation · trained on the stock&apos;s FULL history
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        <Tabs defaultValue="zoo" className="mt-0">
          <TabsList className="grid h-7 w-full grid-cols-2 bg-[#f4ead4]">
            <TabsTrigger value="zoo" className="h-5 text-[10px] data-[state=active]:bg-[#fffdf6]">
              Model Zoo (full history)
            </TabsTrigger>
            <TabsTrigger value="baseline" className="h-5 text-[10px] data-[state=active]:bg-[#fffdf6]">
              Baseline 5y
            </TabsTrigger>
          </TabsList>

          {/* ── T5 + T7: model zoo on the ENTIRE history ── */}
          <TabsContent value="zoo" className="mt-2 flex flex-col gap-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-[11px] leading-snug text-[#97795a]">
                Trains 13 model families on every trading day since inception, ranks them by walk-forward CV
                R², and explains the winner in plain English.
              </p>
              <Button
                size="sm"
                variant="outline"
                className="h-8 flex-shrink-0 border-[#dcc08a] bg-gradient-to-b from-[#fbe3bd] to-[#f6d194] text-[#7c4a12] hover:from-[#f9d9a4] hover:to-[#f0c47e]"
                onClick={runZoo}
                disabled={zooBusy}
              >
                {zooBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                {zoo ? 'Retrain' : 'Train all'}
              </Button>
            </div>

            {zooBusy && (
              <div className="rounded-md border border-[#eed9b4] bg-[#fdf3dc] px-3 py-2 text-xs text-[#8a6a3a]">
                <span className="flex items-center gap-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-[#d98324]" />
                  {zooStage || 'training…'} — full history can take a few minutes; this panel updates automatically.
                </span>
                <Progress value={66} className="mt-2 h-1" />
              </div>
            )}

            {zooErr && (
              <div className="rounded-md border border-[#eecfc7] bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">
                Zoo training failed: {zooErr}
              </div>
            )}

            {zoo?.zoo && (
              <>
                <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                  <Trophy className="h-3.5 w-3.5 text-[#c98a2e]" />
                  <span className="rounded border border-[#a8d8bf] bg-[#e2f3e9] px-1.5 py-px font-semibold text-[#2f7357]">
                    best: {zoo.zoo.best_model}
                  </span>
                  <span className="font-mono text-[#97795a]">
                    CV R² {zoo.zoo.best_cv_r2.toFixed(4)}
                  </span>
                  <span className="text-[#b39a76]">
                    · {zoo.samples} days · {zoo.history_start} → {zoo.history_end} ({zoo.years_covered}y)
                  </span>
                </div>

                <div className="warm-scroll max-h-64 space-y-1 overflow-y-auto pr-1">
                  {zoo.zoo.leaderboard.map((m, i) => (
                    <div
                      key={m.model}
                      className={`rounded border px-2 py-1.5 text-[11px] ${
                        i === 0 ? 'border-[#a8d8bf] bg-[#e2f3e9]/60' : 'border-[#f0e4cc] bg-[#fffdf6]/70'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium text-[#5c4327]">
                          #{i + 1} {m.model}
                        </span>
                        <span className="font-mono text-[#7c5a2e]">{m.cv_r2.toFixed(4)}</span>
                      </div>
                      <p className="mt-0.5 text-[10px] leading-snug text-[#97795a]">{m.note}</p>
                    </div>
                  ))}
                </div>

                <div className="flex items-start gap-1.5 rounded-lg border border-[#e8ddb8] bg-[#fdf8ec] px-2.5 py-2">
                  <Lightbulb className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-[#c98a2e]" />
                  <p className="text-[11px] leading-relaxed text-[#7c5a2e]">{zoo.zoo.analysis}</p>
                </div>
              </>
            )}
          </TabsContent>

          {/* ── Baseline 5y (original lab) ── */}
          <TabsContent value="baseline" className="mt-2 flex flex-col gap-4">
            <div className="flex items-center justify-between gap-2">
              <div className="text-xs text-[#97795a]">
                {training ? (
                  <span className="flex items-center gap-2">
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-[#d98324]" />
                    Collecting ephemeris features & training…
                  </span>
                ) : trainRes ? (
                  <span>
                    <span className="text-[#b39a76]">{trainRes.samples} samples · </span>
                    <span className="font-mono text-[#7c5a2e]">{trainRes.date_range}</span>
                  </span>
                ) : (
                  'Model not trained yet.'
                )}
              </div>
              <Button
                size="sm"
                variant="outline"
                className="h-8 border-[#dcc08a] bg-gradient-to-b from-[#fbe3bd] to-[#f6d194] text-[#7c4a12] hover:from-[#f9d9a4] hover:to-[#f0c47e]"
                onClick={runTrain}
                disabled={training}
              >
                {training ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                Train
              </Button>
            </div>

            {trainErr && (
              <div className="rounded-md border border-[#eecfc7] bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">
                Training failed: {trainErr}
              </div>
            )}

            {trainRes && (
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-md border border-[#f0e4cc] bg-[#fdf8ec]/80 p-2.5">
                  <p className="text-[10px] uppercase tracking-wide text-[#b39a76]">Linear R²</p>
                  <p className="mt-0.5 font-mono text-lg text-[#5c4327]">{trainRes.linear_r2.toFixed(4)}</p>
                  <Progress value={Math.max(0, Math.min(100, trainRes.linear_r2 * 100))} className="mt-1.5 h-1" />
                </div>
                <div className="rounded-md border border-[#f0e4cc] bg-[#fdf8ec]/80 p-2.5">
                  <p className="text-[10px] uppercase tracking-wide text-[#b39a76]">Random Forest R²</p>
                  <p className="mt-0.5 font-mono text-lg text-[#5c4327]">{trainRes.rf_r2.toFixed(4)}</p>
                  <Progress value={Math.max(0, Math.min(100, trainRes.rf_r2 * 100))} className="mt-1.5 h-1" />
                </div>
              </div>
            )}

            {importance.length > 0 && (
              <div>
                <p className="mb-1.5 text-[10px] uppercase tracking-wide text-[#b39a76]">
                  Top features (RF importance %)
                </p>
                <div className="h-[150px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={importance} layout="vertical" margin={{ left: 0, right: 8, top: 0, bottom: 0 }}>
                      <XAxis type="number" hide />
                      <YAxis
                        type="category"
                        dataKey="name"
                        width={120}
                        tick={{ fill: '#97795a', fontSize: 9 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [`${v}%`, 'importance']} />
                      <Bar dataKey="importance" radius={[0, 4, 4, 0]} isAnimationActive={false}>
                        {importance.map((_, i) => (
                          <Cell key={i} fill={FEATURE_COLORS[i % FEATURE_COLORS.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Predict */}
            <div className="mt-auto border-t border-[#f0e4cc] pt-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-[10px] uppercase tracking-wide text-[#b39a76]">30-day projection</p>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 border-[#dcc08a] bg-gradient-to-b from-[#fbe3bd] to-[#f6d194] text-[#7c4a12] hover:from-[#f9d9a4] hover:to-[#f0c47e]"
                  onClick={runPredict}
                  disabled={predicting || !trainRes}
                >
                  {predicting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                  Predict
                </Button>
              </div>

              {predErr && (
                <div className="mt-2 rounded-md border border-[#eecfc7] bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">
                  Prediction failed: {predErr}
                </div>
              )}

              {predRes && predData.length > 0 && (
                <div className="mt-2">
                  <div className="mb-1 flex items-baseline justify-between text-xs">
                    <span className="text-[#97795a]">
                      {predRes.current_price.toLocaleString('en-US', { maximumFractionDigits: 2 })} →{' '}
                      <span className="font-mono text-[#5c4327]">
                        {last.price.toLocaleString('en-US', { maximumFractionDigits: 2 })}
                      </span>
                    </span>
                    <span className={totalChange >= 0 ? 'font-medium text-[#3f8a6e]' : 'font-medium text-[#c9553f]'}>
                      {totalChange >= 0 ? '+' : ''}
                      {totalChange.toFixed(2)}% / 30d
                    </span>
                  </div>
                  <div className="h-[120px]">
                    <Tabs defaultValue="price" className="h-full">
                      <TabsList className="mb-1 grid h-7 w-full grid-cols-2 bg-[#f4ead4]">
                        <TabsTrigger value="price" className="h-5 text-[10px] data-[state=active]:bg-[#fffdf6]">Projected price</TabsTrigger>
                        <TabsTrigger value="cum" className="h-5 text-[10px] data-[state=active]:bg-[#fffdf6]">Cumulative return</TabsTrigger>
                      </TabsList>
                      <TabsContent value="price" className="mt-0 h-[88px]">
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart data={predData} margin={{ top: 2, right: 4, bottom: 0, left: 4 }}>
                            <ReferenceLine
                              y={predRes.current_price}
                              stroke="#cfa96a"
                              strokeDasharray="4 4"
                              strokeWidth={1}
                            />
                            <XAxis dataKey="date" hide />
                            <YAxis hide domain={['auto', 'auto']} />
                            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number) => [v.toFixed(2), 'price']} />
                            <Area
                              type="monotone"
                              dataKey="price"
                              stroke="#d98324"
                              strokeWidth={1.6}
                              fill="rgba(232, 160, 76, 0.16)"
                              isAnimationActive={false}
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      </TabsContent>
                      <TabsContent value="cum" className="mt-0 h-[88px]">
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart data={predData} margin={{ top: 2, right: 4, bottom: 0, left: 4 }}>
                            <ReferenceLine y={0} stroke="#cfa96a" strokeDasharray="4 4" strokeWidth={1} />
                            <XAxis dataKey="date" hide />
                            <YAxis hide domain={['auto', 'auto']} />
                            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number) => [`${v.toFixed(2)}%`, 'cum. return']} />
                            <Area
                              type="monotone"
                              dataKey="cum"
                              stroke={totalChange >= 0 ? '#4a9a7e' : '#cf5b54'}
                              strokeWidth={1.6}
                              fill={totalChange >= 0 ? 'rgba(74, 154, 126, 0.14)' : 'rgba(207, 91, 84, 0.14)'}
                              isAnimationActive={false}
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      </TabsContent>
                    </Tabs>
                  </div>
                  <p className="mt-1 text-[10px] leading-relaxed text-[#b39a76]">
                    Baseline R² ≈ 0 — planetary features carry no proven signal; projections illustrate the
                    methodology only.
                  </p>
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
