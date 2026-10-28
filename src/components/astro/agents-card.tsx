'use client';

import { useEffect, useState, type ComponentType } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { strategyApi, fmtPx, fmtGbp, type TradingAgentsResult, type Rating } from '@/lib/astro/api-strategy';
import {
  Bot,
  Briefcase,
  Building2,
  ChevronDown,
  ChevronRight,
  Flame,
  Gavel,
  LineChart,
  MessagesSquare,
  Minus,
  Newspaper,
  Plus,
  Scale,
  Shield,
  ShieldCheck,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';

type Icon = ComponentType<{ className?: string }>;

const AVATAR: Record<string, { icon: Icon; bg: string }> = {
  market: { icon: LineChart, bg: 'bg-[#e2eef3] text-[#2f6577]' },
  fundamentals: { icon: Building2, bg: 'bg-[#f9efd8] text-[#8a6a3a]' },
  sentiment: { icon: MessagesSquare, bg: 'bg-[#f3e6f0] text-[#8a4f78]' },
  news: { icon: Newspaper, bg: 'bg-[#eef0e4] text-[#5d6b3a]' },
  astro: { icon: Sparkles, bg: 'bg-[#fdf0dc] text-[#c98a2e]' },
};

const STANCE: Record<string, string> = {
  bullish: 'border-[#a8d8bf] bg-[#e2f3e9] text-[#2f7357]',
  bearish: 'border-[#e8b3a8] bg-[#fbe7e0] text-[#a34332]',
  neutral: 'border-[#dcc08a] bg-[#f9efd8] text-[#8a6a3a]',
  abstain: 'border-[#e2d8c6] bg-[#f6f1e7] text-[#9a8a72]',
};

export const RATING_STYLE: Record<Rating, string> = {
  BUY: 'border-[#7fc4a1] bg-[#d5efe1] text-[#24644a]',
  OVERWEIGHT: 'border-[#a8d8bf] bg-[#e2f3e9] text-[#2f7357]',
  HOLD: 'border-[#dcc08a] bg-[#f9efd8] text-[#8a6a3a]',
  UNDERWEIGHT: 'border-[#e8b3a8] bg-[#fbe7e0] text-[#a34332]',
  SELL: 'border-[#d98b7a] bg-[#f7d6cc] text-[#8f2f20]',
};

function Avatar({ icon: I, bg }: { icon: Icon; bg: string }) {
  return (
    <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${bg}`}>
      <I className="h-4 w-4" />
    </span>
  );
}

function ScoreBar({ score }: { score: number }) {
  const w = Math.min(50, Math.abs(score) / 2);
  return (
    <div className="relative h-1.5 w-full rounded-full bg-[#f0e4cc]">
      <div className="absolute left-1/2 top-0 h-1.5 w-px bg-[#c9b48c]" />
      <div
        className={`absolute top-0 h-1.5 rounded-full ${score >= 0 ? 'bg-[#6fb38f]' : 'bg-[#d27a66]'}`}
        style={score >= 0 ? { left: '50%', width: `${w}%` } : { right: '50%', width: `${w}%` }}
      />
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-dashed border-[#efe2c6] py-1 text-[11px] last:border-0">
      <span className="text-[#97795a]">{k}</span>
      <span className="text-right font-semibold text-[#5c4327]">{v}</span>
    </div>
  );
}

export function AgentsCard({ symbol }: { symbol: string }) {
  const [rounds, setRounds] = useState(2);
  const [llm, setLlm] = useState(false);
  const [state, setState] = useState<{ key: string; data?: TradingAgentsResult; error?: string } | null>(null);
  const key = `${symbol}|${rounds}|${llm}`;

  useEffect(() => {
    let alive = true;
    strategyApi
      .agents(symbol, { rounds, llm })
      .then((d) => alive && setState({ key, data: d }))
      .catch((e) => alive && setState({ key, error: String(e?.message ?? e) }));
    return () => {
      alive = false;
    };
  }, [symbol, rounds, llm, key]);

  const loading = !state || state.key !== key;
  const data = !loading ? state?.data : undefined;
  const error = !loading ? state?.error : undefined;
  const pm = data?.portfolio_manager;

  return (
    <Card className="vedic-card">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 text-[#c98a2e]" />
            <CardTitle className="font-display text-base tracking-wide">TradingAgents — Multi-Agent Desk</CardTitle>
          </div>
          {pm && (
            <span className={`rounded border px-2 py-0.5 text-[11px] font-bold ${RATING_STYLE[pm.rating]}`}>
              <Gavel className="mr-1 inline h-3 w-3" />
              {pm.rating} · {pm.confidence}%
            </span>
          )}
        </div>
        <CardDescription className="text-[#97795a]">
          Analysts → Bull/Bear researchers → Research Manager → Trader → Risk team → Portfolio Manager. Structure inspired by{' '}
          <a
            href="https://github.com/TauricResearch/TradingAgents"
            target="_blank"
            rel="noreferrer"
            className="underline decoration-[#d9b46a] underline-offset-2"
          >
            TauricResearch/TradingAgents
          </a>
          .
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {/* controls */}
        <div className="flex flex-wrap items-center gap-3 text-[11px] text-[#7c5a2e]">
          <div className="flex items-center gap-1">
            <span>Debate rounds</span>
            {[1, 2, 3].map((n) => (
              <button
                key={n}
                onClick={() => setRounds(n)}
                className={`h-6 w-6 rounded border text-[11px] font-semibold ${
                  rounds === n ? 'border-[#d9b46a] bg-[#fdf3dc] text-[#8a6a3a]' : 'border-[#efe2c6] bg-[#fffdf6] text-[#b39a76]'
                }`}
              >
                {n}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-1.5">
            <Switch checked={llm} disabled={!!data && !data.llm_available} onCheckedChange={setLlm} />
            <span>Claude narration</span>
          </label>
          {data && (
            <span className="text-[10px] text-[#b39a76]">
              {data.llm_available ? `mode: ${data.mode}` : 'Rule-based mode (set ANTHROPIC_API_KEY on the backend to enable Claude narration)'}
            </span>
          )}
        </div>

        {loading && (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full bg-[#efdfbc]" />
            ))}
          </div>
        )}
        {error && (
          <div className="rounded-md border border-[#eecfc7] bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">
            Agents unavailable — {error}
          </div>
        )}

        {data && pm && (
          <>
            {/* flow */}
            <div className="flex flex-wrap items-center gap-1 text-[10px] text-[#8a6a3a]">
              {data.flow.map((f, i) => (
                <span key={f} className="flex items-center gap-1">
                  <span className="rounded-full border border-[#ecdcb8] bg-[#fffaf0] px-2 py-0.5">{f}</span>
                  {i < data.flow.length - 1 && <ChevronRight className="h-3 w-3 text-[#c9b48c]" />}
                </span>
              ))}
            </div>

            {/* decision hero */}
            <div className="rounded-xl border border-[#d9b46a] bg-gradient-to-r from-[#fdf3dc] via-[#fffdf6] to-[#e2f3e9] p-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className={`rounded-lg border px-3 py-1 font-display text-xl font-bold tracking-wide ${RATING_STYLE[pm.rating]}`}>
                  {pm.rating}
                </span>
                <div className="min-w-[140px] flex-1">
                  <div className="flex justify-between text-[10px] uppercase tracking-wide text-[#97795a]">
                    <span>Portfolio Manager confidence</span>
                    <span className="font-semibold text-[#5c4327]">{pm.confidence}%</span>
                  </div>
                  <div className="mt-1 h-2 rounded-full bg-[#f0e4cc]">
                    <div className="h-2 rounded-full bg-[#c98a2e]" style={{ width: `${pm.confidence}%` }} />
                  </div>
                  <p className="mt-1 text-[10px] text-[#97795a]">
                    Final score {pm.score > 0 ? '+' : ''}
                    {pm.score} / 100 · analyst composite {data.analyst_composite > 0 ? '+' : ''}
                    {data.analyst_composite}
                  </p>
                </div>
              </div>
              <p className="mt-3 text-[10px] font-semibold uppercase tracking-wide text-[#8a6a3a]">What this means for you</p>
              <p className="mt-0.5 text-xs leading-relaxed text-[#5c4327]">{data.plain_english}</p>
            </div>

            <Tabs defaultValue="analysts">
              <TabsList className="h-auto flex-wrap bg-[#f4e8cf]">
                <TabsTrigger value="analysts" className="text-xs data-[state=active]:bg-[#fffdf6]">Analyst Team</TabsTrigger>
                <TabsTrigger value="debate" className="text-xs data-[state=active]:bg-[#fffdf6]">Bull vs Bear</TabsTrigger>
                <TabsTrigger value="trader" className="text-xs data-[state=active]:bg-[#fffdf6]">Trader</TabsTrigger>
                <TabsTrigger value="risk" className="text-xs data-[state=active]:bg-[#fffdf6]">Risk &amp; Decision</TabsTrigger>
              </TabsList>

              <TabsContent value="analysts" className="mt-3">
                <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                  {data.analysts.map((a) => {
                    const av = AVATAR[a.key] ?? AVATAR.market;
                    return (
                      <div key={a.key} className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6]/80 p-3">
                        <div className="flex items-start gap-2">
                          <Avatar {...av} />
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center justify-between gap-1">
                              <p className="text-xs font-semibold text-[#5c4327]">{a.agent}</p>
                              <span className={`rounded border px-1.5 py-px text-[9px] uppercase ${STANCE[a.stance] ?? STANCE.neutral}`}>
                                {a.stance}
                                {!a.abstain && ` ${a.score > 0 ? '+' : ''}${Math.round(a.score)}`}
                              </span>
                            </div>
                            <p className="text-[10px] uppercase tracking-wide text-[#b39a76]">{a.role}</p>
                          </div>
                        </div>
                        {!a.abstain && <div className="mt-2"><ScoreBar score={a.score} /></div>}
                        <p className="mt-2 text-[11px] leading-relaxed text-[#7c5a2e]">{a.report}</p>
                        {a.key_points.length > 0 && (
                          <ul className="mt-1.5 space-y-0.5">
                            {a.key_points.slice(0, 4).map((p, i) => (
                              <li key={i} className="flex gap-1 text-[10.5px] leading-snug text-[#7c5a2e]">
                                {p.sign > 0 ? (
                                  <Plus className="mt-0.5 h-3 w-3 shrink-0 text-[#2f7357]" />
                                ) : (
                                  <Minus className="mt-0.5 h-3 w-3 shrink-0 text-[#a34332]" />
                                )}
                                <span className="break-words">{p.text}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                        {a.headlines && a.headlines.length > 0 && (
                          <ul className="mt-1.5 space-y-0.5 border-t border-dashed border-[#efe2c6] pt-1">
                            {a.headlines.slice(0, 5).map((h, i) => (
                              <li key={i} className="text-[10px] text-[#97795a]">
                                <a href={h.url || undefined} target="_blank" rel="noreferrer" className="hover:underline">
                                  {h.title}
                                </a>{' '}
                                <span className={h.sentiment > 0 ? 'text-[#2f7357]' : h.sentiment < 0 ? 'text-[#a34332]' : ''}>
                                  ({h.sentiment > 0 ? '+' : ''}
                                  {h.sentiment})
                                </span>
                              </li>
                            ))}
                          </ul>
                        )}
                        <p className="mt-1.5 text-[9.5px] text-[#b39a76]">
                          Data: {a.data_used.join(' · ')} · confidence {Math.round(a.confidence * 100)}%
                        </p>
                      </div>
                    );
                  })}
                </div>
              </TabsContent>

              <TabsContent value="debate" className="mt-3 flex flex-col gap-2">
                <div className="grid grid-cols-2 gap-2 text-[10px]">
                  <div className="rounded-md border border-[#cfe8da] bg-[#eef8f2] p-2 text-[#2f7357]">
                    <TrendingUp className="mr-1 inline h-3 w-3" />
                    Bull evidence {Math.round(data.debate.bull_strength)} · {data.debate.bull_points} points
                  </div>
                  <div className="rounded-md border border-[#f0d0c6] bg-[#fdf0eb] p-2 text-[#a34332]">
                    <TrendingDown className="mr-1 inline h-3 w-3" />
                    Bear evidence {Math.round(data.debate.bear_strength)} · {data.debate.bear_points} points
                  </div>
                </div>
                {data.debate.rounds.map((r) => (
                  <Collapsible key={r.round} defaultOpen={r.round === 1} className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6]/80">
                    <CollapsibleTrigger className="group flex w-full items-center justify-between px-3 py-2 text-left text-xs font-semibold text-[#5c4327]">
                      Round {r.round}
                      <ChevronDown className="h-3.5 w-3.5 text-[#b39a76] transition-transform group-data-[state=open]:rotate-180" />
                    </CollapsibleTrigger>
                    <CollapsibleContent className="flex flex-col gap-2 px-3 pb-3">
                      <div className="flex gap-2">
                        <Avatar icon={TrendingUp} bg="bg-[#e2f3e9] text-[#2f7357]" />
                        <div className="rounded-lg rounded-tl-none border border-[#cfe8da] bg-[#f3fbf6] px-3 py-2">
                          <p className="text-[10px] font-semibold uppercase text-[#2f7357]">Bull Researcher</p>
                          <p className="text-[11px] leading-relaxed text-[#46604f]">{r.bull.text}</p>
                        </div>
                      </div>
                      <div className="flex flex-row-reverse gap-2">
                        <Avatar icon={TrendingDown} bg="bg-[#fbe7e0] text-[#a34332]" />
                        <div className="rounded-lg rounded-tr-none border border-[#f0d0c6] bg-[#fdf5f1] px-3 py-2">
                          <p className="text-[10px] font-semibold uppercase text-[#a34332]">Bear Researcher</p>
                          <p className="text-[11px] leading-relaxed text-[#6e4a40]">{r.bear.text}</p>
                        </div>
                      </div>
                    </CollapsibleContent>
                  </Collapsible>
                ))}
                <div className="flex gap-2 rounded-lg border border-[#d9b46a] bg-[#fdf6e6] p-3">
                  <Avatar icon={Scale} bg="bg-[#f9efd8] text-[#8a6a3a]" />
                  <div>
                    <p className="text-xs font-semibold text-[#5c4327]">
                      Research Manager · <span className={`rounded border px-1 text-[10px] ${RATING_STYLE[data.research_manager.recommendation]}`}>{data.research_manager.recommendation}</span>
                    </p>
                    <p className="mt-1 text-[11px] leading-relaxed text-[#7c5a2e]">{data.research_manager.view}</p>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="trader" className="mt-3">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <div className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6]/80 p-3">
                    <div className="mb-2 flex items-center gap-2">
                      <Avatar icon={Briefcase} bg="bg-[#e2eef3] text-[#2f6577]" />
                      <div>
                        <p className="text-xs font-semibold text-[#5c4327]">Trader</p>
                        <p className="text-[10px] uppercase text-[#b39a76]">concrete plan · {data.trader.horizon}</p>
                      </div>
                    </div>
                    <Row k="Action" v={data.trader.action} />
                    <Row k={data.trader.direction === 'reduce' ? 'Sell zone' : 'Entry zone'} v={`${fmtPx(data.trader.entry_low)} – ${fmtPx(data.trader.entry_high)}`} />
                    <Row k="Stop" v={fmtPx(data.trader.stop)} />
                    <Row k="Targets" v={`${fmtPx(data.trader.target_1)} → ${fmtPx(data.trader.target_2)}`} />
                    <Row k="Reward : risk (T1)" v={`${data.trader.reward_risk.toFixed(1)} : 1`} />
                    <Row k="Size (1% risk)" v={`${fmtGbp(data.trader.size_value)} of ${fmtGbp(data.capital)}`} />
                    {data.trader.avoid_dates.length > 0 && <Row k="Avoid new risk on" v={data.trader.avoid_dates.join(', ')} />}
                  </div>
                  <p className="text-[11px] leading-relaxed text-[#7c5a2e]">{data.trader.view}</p>
                </div>
              </TabsContent>

              <TabsContent value="risk" className="mt-3 flex flex-col gap-2">
                <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                  {data.risk_team.views.map((v) => {
                    const I = v.stance === 'aggressive' ? Flame : v.stance === 'neutral' ? ShieldCheck : Shield;
                    const bg =
                      v.stance === 'aggressive'
                        ? 'bg-[#fbe7e0] text-[#a34332]'
                        : v.stance === 'neutral'
                          ? 'bg-[#f9efd8] text-[#8a6a3a]'
                          : 'bg-[#e2eef3] text-[#2f6577]';
                    return (
                      <div key={v.agent} className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6]/80 p-3">
                        <div className="flex items-center gap-2">
                          <Avatar icon={I} bg={bg} />
                          <div>
                            <p className="text-xs font-semibold text-[#5c4327]">{v.agent}</p>
                            <p className="text-[10px] text-[#b39a76]">size ×{v.size_mult.toFixed(2)}</p>
                          </div>
                        </div>
                        <p className="mt-2 text-[11px] leading-relaxed text-[#7c5a2e]">{v.view}</p>
                      </div>
                    );
                  })}
                </div>
                <p className="text-[11px] text-[#97795a]">{data.risk_team.summary}</p>
                <div className="flex gap-2 rounded-xl border border-[#d9b46a] bg-gradient-to-r from-[#fdf3dc] to-[#fffdf6] p-3">
                  <Avatar icon={Gavel} bg="bg-[#fdf0dc] text-[#c98a2e]" />
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-[#5c4327]">
                      Portfolio Manager — final decision{' '}
                      <span className={`rounded border px-1 text-[10px] ${RATING_STYLE[pm.rating]}`}>{pm.rating}</span>
                    </p>
                    <p className="mt-1 text-[11px] leading-relaxed text-[#5c4327]">{pm.view}</p>
                    <p className="mt-1 text-[10px] text-[#97795a]">
                      Final size {fmtGbp(pm.final_plan.size_value)} ({pm.final_plan.size_pct_capital ?? 0}% of capital) · stop{' '}
                      {fmtPx(pm.final_plan.stop)} · targets {fmtPx(pm.final_plan.target_1)} / {fmtPx(pm.final_plan.target_2)}
                    </p>
                  </div>
                </div>
              </TabsContent>
            </Tabs>
            <p className="text-[10px] text-[#b39a76]">{data.disclaimer}</p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
