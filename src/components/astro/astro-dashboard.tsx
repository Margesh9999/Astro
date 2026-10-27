'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { astroApi } from '@/lib/astro/api';
import type { MarketQuote, PlanetaryResponse, SymbolInfo } from '@/lib/astro/types';
import { Skeleton } from '@/components/ui/skeleton';
import { MarketCard } from './market-card';
import { PlanetaryCard } from './planetary-card';
import { ModelLab } from './model-lab';
import { BacktestCard } from './backtest-card';
import { EventsCard } from './events-card';
import { AstroSignalCard } from './astro-signal-card';
import { QuantDeskCard } from './quant-desk-card';
import { OptionsLabCard } from './options-lab-card';
import { JatakaCard } from './jataka-card';
import { AgentsCard } from './agents-card';
import { ConceptsCard } from './concepts-card';
import { InstrumentPicker } from './instrument-picker';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';

const FALLBACK_SYMBOLS: SymbolInfo[] = [
  { symbol: '^GSPC', name: 'S&P 500', market: 'US', flag: '🇺🇸' },
  { symbol: '^IXIC', name: 'NASDAQ Composite', market: 'US', flag: '🇺🇸' },
  { symbol: '^NSEI', name: 'Nifty 50', market: 'India', flag: '🇮🇳' },
  { symbol: '^BSESN', name: 'BSE Sensex', market: 'India', flag: '🇮🇳' },
  { symbol: '^FTSE', name: 'FTSE 100', market: 'UK', flag: '🇬🇧' },
];

/** Vedic (sidereal · Lahiri) is the one and only mode — the toggle was removed
 *  on purpose so the kundali charts are ALWAYS Vedic. */
const VEDIC = true;

