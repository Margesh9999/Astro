'use client';

import { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { enhanceApi } from '@/lib/astro/api';
import type { ConceptRepo } from '@/lib/astro/types';
import { Library, Search } from 'lucide-react';

const STATUS_STYLE: Record<string, { cls: string; label: string }> = {
  implemented: { cls: 'border-[#a8d8bf] bg-[#e2f3e9] text-[#2f7357]', label: 'implemented' },
  partial: { cls: 'border-[#dcc08a] bg-[#f9efd8] text-[#8a6a3a]', label: 'partial' },
  reference: { cls: 'border-[#cbb8dd] bg-[#efe7f8] text-[#6b4e93]', label: 'reference' },
};

export function ConceptsCard() {
  const [repos, setRepos] = useState<ConceptRepo[] | null>(null);
  const [summary, setSummary] = useState<{ repos: number; concepts: number; implemented: number; partial: number; reference: number; coverage_pct: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<'all' | 'implemented' | 'partial' | 'reference'>('all');

  useEffect(() => {
    enhanceApi
      .concepts()
      .then((r) => {
        setRepos(r.repos);
        setSummary(r.summary);
      })
      .catch((e) => setError(String(e?.message ?? e)));
  }, []);

  const filtered = useMemo(() => {
    if (!repos) return [];
    const q = query.trim().toLowerCase();
    return repos
      .map((r) => ({
        ...r,
        concepts: r.concepts.filter(
          (c) =>
            (filter === 'all' || c.status === filter) &&
            (!q ||
              r.repo.toLowerCase().includes(q) ||
              c.name.toLowerCase().includes(q) ||
              c.where.toLowerCase().includes(q) ||
              c.meaning.toLowerCase().includes(q)),
        ),
      }))
      .filter((r) => r.concepts.length > 0);
  }, [repos, query, filter]);

  return (
    <Card className="vedic-card">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Library className="h-4 w-4 text-[#c98a2e]" />
            <CardTitle className="font-display text-base tracking-wide">
              Open-Source Quant Library Coverage
            </CardTitle>
          </div>
          {summary && (
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant="outline" className="border-[#dcc08a] bg-[#f9efd8] text-[10px] text-[#8a6a3a]">
                {summary.repos} repos audited
              </Badge>
              <Badge variant="outline" className="border-[#a8d8bf] bg-[#e2f3e9] text-[10px] text-[#2f7357]">
                {summary.implemented + summary.partial}/{summary.concepts} concepts live ({summary.coverage_pct}%)
              </Badge>
            </div>
          )}
        </div>
        <CardDescription className="text-[#97795a]">
          Every concept from the 28 audited repositories — mapped to where it lives in AstroTrader, with its
          trading meaning. Nothing silently dropped: implemented, partial, or documented as reference-only.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#b39a76]" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search repo, concept, or location… (e.g. VaR, Heston, OpenBB)"
              className="h-8 border-[#ecdec2] bg-white pl-7 text-xs"
            />
          </div>
          <div className="flex gap-1">
            {(['all', 'implemented', 'partial', 'reference'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`rounded-full border px-2.5 py-1 text-[10px] font-medium capitalize transition ${
                  filter === f
                    ? 'border-[#d98324] bg-[#fbe3bd] text-[#7c4a12]'
                    : 'border-[#ecdec2] bg-[#fffdf6]/80 text-[#97795a] hover:border-[#d9b46a]'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {!repos && !error && (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full bg-[#efdfbc]" />
            ))}
          </div>
        )}
        {error && (
          <div className="rounded-md border border-[#eecfc7] bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">
            Coverage matrix unavailable — {error}
          </div>
        )}

        <div className="warm-scroll max-h-[420px] space-y-2 overflow-y-auto pr-1">
          {filtered.map((r) => (
            <div key={r.repo} className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6]/70 px-3 py-2">
              <div className="flex flex-wrap items-center justify-between gap-1">
                <a href={r.url} target="_blank" rel="noreferrer"
                   className="text-xs font-semibold text-[#8a6a3a] underline decoration-[#e3cfa4] underline-offset-2 hover:text-[#a8701a]">
                  {r.repo}
                </a>
                <span className="font-mono text-[10px] text-[#b39a76]">{r.concepts.length} concepts</span>
              </div>
              <div className="mt-1.5 space-y-1.5">
                {r.concepts.map((c) => (
                  <div key={c.name} className="rounded border border-[#f4ead2] bg-[#fdf8ec] px-2 py-1.5">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <p className="text-[11px] font-medium text-[#5c4327]">{c.name}</p>
                      <span className={`rounded border px-1 py-px text-[9px] uppercase ${STATUS_STYLE[c.status].cls}`}>
                        {STATUS_STYLE[c.status].label}
                      </span>
                      <span className="text-[10px] text-[#97795a]">→ {c.where}</span>
                    </div>
                    <p className="mt-0.5 text-[11px] leading-snug text-[#7c5a2e]">{c.meaning}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {repos && filtered.length === 0 && (
            <p className="py-6 text-center text-xs text-[#97795a]">No concepts match that search.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
