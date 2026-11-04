'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ExternalLink, Globe, Lightbulb, Plus, Radio, Trash2, Youtube } from 'lucide-react';
import { astrologersApi } from '@/lib/astro/api-astrologers';
import type { AstrologerFeed, Direction, Discover, Insights, LoggedCall, ScoredCall } from '@/lib/astro/api-astrologers';

const DEFAULT_HANDLES = ['@AstroKapoorcom'];
const LS_SOURCES = 'astro.astrologers.sources';
const LS_CALLS = 'astro.astrologers.calls';

const DIR: Record<Direction, { cls: string; label: string }> = {
  bullish: { cls: 'border-[#cfe0c2] bg-[#eef5e8] text-[#4f7a3f]', label: 'bullish' },
  bearish: { cls: 'border-[#eec3b8] bg-[#fbe9e3] text-[#a14d3c]', label: 'bearish' },
  volatile: { cls: 'border-[#e3d6ee] bg-[#f8f1fb] text-[#6b4e93]', label: 'volatile' },
  neutral: { cls: 'border-[#ecdec2] bg-[#fdf8ec] text-[#97795a]', label: 'no clear call' },
};

function load<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : fallback;
  } catch {
    return fallback;
  }
}
function save(key: string, v: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(v));
  } catch {
    /* private mode: keep in memory only */
  }
}

function Pill({ d }: { d: Direction }) {
  return <span className={`rounded border px-1.5 py-px text-[9.5px] uppercase ${DIR[d].cls}`}>{DIR[d].label}</span>;
}

function InsightsBox({ ins, title }: { ins: Insights; title: string }) {
  const chips = (label: string, rows?: [string, number][]) =>
    rows && rows.length > 0 ? (
      <div className="flex flex-wrap items-center gap-1">
        <span className="text-[10px] uppercase tracking-wider text-[#b39a76]">{label}</span>
        {rows.map(([k, c]) => (
          <span key={k} className="rounded bg-[#f4ecdd] px-1.5 py-px text-[10.5px] text-[#7c5a2e]">
            {k} <span className="font-mono">{c}</span>
          </span>
        ))}
      </div>
    ) : null;
  const d = ins.directions;
  const tot = d ? d.bullish + d.bearish + d.volatile + d.neutral : 0;
  return (
    <div className="space-y-1.5 rounded-md border border-[#e3d6ee] bg-[#f8f1fb] px-3 py-2 text-xs text-[#5e3f7f]">
      <p className="font-semibold">{title}</p>
      {d && tot > 0 && (
        <div className="flex h-2 w-full overflow-hidden rounded-full bg-[#efe7f8]" aria-label="direction mix">
          <div className="bg-[#6f9e5b]" style={{ width: `${(d.bullish / tot) * 100}%` }} title={`bullish ${d.bullish}`} />
          <div className="bg-[#c9553f]" style={{ width: `${(d.bearish / tot) * 100}%` }} title={`bearish ${d.bearish}`} />
          <div className="bg-[#8a6aa3]" style={{ width: `${(d.volatile / tot) * 100}%` }} title={`big move ${d.volatile}`} />
          <div className="bg-[#e3d6ee]" style={{ width: `${(d.neutral / tot) * 100}%` }} title={`no clear call ${d.neutral}`} />
        </div>
      )}
      <p className="leading-relaxed">{ins.summary}</p>
      {chips('markets', ins.instruments)}
      {chips('planets', ins.planets)}
      {chips('themes', ins.themes)}
      {chips('months', ins.months)}
    </div>
  );
}

const ago = (iso: string) => {
  const d = (Date.now() - new Date(iso).getTime()) / 86400000;
  return d < 1 ? 'today' : `${Math.floor(d)}d ago`;
};

