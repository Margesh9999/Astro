'use client';

import { useCallback, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { labApi } from '@/lib/astro/api';
import type { IncomePlanResponse } from '@/lib/astro/types';
import { Loader2, PiggyBank } from 'lucide-react';

function gbp(n: number | null | undefined, d = 0): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return '—';
  return `£${n.toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d })}`;
}

const VERDICT_META: Record<string, { label: string; cls: string; note: string }> = {
  achievable: {
    label: 'Target achievable',
    cls: 'border-[#8fc4ae] bg-[#e8f4ee] text-[#3f8a6e]',
    note: 'This capital base can credibly target the requested weekly income at base yields — with full drawdown discipline.',
  },
  stretch: {
    label: 'Stretch — aggressive end required',
    cls: 'border-[#d9a441] bg-[#fdf3dc] text-[#8a6a3a]',
    note: 'The base regime falls short of the target. You would need the aggressive end of the yield ranges (higher risk of drawdowns) or a larger capital base.',
  },
  below_base_regime: {
    label: 'Not realistically achievable at this size',
    cls: 'border-[#eecfc7] bg-[#fbeae4] text-[#a14d3c]',
    note: 'Chasing the target at this capital would require unsafe leverage. See the max sustainable figure instead.',
  },
};

export function LabIncomeTab() {
  const [capital, setCapital] = useState(100000);
  const [target, setTarget] = useState(500);
  const [focus, setFocus] = useState('uk');
  const [plan, setPlan] = useState<IncomePlanResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = useCallback(async () => {
    setBusy(true);
    setErr(null);
    try {
      const p = await labApi.incomePlan({ capital, target_weekly: target, focus });
      setPlan(p);
    } catch (e) {
      setErr(String(e?.message ?? e));
    } finally {
      setBusy(false);
    }
  }, [capital, target, focus]);

  const vm = plan ? VERDICT_META[plan.verdict] : null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <label>
          <span className="text-[10px] uppercase tracking-wide text-[#b39a76]">Capital (GBP)</span>
          <Input
            type="number"
            min={1000}
            step={1000}
            value={capital}
            onChange={(e) => setCapital(Math.max(0, parseFloat(e.target.value || '0')))}
            className="h-8 w-32 border-[#ecdec2] bg-[#fffdf6] px-2 font-mono text-xs"
          />
        </label>
        <div className="flex gap-1 pb-0.5">
          {[25000, 50000, 100000, 250000].map((c) => (
            <button
              key={c}
              onClick={() => setCapital(c)}
              className={`rounded-full border px-2 py-0.5 text-[10px] ${
                capital === c
                  ? 'border-[#d9a441] bg-[#fdf3dc] font-semibold text-[#8a6a3a]'
                  : 'border-[#ecdec2] bg-[#fffdf6] text-[#97795a] hover:bg-[#fdf8ec]'
              }`}
            >
              £{c / 1000}k
            </button>
          ))}
        </div>
        <label>
          <span className="text-[10px] uppercase tracking-wide text-[#b39a76]">Target / week</span>
          <Input
            type="number"
            min={0}
            step={50}
            value={target}
            onChange={(e) => setTarget(Math.max(0, parseFloat(e.target.value || '0')))}
            className="h-8 w-24 border-[#ecdec2] bg-[#fffdf6] px-2 font-mono text-xs"
          />
        </label>
        <label>
          <span className="text-[10px] uppercase tracking-wide text-[#b39a76]">Focus</span>
          <select
            value={focus}
            onChange={(e) => setFocus(e.target.value)}
            className="h-8 rounded-md border border-[#ecdec2] bg-[#fffdf6] px-2 text-xs text-[#5c4327]"
          >
            <option value="uk">🇬🇧 UK / Global</option>
            <option value="us">🇺🇸 US</option>
            <option value="india">🇮🇳 India (Nifty weekly)</option>
          </select>
        </label>
        <Button
          onClick={run}
          disabled={busy}
          className="h-8 border border-[#d9a441]/50 bg-gradient-to-r from-[#fdf3dc] to-[#fbead0] px-4 font-display text-xs tracking-wide text-[#8a6a3a] hover:from-[#fbead0] hover:to-[#f6dcb4]"
        >
          {busy ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <PiggyBank className="mr-1 h-3.5 w-3.5" />}
          Plan my income
        </Button>
      </div>

      {err && (
        <p className="rounded border border-[#eecfc7] bg-[#fbeae4] px-2 py-1.5 text-[11px] text-[#a14d3c]">{err}</p>
      )}

      {busy && !plan && <Skeleton className="h-40 w-full bg-[#efdfbc]" />}

      {plan && vm && (
        <div className="space-y-3">
          {/* verdict + headline numbers */}
          <div className={`rounded-lg border px-3 py-2 ${vm.cls}`}>
            <p className="text-xs font-semibold">
              {vm.label} — {gbp(plan.inputs.capital)} targeting {gbp(plan.inputs.target_weekly)}/week (
              {gbp(plan.annual_target)}/yr)
            </p>
            <p className="mt-0.5 text-[11px] opacity-90">{vm.note}</p>
          </div>

          <div className="grid grid-cols-2 gap-2 lg:grid-cols-5">
            {(
              [
                ['Base capital needed', gbp(plan.required_capital_total_base)],
                ['Plan yield / week', gbp(plan.est_weekly_from_ladder_yields)],
                ['Max sustainable / wk', gbp(plan.max_sustainable_weekly)],
                ['Gross premium capture', gbp(plan.gross_premium_capture_weekly_gbp)],
                ['FX used', `£1 = $${plan.inputs.gbpusd.toFixed(3)}`],
              ] as Array<[string, string]>
            ).map(([label, v]) => (
              <div key={label} className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6] px-2 py-1.5">
                <p className="text-[9px] uppercase tracking-wide text-[#b39a76]">{label}</p>
                <p className="font-mono text-xs font-semibold text-[#5c4327]">{v}</p>
              </div>
            ))}
          </div>

          {/* capital requirements table */}
          <div className="overflow-hidden rounded-lg border border-[#f0e4cc]">
            <table className="w-full text-[11px]">
              <thead className="bg-[#fdf8ec] text-[9px] uppercase tracking-wide text-[#b39a76]">
                <tr>
                  <th className="px-2 py-1 text-left font-medium">Programme</th>
                  <th className="px-2 py-1 text-left font-medium">Yield range (managed)</th>
                  <th className="px-2 py-1 text-right font-medium">Capital @ base</th>
                  <th className="px-2 py-1 text-right font-medium">Conservative</th>
                  <th className="px-2 py-1 text-right font-medium">Aggressive</th>
                </tr>
              </thead>
              <tbody>
                {plan.capital_table.map((t) => (
                  <tr key={t.key} className="border-t border-[#f7ecd4]">
                    <td className="px-2 py-1">
                      <p className="font-medium text-[#5c4327]">{t.label}</p>
                      <p className="text-[9px] text-[#b39a76]">
                        {t.dte} DTE · {t.basis.replace(/_/g, ' ')} · {t.risk}
                      </p>
                    </td>
                    <td className="px-2 py-1 font-mono text-[#97795a]">
                      {(t.yield_range.conservative * 100).toFixed(0)}–{(t.yield_range.aggressive * 100).toFixed(0)}%
                    </td>
                    <td className="px-2 py-1 text-right font-mono font-semibold text-[#5c4327]">
                      {gbp(t.capital_required.base)}
                    </td>
                    <td className="px-2 py-1 text-right font-mono text-[#3f8a6e]">{gbp(t.capital_required.conservative)}</td>
                    <td className="px-2 py-1 text-right font-mono text-[#c9553f]">{gbp(t.capital_required.aggressive)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* ladder tickets */}
          <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
            {plan.ladder.map((b) => (
              <div key={b.key} className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6] p-2.5">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold text-[#5c4327]">
                    {(b.weight * 100).toFixed(0)}% · {b.label}
                  </p>
                  <Badge variant="outline" className="h-4 px-1 text-[9px] text-[#8a6a3a]">
                    {gbp(b.target_weekly)}/wk target
                  </Badge>
                </div>
                {b.ticket ? (
                  <div className="mt-1.5 space-y-1">
                    <p className="text-[11px] text-[#97795a]">
                      <span className="font-mono font-semibold text-[#4a3525]">{b.ticket.underlying}</span>{' '}
                      {b.ticket.strategy_name} · {b.ticket.expiry} ({b.ticket.dte.toFixed(0)}d) · qty{' '}
                      <span className="font-mono font-semibold">{b.ticket.qty}</span>
                      {!b.ticket.fits_allocation && (
                        <span className="ml-1 text-[#c9553f]">(1 unit min — bucket too small)</span>
                      )}
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {b.ticket.legs.map((l, i) => (
                        <span
                          key={i}
                          className={`rounded px-1.5 py-0.5 font-mono text-[9px] ${
                            l.action === 'buy' ? 'bg-[#e8f4ee] text-[#3f8a6e]' : 'bg-[#fbeae4] text-[#c9553f]'
                          }`}
                        >
                          {l.action} {l.cp} {l.cp === 'stock' ? '' : l.strike}
                        </span>
                      ))}
                    </div>
                    <p className="font-mono text-[10px] text-[#97795a]">
                      credit {b.ticket.credit_per_unit.toLocaleString()} {b.ticket.currency}/u · margin{' '}
                      {b.ticket.margin_per_unit.toLocaleString()}/u · POP {(b.ticket.pop * 100).toFixed(0)}% ·
                      max loss {b.ticket.max_loss === null ? '∞' : b.ticket.max_loss.toLocaleString()}
                    </p>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#f0e4cc]">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-[#8fc4ae] to-[#3f8a6e]"
                        style={{ width: `${Math.min(100, b.ticket.pop * 100)}%` }}
                      />
                    </div>
                    <p className="text-[9px] text-[#b39a76]">
                      {b.ticket.chain_source === 'live' ? '● live chain' : '◈ modelled'} · {b.ticket.note}
                    </p>
                  </div>
                ) : (
                  <p className="mt-1.5 text-[11px] text-[#c9553f]">No chain available for this bucket.</p>
                )}
              </div>
            ))}
          </div>

          {/* honest notes */}
          <div className="rounded-lg border border-[#eed9b4] bg-gradient-to-r from-[#fdf3dc] to-[#fbead0] px-3 py-2">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-[#8a6a3a]">
              Read this before trading
            </p>
            <ul className="list-disc space-y-0.5 pl-4 text-[10px] leading-relaxed text-[#8a6a3a]">
              {plan.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
            <p className="mt-1 text-[9px] italic text-[#b39a76]">{plan.disclaimer}</p>
          </div>
        </div>
      )}

      {!plan && !busy && (
        <p className="py-4 text-center text-xs text-[#97795a]">
          Set your capital and weekly target, then run the planner — it prices a real ladder of tickets from live
          option chains and tells you honestly whether the target is reachable.
        </p>
      )}
    </div>
  );
}
