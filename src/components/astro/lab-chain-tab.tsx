'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { labApi } from '@/lib/astro/api';
import type { OptionChainResponse, OptionExpirationsResponse } from '@/lib/astro/types';

function fmt(n: number | undefined | null, d = 2): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return '—';
  return n.toFixed(d);
}

export function LabChainTab({ symbol, exp }: { symbol: string; exp: OptionExpirationsResponse }) {
  const [expiry, setExpiry] = useState<string>('');
  const [chain, setChain] = useState<OptionChainResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // pick the expiry closest to ~35 DTE by default (async callback pattern)
  useEffect(() => {
    if (!exp.expirations.length) return;
    const dtes = exp.dte;
    let best = 0;
    let bestDiff = Infinity;
    exp.expirations.forEach((_, i) => {
      const diff = Math.abs((dtes[i] ?? 35) - 35);
      if (diff < bestDiff) {
        bestDiff = diff;
        best = i;
      }
    });
    setExpiry(exp.expirations[best]);
  }, [exp]);

  const load = useCallback(async (sym: string, exp_date: string) => {
    setBusy(true);
    setErr(null);
    try {
      const c = await labApi.chain(sym, exp_date);
      setChain(c);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (expiry) load(symbol, expiry);
  }, [symbol, expiry, load]);

  // center the view on ATM: keep ~14 strikes on each side
  const visible = useMemo(() => {
    if (!chain) return [];
    const rows = [...chain.rows].sort((a, b) => a.strike - b.strike);
    let atmIdx = rows.findIndex((r) => r.strike >= chain.spot);
    if (atmIdx < 0) atmIdx = rows.length - 1;
    const start = Math.max(0, atmIdx - 12);
    return rows.slice(start, start + 25);
  }, [chain]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={expiry}
          onChange={(e) => setExpiry(e.target.value)}
          className="h-8 rounded-md border border-[#ecdec2] bg-[#fffdf6] px-2 font-mono text-xs text-[#5c4327]"
        >
          {exp.expirations.map((e, i) => (
            <option key={e} value={e}>
              {e} {exp.dte[i] !== null ? `· ${Math.round(exp.dte[i] ?? 0)}d` : ''}
            </option>
          ))}
        </select>
        {chain && (
          <Badge
            variant="outline"
            className={`h-5 px-1.5 text-[10px] ${
              chain.source === 'live'
                ? 'border-[#8fc4ae] bg-[#e8f4ee] text-[#3f8a6e]'
                : 'border-[#c9a3c4] bg-[#f6e9f0] text-[#8a4a62]'
            }`}
          >
            {chain.source === 'live' ? '● live Yahoo chain' : '◈ synthetic SABR model'}
          </Badge>
        )}
        {chain && (
          <span className="text-[11px] text-[#97795a]">
            spot <span className="font-mono font-semibold text-[#5c4327]">{fmt(chain.spot)}</span> · ATM vol{' '}
            <span className="font-mono font-semibold text-[#5c4327]">{(chain.atm_vol * 100).toFixed(1)}%</span> ·{' '}
            {chain.dte.toFixed(0)} DTE · r {(chain.risk_free * 100).toFixed(1)}%
          </span>
        )}
      </div>

      {err && (
        <p className="rounded border border-[#eecfc7] bg-[#fbeae4] px-2 py-1.5 text-[11px] text-[#a14d3c]">{err}</p>
      )}

      {busy && !chain && <p className="py-4 text-center text-xs text-[#97795a]">Loading chain…</p>}

      {chain && (
        <div className="warm-scroll max-h-[420px] overflow-auto rounded-lg border border-[#f0e4cc]">
          <table className="w-full min-w-[760px] border-collapse text-[11px]">
            <thead className="sticky top-0 bg-[#fdf8ec] text-[9px] uppercase tracking-wide text-[#b39a76]">
              <tr>
                <th colSpan={5} className="border-b border-[#f0e4cc] px-2 py-1 text-center text-[#3f8a6e]">
                  Calls
                </th>
                <th className="border-b border-[#f0e4cc] px-2 py-1 text-center font-display text-[10px] text-[#8a6a3a]">
                  Strike
                </th>
                <th colSpan={5} className="border-b border-[#f0e4cc] px-2 py-1 text-center text-[#c9553f]">
                  Puts
                </th>
              </tr>
              <tr>
                {['Bid/Ask', 'Mid', 'IV', 'Δ', 'OI', ''].map((h, i) => (
                  <th key={`c${i}`} className="px-2 py-1 font-medium">
                    {h}
                  </th>
                ))}
                {['OI', 'Δ', 'IV', 'Mid', 'Bid/Ask'].map((h, i) => (
                  <th key={`p${i}`} className="px-2 py-1 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="font-mono">
              {visible.map((r) => {
                const isAtm = Math.abs(r.strike - chain.spot) <= Math.min(7.5, chain.spot * 0.008);
                return (
                  <tr
                    key={r.strike}
                    className={`border-b border-[#f7ecd4] text-center ${
                      isAtm ? 'bg-[#fdf3dc]/70 font-semibold' : 'odd:bg-[#fffdf6]'
                    }`}
                  >
                    <td className="px-2 py-1 text-[#5c4327]">
                      {fmt(r.call.bid)}/{fmt(r.call.ask)}
                    </td>
                    <td className="px-2 py-1 text-[#5c4327]">{fmt(r.call.mid)}</td>
                    <td className="px-2 py-1 text-[#97795a]">{(r.call.iv * 100).toFixed(1)}%</td>
                    <td className="px-2 py-1 text-[#3f8a6e]">{r.call.delta.toFixed(2)}</td>
                    <td className="px-2 py-1 text-[#b39a76]">{r.call.open_interest || '—'}</td>
                    <td
                      className={`px-2 py-1 font-semibold ${isAtm ? 'text-[#8a6a3a]' : 'text-[#4a3525]'}`}
                    >
                      {r.strike}
                    </td>
                    <td className="px-2 py-1 text-[#b39a76]">{r.put.open_interest || '—'}</td>
                    <td className="px-2 py-1 text-[#c9553f]">{r.put.delta.toFixed(2)}</td>
                    <td className="px-2 py-1 text-[#97795a]">{(r.put.iv * 100).toFixed(1)}%</td>
                    <td className="px-2 py-1 text-[#5c4327]">{fmt(r.put.mid)}</td>
                    <td className="px-2 py-1 text-[#5c4327]">
                      {fmt(r.put.bid)}/{fmt(r.put.ask)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {chain && <p className="text-[10px] leading-relaxed text-[#b39a76]">{chain.disclaimer}</p>}
    </div>
  );
}
