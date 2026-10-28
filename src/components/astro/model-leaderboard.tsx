'use client';

import { Fragment, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { ZooRow } from '@/lib/astro/api-models';

const pct = (v: number | null | undefined, nd = 1) => (v == null ? '—' : `${(v * 100).toFixed(nd)}%`);

/** Leaderboard of every regression / time-series / ensemble model, filterable by family. */
export function ModelLeaderboard({ rows, families, bestKey }: { rows: ZooRow[]; families: string[]; bestKey: string | null }) {
  const [family, setFamily] = useState<string>('All');
  const [open, setOpen] = useState<string | null>(null);
  const fams = useMemo(
    () => ['All', ...families.filter((f) => f !== 'Direction classifiers' && rows.some((r) => r.family === f))],
    [families, rows],
  );
  const shown = rows.filter((r) => family === 'All' || r.family === family);
  const ranks = new Map<string, number>();
  shown.filter((r) => r.status === 'ok').forEach((r, i) => ranks.set(r.key, i + 1));

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-1">
        {fams.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFamily(f)}
            className={`rounded-full border px-2 py-0.5 text-[10px] transition ${
              family === f
                ? 'border-[#dcc08a] bg-[#f6d194] text-[#7c4a12]'
                : 'border-[#f0e4cc] bg-[#fffdf6] text-[#97795a] hover:bg-[#fdf3dc]'
            }`}
          >
            {f}
            {f !== 'All' && <span className="ml-1 text-[#b39a76]">{rows.filter((r) => r.family === f).length}</span>}
          </button>
        ))}
      </div>
      <div className="warm-scroll max-h-[420px] overflow-auto rounded-md border border-[#f0e4cc]">
        <table className="w-full min-w-[340px] text-[11px]">
          <thead className="sticky top-0 bg-[#f9efd8] text-[10px] uppercase tracking-wide text-[#97795a]">
            <tr>
              <th className="px-2 py-1.5 text-left">#</th>
              <th className="px-2 py-1.5 text-left">Model</th>
              <th className="hidden px-2 py-1.5 text-left sm:table-cell">Family</th>
              <th className="px-2 py-1.5 text-right" title="Out-of-sample R² vs the historical-mean forecast">R² vs naive</th>
              <th className="px-2 py-1.5 text-right" title="Share of days the sign was right">Hit rate</th>
              <th className="px-2 py-1.5 text-right" title="Decade-long test blocks where it beat naive">Blocks</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => {
              const ok = r.status === 'ok';
              const isOpen = open === r.key;
              const r2 = r.r2_os ?? null;
              return (
                <Fragment key={r.key}>
                  <tr
                    onClick={() => setOpen(isOpen ? null : r.key)}
                    className={`cursor-pointer border-t border-[#f4ead4] ${
                      r.key === bestKey ? 'bg-[#e2f3e9]/60' : r.kind === 'naive' ? 'bg-[#f7f1e4]/70' : 'bg-[#fffdf6]/70'
                    } hover:bg-[#fdf3dc]`}
                  >
                    <td className="px-2 py-1 font-mono text-[#b39a76]">{ranks.get(r.key) ?? '–'}</td>
                    <td className="px-2 py-1 text-[#5c4327]">
                      <span className="flex items-center gap-1">
                        {isOpen ? <ChevronDown className="h-3 w-3 text-[#b39a76]" /> : <ChevronRight className="h-3 w-3 text-[#b39a76]" />}
                        <span className={r.key === bestKey ? 'font-semibold' : ''}>{r.name}</span>
                        {r.key === bestKey && <span className="rounded bg-[#a8d8bf] px-1 text-[9px] text-[#2f7357]">best</span>}
                        {r.kind === 'naive' && <span className="rounded bg-[#efe3c8] px-1 text-[9px] text-[#8a6a3a]">baseline</span>}
                      </span>
                    </td>
                    <td className="hidden px-2 py-1 text-[#97795a] sm:table-cell">{r.family}</td>
                    {ok ? (
                      <>
                        <td className={`px-2 py-1 text-right font-mono ${r2 != null && r2 > 0 ? 'text-[#2f7357]' : 'text-[#c9553f]'}`}>
                          {r2 == null ? '—' : `${(r2 * 100).toFixed(3)}%`}
                        </td>
                        <td className="px-2 py-1 text-right font-mono text-[#7c5a2e]">{pct(r.hit_rate)}</td>
                        <td className="px-2 py-1 text-right font-mono text-[#7c5a2e]">
                          {r.folds_beat != null ? `${r.folds_beat}/${r.n_folds}` : '—'}
                        </td>
                      </>
                    ) : (
                      <td colSpan={3} className="px-2 py-1 text-right text-[10px] italic text-[#b39a76]">
                        {r.status === 'skipped' ? 'skipped' : 'failed'}
                      </td>
                    )}
                  </tr>
                  {isOpen && (
                    <tr className="bg-[#fdf8ec]">
                      <td />
                      <td colSpan={5} className="px-2 pb-2 pt-0.5 text-[10px] leading-relaxed text-[#7c5a2e]">
                        <p className="text-[#97795a]">{r.desc}</p>
                        <p className="mt-0.5">{r.insight}</p>
                        <p className="mt-0.5 text-[#b39a76]">
                          {r.features_used ? `Inputs: ${r.features_used}. ` : ''}
                          {r.cap ? `Trained on the most recent ${r.cap.toLocaleString()} sessions per fold (speed cap). ` : ''}
                          {r.members ? `Members: ${r.members.join(', ')}. ` : ''}
                          {r.seconds != null ? `${r.seconds}s.` : ''}
                        </p>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-[10px] text-[#b39a76]">
        Click a row for what the model does and what its result means. R² vs naive &gt; 0 means it beat assuming the
        average return on data it never saw.
      </p>
    </div>
  );
}
