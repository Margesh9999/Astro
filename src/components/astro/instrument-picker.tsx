'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Input } from '@/components/ui/input';
import { Loader2, Search, TrendingUp, X } from 'lucide-react';
import { labApi } from '@/lib/astro/api';
import type { UniverseEntry, UniverseMeta } from '@/lib/astro/types';

/**
 * Searchable instrument picker — curated universe across US / UK / India /
 * Europe / Japan / Crypto / FX with equity, ETF, index, mutual-fund, crypto
 * and currency classes. Falls back to a custom Yahoo symbol when nothing
 * matches (the backend accepts any valid symbol).
 */
export function InstrumentPicker({
  value,
  onSelect,
  compact = false,
}: {
  value: string;
  onSelect: (entry: { symbol: string; name: string }) => void;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [market, setMarket] = useState('');
  const [type, setType] = useState('');
  const [optionsOnly, setOptionsOnly] = useState(false);
  const [rows, setRows] = useState<UniverseEntry[]>([]);
  const [meta, setMeta] = useState<UniverseMeta | null>(null);
  const [busy, setBusy] = useState(false);
  const seqRef = useRef(0);

  useEffect(() => {
    labApi.universeMeta().then((r) => setMeta(r.meta)).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!open) return;
    const seq = ++seqRef.current;
    const t = setTimeout(() => {
      setBusy(true);
      labApi
        .universe({ q, market, type, options_only: optionsOnly || undefined, limit: 80 })
        .then((r) => {
          if (seq === seqRef.current) setRows(r.results);
        })
        .catch(() => undefined)
        .finally(() => {
          if (seq === seqRef.current) setBusy(false);
        });
    }, 160);
    return () => clearTimeout(t);
  }, [q, market, type, optionsOnly, open]);

  const pick = useCallback(
    (symbol: string, name: string) => {
      onSelect({ symbol, name });
      setOpen(false);
      setQ('');
    },
    [onSelect],
  );

  const exact = rows.some((r) => r.symbol.toLowerCase() === q.trim().toLowerCase());
  const showCustom = q.trim().length >= 1 && !exact;

  const chip = (active: boolean) =>
    `rounded-full border px-2 py-0.5 text-[10px] transition-colors ${
      active
        ? 'border-[#d9a441] bg-[#fdf3dc] font-semibold text-[#8a6a3a]'
        : 'border-[#ecdec2] bg-[#fffdf6] text-[#97795a] hover:bg-[#fdf8ec]'
    }`;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          className={`flex items-center gap-2 rounded-full border border-[#ecdec2] bg-[#fffdf6]/80 text-[#7c5a2e] transition-colors hover:border-[#d9b46a] ${
            compact ? 'px-2.5 py-1 text-[11px]' : 'px-3 py-1.5 text-xs'
          }`}
          aria-label="Search instruments"
        >
          <Search className="h-3.5 w-3.5 text-[#c98a2e]" />
          <span className="max-w-[190px] truncate font-medium">{value}</span>
          <TrendingUp className="h-3 w-3 text-[#b39a76]" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="w-[360px] border-[#ecdec2] bg-[#fffdf6] p-3 shadow-lg"
      >
        <div className="relative">
          <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#b39a76]" />
          <Input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && showCustom) pick(q.trim().toUpperCase(), 'Custom symbol');
              if (e.key === 'Enter' && rows.length) pick(rows[0].symbol, rows[0].name);
            }}
            placeholder="Search 350+ instruments or type any symbol…"
            className="h-8 border-[#ecdec2] bg-[#fffdf6] pl-7 pr-7 font-mono text-xs"
          />
          {busy ? (
            <Loader2 className="absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 animate-spin text-[#c98a2e]" />
          ) : (
            q && (
              <button
                onClick={() => setQ('')}
                aria-label="Clear search"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[#b39a76] hover:text-[#7c5a2e]"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )
          )}
        </div>

        {/* market filter */}
        <div className="mt-2 flex flex-wrap gap-1">
          <button className={chip(market === '')} onClick={() => setMarket('')}>
            All
          </button>
          {(meta?.markets ?? []).map((m) => (
            <button key={m.market} className={chip(market === m.market)} onClick={() => setMarket(market === m.market ? '' : m.market)}>
              <span className="mr-0.5">{m.flag}</span>
              {m.label}
            </button>
          ))}
        </div>

        {/* type filter */}
        <div className="mt-1.5 flex flex-wrap gap-1">
          <button className={chip(type === '')} onClick={() => setType('')}>
            All types
          </button>
          {(meta?.types ?? []).map((t) => (
            <button key={t.type} className={chip(type === t.type)} onClick={() => setType(type === t.type ? '' : t.type)}>
              {t.label}s
            </button>
          ))}
          <button
            className={chip(optionsOnly)}
            onClick={() => setOptionsOnly(!optionsOnly)}
            title="Only instruments with listed options (usable in the Options Lab)"
          >
            ⚡ Options
          </button>
        </div>

        {/* results */}
        <div className="warm-scroll mt-2 max-h-64 space-y-0.5 overflow-y-auto pr-1">
          {showCustom && (
            <button
              onClick={() => pick(q.trim().toUpperCase(), 'Custom symbol')}
              className="w-full rounded-md border border-dashed border-[#d9b46a] bg-[#fdf8ec] px-2 py-1.5 text-left text-[11px] text-[#8a6a3a] hover:bg-[#fbead0]"
            >
              Use <span className="font-mono font-semibold">{q.trim().toUpperCase()}</span> as a custom symbol
            </button>
          )}
          {!busy && !rows.length && !showCustom && (
            <p className="px-2 py-3 text-center text-[11px] text-[#b39a76]">No instruments match.</p>
          )}
          {rows.map((r) => (
            <button
              key={r.symbol}
              onClick={() => pick(r.symbol, r.name)}
              className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-[#fdf3dc] ${
                r.symbol === value ? 'bg-[#fbead0]' : ''
              }`}
            >
              <span className="w-6 text-center text-sm">{r.flag}</span>
              <span className="w-28 shrink-0 truncate font-mono text-[11px] font-semibold text-[#4a3525]">
                {r.symbol}
              </span>
              <span className="flex-1 truncate text-[11px] text-[#97795a]">{r.name}</span>
              <span className="rounded bg-[#f7ecd4] px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-[#97795a]">
                {r.type_label}
              </span>
              {r.has_options && (
                <span
                  className="rounded bg-[#e8f4ee] px-1.5 py-0.5 text-[9px] font-semibold text-[#3f8a6e]"
                  title="Listed options available — full Options Lab support"
                >
                  ⚡
                </span>
              )}
            </button>
          ))}
        </div>
        {meta && (
          <p className="mt-2 border-t border-[#f0e4cc] pt-1.5 text-[10px] text-[#b39a76]">
            {meta.total} instruments · {meta.options_enabled} with listed options · any other Yahoo symbol works via custom entry
          </p>
        )}
      </PopoverContent>
    </Popover>
  );
}