export function AstroDashboard() {
  const [symbols, setSymbols] = useState<SymbolInfo[]>(FALLBACK_SYMBOLS);
  const [symbol, setSymbol] = useState('^GSPC');
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [quote, setQuote] = useState<MarketQuote | null>(null);
  const [planetary, setPlanetary] = useState<PlanetaryResponse | null>(null);
  const [loadingCore, setLoadingCore] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const seqRef = useRef(0);

  const loadCore = useCallback(
    async (sym: string, silent: boolean = false) => {
      const seq = ++seqRef.current;
      if (silent) setRefreshing(true);
      else setLoadingCore(true);
      try {
        const health = await astroApi.health();
        if (seq !== seqRef.current) return;
        setBackendOk(health.status === 'healthy');

        const today = new Date().toISOString().slice(0, 10);
        const [q, p] = await Promise.allSettled([
          astroApi.market(sym),
          astroApi.planetary(today, VEDIC),
        ]);
        if (seq !== seqRef.current) return; // a newer request superseded this one
        setQuote(q.status === 'fulfilled' ? q.value : null);
        setPlanetary(p.status === 'fulfilled' ? p.value : null);
        if (q.status === 'rejected') console.error('market:', q.reason);
        if (p.status === 'rejected') console.error('planetary:', p.reason);
      } catch (e) {
        console.error('core load failed:', e);
        if (seq !== seqRef.current) return;
        setBackendOk(false);
      } finally {
        if (seq === seqRef.current) {
          setLoadingCore(false);
          setRefreshing(false);
        }
      }
    },
    [],
  );

  useEffect(() => {
    loadCore(symbol);
  }, [symbol]);

  return (
    <div className="vedic-backdrop min-h-screen text-[#4a3525]">
      <header className="relative border-b border-[#ecdec2] bg-[#fffdf6]/70 backdrop-blur">
        <div className="mx-auto max-w-7xl px-4 py-5 sm:px-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <div className="relative flex h-12 w-12 items-center justify-center rounded-full border border-[#d9b46a] bg-gradient-to-br from-[#fdeecd] to-[#f7dfb2] shadow-[0_2px_10px_rgba(201,150,46,0.25)]">
                <span className="font-brand text-xl leading-none text-[#a8701a]">ॐ</span>
                <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-gradient-to-br from-[#e8a04c] to-[#c9553f] shadow-sm" />
              </div>
              <div>
                <h1 className="font-brand text-2xl leading-tight tracking-wide">
                  Astro<span className="gold-text">Trader</span>
                </h1>
                <p className="font-display text-[11px] uppercase tracking-[0.22em] text-[#97795a]">
                  Jyotisha × Market Data — a technical exploration
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {/* instrument universe picker */}
              <InstrumentPicker
                value={symbol}
                onSelect={(e) => setSymbol(e.symbol)}
              />

              {/* quick-select pills */}
              <div className="flex flex-wrap items-center gap-1.5">
                {symbols.map((s) => {
                  const active = symbol === s.symbol;
                  return (
                    <button
                      key={s.symbol}
                      onClick={() => setSymbol(s.symbol)}
                      className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-all ${
                        active
                          ? 'border-[#d98324] bg-gradient-to-b from-[#fbe3bd] to-[#f6d194] text-[#7c4a12] shadow-[0_1px_6px_rgba(217,131,36,0.25)]'
                          : 'border-[#ecdec2] bg-[#fffdf6]/80 text-[#97795a] hover:border-[#d9b46a] hover:text-[#7c5a2e]'
                      }`}
                    >
                      <span className="mr-1">{s.flag}</span>
                      {s.name}
                    </button>
                  );
                })}
              </div>

              {/* ayanamsa badge — Vedic-only mode (toggle removed by design) */}
              <div className="flex items-center gap-2 rounded-full border border-[#d9c9e0] bg-gradient-to-r from-[#f6e9f0] to-[#fbead0] px-3 py-1.5">
                <span className="font-brand text-sm leading-none text-[#8a4a62]">ॐ</span>
                <span className="text-xs font-medium text-[#7c5a2e]">Vedic · Sidereal · Lahiri</span>
              </div>

              <Button
                variant="outline"
                size="icon"
                className="h-9 w-9 border-[#ecdec2] bg-[#fffdf6]/80 hover:border-[#d9b46a] hover:bg-[#f7e8cd]"
                onClick={() => loadCore(symbol, true)}
                disabled={refreshing}
                aria-label="Refresh data"
              >
                <RefreshCw className={`h-4 w-4 text-[#b0763a] ${refreshing ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>

          {/* disclaimer */}
          <div className="mt-4 flex items-start gap-2 rounded-lg border border-[#eed9b4] bg-gradient-to-r from-[#fdf3dc] to-[#fbead0] px-3 py-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#c98a2e]" />
            <p className="text-xs leading-relaxed text-[#8a6a3a]">
              Educational exploration only — planetary correlations and modelled option analytics have no proven
              predictive value. Options involve substantial risk of loss. This is not financial advice.
            </p>
          </div>
        </div>
        <div className="ornament-rule" />
      </header>

      <main className="relative mx-auto max-w-7xl px-4 py-6 sm:px-6">
        {backendOk === false && (
          <div className="mb-6 rounded-lg border border-[#eecfc7] bg-[#fbeae4] px-4 py-3 text-sm text-[#a14d3c]">
            Backend service is not responding. It boots automatically with the app — try refreshing in a
            few seconds.
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <MarketCard quote={quote} loading={loadingCore} />
          <div className="lg:col-span-2">
            <PlanetaryCard data={planetary} loading={loadingCore} vedic={VEDIC} />
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
          <ModelLab symbol={symbol} vedic={VEDIC} />
          <div className="lg:col-span-2">
            <BacktestCard symbol={symbol} vedic={VEDIC} />
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
          <EventsCard symbol={symbol} />
          <div className="lg:col-span-2">
            <AstroSignalCard symbol={symbol} spot={quote?.price} />
          </div>
        </div>

        {/* ── Merged: Janma Kundli & Wealth Blueprint (configurable, default Margesh) ── */}
        <section className="mt-8">
          <div className="mb-3 flex items-center gap-3">
            <h2 className="font-display text-sm font-semibold uppercase tracking-[0.2em] text-[#97795a]">
              ✦ Janma Kundli &amp; Wealth Blueprint
            </h2>
            <div className="h-px flex-1 bg-gradient-to-r from-[#e3cfa4] to-transparent" />
          </div>
          <JatakaCard symbol={symbol} symbolName={quote?.name} />
        </section>

        {/* ── Institutional Desk ─────────────────────────────────────── */}
        <section className="mt-8">
          <div className="mb-3 flex items-center gap-3">
            <h2 className="font-display text-sm font-semibold uppercase tracking-[0.2em] text-[#97795a]">
              ✦ Institutional Desk
            </h2>
            <div className="h-px flex-1 bg-gradient-to-r from-[#e3cfa4] to-transparent" />
          </div>
          <div className="flex flex-col gap-4">
            <QuantDeskCard symbol={symbol} />
            <OptionsLabCard symbol={symbol} spot={quote?.price} />
          </div>
        </section>

        {/* ── AI Agents & Knowledge Coverage ── */}
        <section className="mt-8">
          <div className="mb-3 flex items-center gap-3">
            <h2 className="font-display text-sm font-semibold uppercase tracking-[0.2em] text-[#97795a]">
              ✦ AI Agents & Quant Library Coverage
            </h2>
            <div className="h-px flex-1 bg-gradient-to-r from-[#e3cfa4] to-transparent" />
          </div>
          <div className="flex flex-col gap-4">
            <AgentsCard symbol={symbol} />
            <ConceptsCard />
          </div>
        </section>

        {loadingCore && (
          <div className="mt-4 flex items-center justify-center gap-2 text-xs text-[#97795a]">
            <Skeleton className="h-3 w-3 rounded-full bg-[#e8d5ae]" />
            Loading live data…
          </div>
        )}
      </main>

      <footer className="relative mt-8 border-t border-[#ecdec2] bg-[#fffdf6]/85 py-6">
        <div className="ornament-rule mb-6 opacity-60" />
        <div className="mx-auto max-w-7xl px-4 text-center text-xs text-[#97795a] sm:px-6">
          <p className="font-display tracking-wide">
            <span className="gold-text font-brand text-sm">॥ AstroTrader ॥</span>
          </p>
          <p className="mt-1.5">
            Swiss Ephemeris (pyswisseph) · yfinance · scikit-learn · FastAPI · Next.js. Data via Yahoo
            Finance, delayed.
          </p>
          <p className="mt-1 text-[#b39a76]">
            Past correlations do not indicate future results. No warranty of any kind.
          </p>
        </div>
      </footer>
    </div>
  );
}