export function AstrologerSignalsCard({ symbol, symbolName }: { symbol: string; symbolName?: string }) {
  const [handles, setHandles] = useState<string[]>(DEFAULT_HANDLES);
  const [calls, setCalls] = useState<LoggedCall[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const [newHandle, setNewHandle] = useState('');
  const [res, setRes] = useState<{ key: string; data?: AstrologerFeed; err?: string } | null>(null);
  const [scored, setScored] = useState<ScoredCall[] | null>(null);
  const [disc, setDisc] = useState<{ key: string; data?: Discover; err?: string } | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [form, setForm] = useState({ source: 'Prashant Kapoor', direction: 'bullish' as Direction, start: '', end: '', note: '' });

  // localStorage is read after mount so server and client render the same first frame
  useEffect(() => {
    const h = load<string[]>(LS_SOURCES, DEFAULT_HANDLES);
    const c = load<LoggedCall[]>(LS_CALLS, []);
    queueMicrotask(() => {
      setHandles(h.length ? h : DEFAULT_HANDLES);
      setCalls(c);
      setHydrated(true);
    });
  }, []);

  const key = `${handles.join(',')}|${symbol}`;
  useEffect(() => {
    if (!hydrated) return;
    let live = true;
    astrologersApi
      .feed(handles, symbol)
      .then((data) => live && setRes({ key, data }))
      .catch((e) => live && setRes({ key, err: String(e?.message ?? e) }));
    return () => {
      live = false;
    };
  }, [handles, symbol, key, hydrated]);

  useEffect(() => {
    let live = true;
    astrologersApi
      .discover(symbol)
      .then((data) => live && setDisc({ key: symbol, data }))
      .catch((e) => live && setDisc({ key: symbol, err: String(e?.message ?? e) }));
    return () => {
      live = false;
    };
  }, [symbol]);

  useEffect(() => {
    if (!hydrated || calls.length === 0) return;
    let live = true;
    astrologersApi
      .score(calls)
      .then((r) => live && setScored(r.calls))
      .catch(() => live && setScored(null));
    return () => {
      live = false;
    };
  }, [calls, hydrated]);

  const data = res?.key === key ? res.data : undefined;
  const err = res?.key === key ? res.err : undefined;

  const updateHandles = (h: string[]) => {
    setHandles(h);
    save(LS_SOURCES, h);
  };
  const updateCalls = (c: LoggedCall[]) => {
    setCalls(c);
    save(LS_CALLS, c);
    if (c.length === 0) setScored(null);
  };
  const addHandle = () => {
    const h = newHandle.trim();
    if (!h) return;
    const norm = h.startsWith('@') || h.startsWith('http') ? h : `@${h}`;
    if (!handles.includes(norm)) updateHandles([...handles, norm].slice(0, 6));
    setNewHandle('');
  };
  const addCall = () => {
    if (!form.start) return;
    updateCalls([
      ...calls,
      { id: `${Date.now()}`, source: form.source || 'unknown', symbol, direction: form.direction, start: form.start, end: form.end || form.start, note: form.note },
    ]);
    setForm({ ...form, note: '' });
  };

  const cons = data?.consensus;
  const dd = disc?.key === symbol ? disc.data : undefined;
  const derr = disc?.key === symbol ? disc.err : undefined;
  return (
    <Card className="border-[#ecdec2] bg-[#fffdf6]/90 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="font-display flex items-center gap-2 text-base text-[#5c4327]">
          <Radio className="h-4 w-4 text-[#c98a2e]" /> Astrologer Signals
        </CardTitle>
        <CardDescription className="text-xs text-[#97795a]">
          Public market calls from financial astrologers&apos; YouTube channels (Prashant Kapoor by default), each linked to its
          source, tagged bullish / bearish / volatile, and checked against what the market actually did next.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* sources */}
        <div className="flex flex-wrap items-center gap-1.5">
          {handles.map((h) => (
            <span key={h} className="flex items-center gap-1 rounded-full border border-[#ecdec2] bg-[#fdf8ec] px-2 py-0.5 text-xs text-[#7c5a2e]">
              <Youtube className="h-3.5 w-3.5 text-[#c9553f]" />
              <a href={h.startsWith('http') ? h : `https://www.youtube.com/${h}`} target="_blank" rel="noreferrer" className="hover:underline">
                {h}
              </a>
              {handles.length > 1 && (
                <button aria-label={`Remove ${h}`} onClick={() => updateHandles(handles.filter((x) => x !== h))} className="text-[#b39a76] hover:text-[#a14d3c]">
                  ×
                </button>
              )}
            </span>
          ))}
          <input
            value={newHandle}
            onChange={(e) => setNewHandle(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addHandle()}
            placeholder="add a channel, e.g. @handle"
            className="w-44 rounded-md border border-[#ecdec2] bg-[#fffdf6] px-2 py-1 text-xs"
          />
          <button onClick={addHandle} className="flex items-center gap-1 rounded-md border border-[#ecdec2] px-2 py-1 text-xs text-[#7c5a2e] hover:border-[#d9b46a]">
            <Plus className="h-3.5 w-3.5" /> Track
          </button>
        </div>

        {err && <p className="rounded-md bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">Signals unavailable: {err}</p>}
        {!data && !err && <Skeleton className="h-40 w-full bg-[#f3e6cc]" />}

        {data && cons && (
          <div className="rounded-md border border-[#eed9b4] bg-gradient-to-r from-[#fdf3dc] to-[#fbead0] px-3 py-2">
            <p className="mb-1 flex flex-wrap items-center gap-2 text-xs font-semibold text-[#7c4a12]">
              <Lightbulb className="h-3.5 w-3.5" /> Astrologer consensus for {symbolName ?? symbol}: {cons.lean}
              {cons.calls.length > 0 && <span className="font-mono font-normal">(net {cons.net >= 0 ? '+' : ''}{cons.net.toFixed(2)})</span>}
            </p>
            <p className="text-xs leading-relaxed text-[#6b4f2e]">
              {cons.calls.length === 0
                ? `None of the tracked channels has posted a clear call on ${symbolName ?? symbol} in the last ${cons.window_days} days. Pick an index they cover (Nifty, Bank Nifty, gold) to see one.`
                : `Based on ${cons.calls.length} recent video${cons.calls.length > 1 ? 's' : ''} (newer ones count more). Treat this as one more opinion alongside the quant and cycle panels, and check the track record below before giving it any weight.`}
            </p>
          </div>
        )}

        {data?.insights && data.insights.count > 0 && <InsightsBox ins={data.insights} title="Detailed insights from the channels you track" />}

        {data?.sources.map((s) => (
          <div key={s.handle} className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <a href={s.url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-sm font-medium text-[#5c4327] hover:underline">
                {s.channel_title || s.name} <ExternalLink className="h-3 w-3" />
              </a>
              {s.track_record && (
                <span className="text-[11px] text-[#7c5a2e]">
                  Track record ({s.track_record.horizon_days}-day): {s.track_record.graded ? (
                    <>
                      <b>{s.track_record.hits}/{s.track_record.graded}</b> right ({s.track_record.hit_rate}%) vs {s.track_record.expected_by_chance}% by chance ·{' '}
                    </>
                  ) : null}
                  <i>{s.track_record.verdict}</i>
                </span>
              )}
            </div>
            {!s.ok && <p className="text-xs text-[#a14d3c]">{s.error}</p>}
            {s.ok && (
              <ul className="space-y-1">
                {(s.videos ?? []).slice(0, 10).map((v) => (
                  <li key={v.video_id} className="flex items-start gap-2 rounded-md border border-[#f0e4cc] bg-[#fdf8ec]/80 px-2.5 py-1.5 text-xs">
                    <div className="min-w-0 flex-1">
                      <a href={v.url} target="_blank" rel="noreferrer" className="font-medium text-[#5c4327] hover:underline">
                        {v.title}
                      </a>
                      <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[10.5px] text-[#97795a]">
                        <span>{ago(v.published)}</span>
                        <Pill d={v.direction} />
                        {v.instruments.map((i) => (
                          <span key={i.symbol} className="rounded bg-[#f4ecdd] px-1.5 py-px">
                            {i.label}
                            {i.inferred ? ' (inferred)' : ''}
                          </span>
                        ))}
                        {v.status === 'graded' && (
                          <span className={v.hit ? 'text-[#4f7a3f]' : v.hit === false ? 'text-[#a14d3c]' : ''}>
                            next {data.horizon_days}d {v.ret_pct! >= 0 ? '+' : ''}
                            {v.ret_pct}% {v.hit ? '✓' : v.hit === false ? '✗' : ''}
                          </span>
                        )}
                        {v.status === 'pending' && <span>too recent to grade</span>}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}

        {/* discovery across YouTube search + Reddit */}
        <div className="space-y-2">
          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-[#97795a]">
            <Globe className="h-3.5 w-3.5" /> Recent predictions across YouTube &amp; Reddit
          </p>
          {derr && <p className="text-xs text-[#a14d3c]">Discovery unavailable: {derr}</p>}
          {!dd && !derr && <Skeleton className="h-24 w-full bg-[#f3e6cc]" />}
          {dd && (
            <>
              {dd.insights.count > 0 && <InsightsBox ins={dd.insights} title={`What ${dd.items.length} recent predictions are saying`} />}
              <ul className="space-y-1">
                {dd.items.slice(0, showAll ? 40 : 8).map((v) => (
                  <li key={v.url} className="rounded-md border border-[#f0e4cc] bg-[#fdf8ec]/80 px-2.5 py-1.5 text-xs">
                    <a href={v.url} target="_blank" rel="noreferrer" className="font-medium text-[#5c4327] hover:underline">
                      {v.title}
                    </a>
                    <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[10.5px] text-[#97795a]">
                      <span className="rounded bg-[#fbe7e0] px-1.5 py-px text-[#a14d3c]">{v.platform}</span>
                      {v.channel_url ? (
                        <a href={v.channel_url} target="_blank" rel="noreferrer" className="hover:underline">
                          {v.channel}
                        </a>
                      ) : (
                        <span>{v.channel}</span>
                      )}
                      <span>{v.published_text || (v.published ? ago(v.published) : '')}</span>
                      <Pill d={v.direction} />
                      {v.instruments.map((i) => (
                        <span key={i.symbol} className="rounded bg-[#f4ecdd] px-1.5 py-px">
                          {i.label}
                        </span>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
              {dd.items.length > 8 && (
                <button onClick={() => setShowAll(!showAll)} className="text-xs text-[#7c5a2e] underline">
                  {showAll ? 'show fewer' : `show all ${dd.items.length}`}
                </button>
              )}
              {dd.items.length === 0 && <p className="text-xs text-[#97795a]">Nothing found right now{dd.errors.length ? ` (${dd.errors.join('; ')})` : ''}.</p>}
              <p className="text-[10.5px] text-[#b39a76]">
                Searched: {dd.sources_searched.join(' · ')}. {dd.note}
              </p>
            </>
          )}
        </div>

        {/* user-logged calls */}
        <div className="rounded-md border border-[#f0e4cc] bg-[#fffdf6] px-3 py-2">
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-[#97795a]">Log a call you heard ({symbolName ?? symbol})</p>
          <div className="flex flex-wrap items-end gap-1.5 text-xs">
            <input value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} placeholder="astrologer" className="w-36 rounded-md border border-[#ecdec2] px-2 py-1" />
            <select value={form.direction} onChange={(e) => setForm({ ...form, direction: e.target.value as Direction })} className="rounded-md border border-[#ecdec2] px-2 py-1">
              <option value="bullish">bullish</option>
              <option value="bearish">bearish</option>
              <option value="volatile">big move</option>
            </select>
            <label className="flex items-center gap-1">from <input type="date" value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} className="rounded-md border border-[#ecdec2] px-1 py-0.5" /></label>
            <label className="flex items-center gap-1">to <input type="date" value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} className="rounded-md border border-[#ecdec2] px-1 py-0.5" /></label>
            <input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="note or video link" className="min-w-0 flex-1 rounded-md border border-[#ecdec2] px-2 py-1" />
            <button onClick={addCall} disabled={!form.start} className="rounded-md border border-[#d9b46a] bg-[#fbe3bd] px-2 py-1 text-[#7c4a12] disabled:opacity-50">
              Add
            </button>
          </div>
          {calls.length > 0 && (
            <ul className="mt-2 space-y-1">
              {calls.map((c) => {
                const s = scored?.find((x) => x.id === c.id);
                return (
                  <li key={c.id} className="flex flex-wrap items-center gap-2 text-xs text-[#5c4327]">
                    <span className="font-medium">{c.source}</span>
                    <Pill d={c.direction} />
                    <span className="font-mono text-[#97795a]">
                      {c.symbol} · {c.start} → {c.end}
                    </span>
                    {s?.status === 'graded' ? (
                      <span className={s.hit ? 'text-[#4f7a3f]' : 'text-[#a14d3c]'}>
                        {s.ret_pct! >= 0 ? '+' : ''}
                        {s.ret_pct}% {s.hit ? '✓ right' : '✗ wrong'}
                      </span>
                    ) : (
                      <span className="text-[#97795a]">{s?.status ?? 'checking…'}</span>
                    )}
                    {c.note && <span className="truncate text-[#97795a]">“{c.note}”</span>}
                    <button aria-label="Delete call" onClick={() => updateCalls(calls.filter((x) => x.id !== c.id))} className="ml-auto text-[#b39a76] hover:text-[#a14d3c]">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          <p className="mt-1.5 text-[10.5px] text-[#b39a76]">Saved in this browser only.</p>
        </div>

        {data && (
          <p className="text-[11px] leading-relaxed text-[#97795a]">
            <b>How this works:</b> {data.method} {data.disclaimer}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
