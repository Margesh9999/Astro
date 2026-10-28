'use client';

import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { JatakaReportV13 } from '@/lib/astro/api-jataka';
import { PLANET_META, SIGNS } from './planet-meta';
import { Concept, FitBar, Note, Pill } from './jataka-ui';
import { Compass, Coins, Crown, Grid3X3, Hourglass, Scale, Scroll, ScrollText, Stars, TrendingUp } from 'lucide-react';

const GRAHA_ORDER = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Rahu', 'Ketu', 'Lagna'];

/** Astro Analysis tab — wealth houses, yogas, composite strength, D9/D10 and every master-guide concept. */
export function JatakaAnalysisTab({ report }: { report: JatakaReportV13 }) {
  const aa = report.astro_analysis;
  const plan = report.plan;
  if (!aa || !aa.verdict) {
    return <Note text="Astro Analysis engine unavailable for this chart — the rest of the suite still works." />;
  }
  const savData = aa.ashtakvarga.sav.map((bindus, i) => ({ sign: SIGNS[i], bindus }));
  const wealthHouses = Object.entries(aa.ashtakvarga.wealth)
    .map(([k, v]) => ({ house: Number(k.replace('house_', '')), ...v }))
    .sort((a, b) => a.house - b.house);
  const yogas = aa.yogas.found;
  const dhana = yogas.filter((y) => /Wealth|Dhana|Lakshmi/i.test(y.category + y.name));
  const raja = yogas.filter((y) => /Raja|Power|Pancha/i.test(y.category + y.name));
  const other = yogas.filter((y) => !dhana.includes(y) && !raja.includes(y));
  const comp = plan && !plan.error ? Object.entries(plan.composite_strength).sort((a, b) => b[1].score - a[1].score) : [];
  const strongest = comp.slice(0, 3).map(([g]) => g);
  const weakest = comp.slice(-2).map(([g]) => g);
  const wh = plan && !plan.error ? plan.wealth_houses : [];
  const strongWh = wh.filter((h) => h.tone === 'strong').map((h) => h.house);
  const weakWh = wh.filter((h) => h.tone === 'weak').map((h) => h.house);

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-lg border border-[#e4d0b4] bg-gradient-to-r from-[#fdf3dc] via-[#f9e9d2] to-[#f6e3c4] p-3">
        <p className="font-display text-[10px] uppercase tracking-[0.18em] text-[#a8701a]">Wealth reading in one paragraph</p>
        <p className="mt-1 text-xs leading-relaxed text-[#5c4327]">
          {aa.verdict.headline} (score {aa.verdict.score}/100). Strongest planets: <b>{strongest.join(', ')}</b>; weakest: {weakest.join(', ')}.
          {' '}Wealth houses working for you: {strongWh.length ? strongWh.map((h) => `H${h}`).join(', ') : 'none clearly'}
          {weakWh.length ? `; handle with care: ${weakWh.map((h) => `H${h}`).join(', ')}` : ''}. {dhana.length} wealth (dhana) yoga(s) and {raja.length} power (raja) yoga(s) found.
          {' '}Practical upshot: put most capital where the strong planets and houses point (see the Recommendations tab) and keep the weak houses&apos; activities small and rule-based.
        </p>
      </div>

      {/* wealth houses */}
      {wh.length > 0 && (
        <div className="rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/80 p-3">
          <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-[#5c4327]">
            <Coins className="h-3.5 w-3.5 text-[#c98a2e]" /> Wealth houses 2 · 5 · 8 · 9 · 11 and their lords
          </p>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
            {wh.map((h) => (
              <div key={h.house} className={`rounded-lg border px-2.5 py-2 ${h.tone === 'strong' ? 'border-[#a8d8bf] bg-[#e2f3e9]/50' : h.tone === 'weak' ? 'border-[#e8b3a8] bg-[#fbe7e0]/50' : 'border-[#f0e4cc] bg-[#fdf8ec]'}`}>
                <div className="flex items-center justify-between">
                  <p className="text-[11px] font-semibold text-[#5c4327]">H{h.house} · {h.title}</p>
                  <span className="font-mono text-[10px] text-[#8a6a3a]">{h.score}</span>
                </div>
                <FitBar value={h.score} />
                <p className="mt-1 text-[10px] text-[#97795a]">
                  {h.sign} · lord <span style={{ color: PLANET_META[h.lord]?.color }}>{PLANET_META[h.lord]?.glyph} {h.lord}</span> in H{h.lord_house} ({h.lord_sign}, {h.lord_dignity})
                  {h.bindus != null ? ` · ${h.bindus} bindus` : ''}
                </p>
                <p className="mt-0.5 text-[10px] leading-snug text-[#7c5a2e]">{h.plain}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* yogas */}
      <div className="rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/80 p-3">
        <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-[#5c4327]">
          <Crown className="h-3.5 w-3.5 text-[#c98a2e]" /> Dhana (wealth) &amp; Raja (power) yogas
        </p>
        {([['Wealth / Dhana', dhana, 'green'], ['Power / Raja', raja, 'lav'], ['Other combinations', other, 'gold']] as const).map(([label, list, tone]) => (
          list.length > 0 && (
            <div key={label} className="mb-2">
              <p className="mb-1 text-[10px] uppercase tracking-wide text-[#b39a76]">{label}</p>
              <div className="space-y-1">
                {list.map((y, i) => (
                  <div key={i} className="rounded border border-[#f0e4cc] bg-[#fdf8ec] px-2 py-1">
                    <p className="text-[11px] font-semibold text-[#5c4327]">{y.name} <Pill tone={tone}>{y.strength}</Pill>
                      {y.planets.length > 0 && <span className="ml-1 text-[10px] font-normal text-[#97795a]">({y.planets.join(' + ')})</span>}</p>
                    <p className="text-[10px] leading-snug text-[#7c5a2e]">{y.meaning}</p>
                  </div>
                ))}
              </div>
            </div>
          )
        ))}
        {yogas.length === 0 && <p className="text-[11px] text-[#97795a]">No classical yoga detected by the rule set.</p>}
      </div>

      {/* composite strength */}
      {comp.length > 0 && (
        <div className="rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/80 p-3">
          <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-[#5c4327]">
            <Scale className="h-3.5 w-3.5 text-[#c98a2e]" /> Planetary strength (shadbala-lite composite)
          </p>
          <div className="grid grid-cols-1 gap-x-4 gap-y-1.5 md:grid-cols-2">
            {comp.map(([g, c]) => (
              <div key={g}>
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-[#5c4327]"><span style={{ color: PLANET_META[g]?.color }}>{PLANET_META[g]?.glyph}</span> {g}{report.positions[g]?.combust ? ' · combust' : ''}</span>
                  <span className="font-mono text-[#8a6a3a]">{c.score}</span>
                </div>
                <FitBar value={c.score} />
                <p className="text-[9px] text-[#b39a76]">
                  {Object.entries(c.parts).map(([k, v]) => `${k} ${v}`).join(' · ')}
                </p>
              </div>
            ))}
          </div>
          <p className="mt-2 text-[10px] leading-snug text-[#97795a]">
            Composite = 50% placement (dignity + house) + 30% six-fold Shadbala vs its BPHS requirement + 20% Navamsa (D9) dignity, minus a combustion penalty.
            Planets above ~60 are the ones whose sectors and periods you can lean on.
          </p>
        </div>
      )}

      <p className="mt-1 font-display text-[11px] uppercase tracking-[0.18em] text-[#97795a]">Deep dive — every concept of the master guide</p>
      <Concept icon={<Grid3X3 className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Vargas — the 16 divisional charts (BPHS)"
                     subtitle={aa.vargas.info.D9.title + ' · ' + aa.vargas.info.D10.title} open>
              <Note text={aa.vargas.plain} />
              <Note text={aa.vargas.navamsa_focus} icon={<Stars className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-[#c98a2e]" />} />
              <Note text={aa.vargas.dasamsa_focus} icon={<TrendingUp className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-[#c98a2e]" />} />
              <div className="mt-2 overflow-x-auto">
                <table className="w-full text-left text-[10px]">
                  <thead>
                    <tr className="text-[#b39a76]">
                      <th className="py-1 pr-2">Graha</th>
                      {(['D2', 'D3', 'D9', 'D10', 'D12', 'D60'] as const).map((v) => (
                        <th key={v} className="py-1 pr-2" title={aa.vargas.info[v]?.meaning}>{v}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {GRAHA_ORDER.filter((n) => aa.vargas.planets[n]).map((n) => (
                      <tr key={n} className="border-t border-[#f4ead2]">
                        <td className="py-1 pr-2 font-medium" style={{ color: PLANET_META[n]?.color }}>
                          {PLANET_META[n]?.glyph} {n}
                        </td>
                        {(['D2', 'D3', 'D9', 'D10', 'D12', 'D60'] as const).map((v) => {
                          const cell = aa.vargas.planets[n].vargas[v];
                          const good = ['exalted', 'own', 'moolatrikona'].includes(cell.dignity);
                          const bad = cell.dignity === 'debilitated';
                          return (
                            <td key={v} className={`py-1 pr-2 ${good ? 'text-[#2f7357] font-medium' : bad ? 'text-[#a34332]' : 'text-[#7c5a2e]'}`}>
                              {cell.sign}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Concept>
      
            <Concept icon={<Compass className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Jaimini — chara karakas, Arudha Lagna & Karakamsa"
                     subtitle={`Soul planet ${aa.jaimini.atmakaraka} · Karakamsa ${aa.jaimini.karakamsa_sign}`}>
              <Note text={aa.jaimini.plain} />
              <div className="mt-2 grid grid-cols-1 gap-1.5 md:grid-cols-2">
                {aa.jaimini.karakas.map((k) => (
                  <div key={k.key} className="rounded-lg border border-[#f0e4cc] bg-[#fdf8ec] px-2.5 py-1.5">
                    <p className="text-[11px] font-semibold text-[#5c4327]">
                      <Pill tone="lav">{k.key}</Pill> {k.label} —{' '}
                      <span style={{ color: PLANET_META[k.planet]?.color }}>
                        {PLANET_META[k.planet]?.glyph} {k.planet}
                      </span>{' '}
                      <span className="font-normal text-[#97795a]">{k.sign}, house {k.house}</span>
                    </p>
                    <p className="text-[10px] leading-snug text-[#7c5a2e]">{k.money_meaning}</p>
                  </div>
                ))}
              </div>
            </Concept>
      
            <Concept icon={<Hourglass className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Avasthas — planetary ages (BPHS states)"
                     subtitle="Which grahas are in their delivery prime">
              <Note text={aa.avasthas.plain} />
              <div className="mt-2 flex flex-wrap gap-1.5">
                {Object.entries(aa.avasthas.planets).map(([n, r]) => (
                  <Pill key={n} tone={r.state.startsWith('Yuva') ? 'green' : r.state.startsWith('Mrita') || r.state.startsWith('Vriddha') ? 'rose' : 'gold'}>
                    {PLANET_META[n]?.glyph} {n}: {r.state}
                  </Pill>
                ))}
              </div>
            </Concept>
      
            <Concept icon={<Stars className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Yogas — planetary combinations"
                     subtitle={`${aa.yogas.found.length} classical combination(s) detected`}>
              <Note text={aa.yogas.plain} />
              <div className="mt-2 space-y-1.5">
                {aa.yogas.found.map((y, i) => (
                  <div key={i} className="rounded-lg border border-[#f0e4cc] bg-[#fdf8ec] px-2.5 py-1.5">
                    <p className="text-[11px] font-semibold text-[#5c4327]">
                      {y.name} <Pill tone={y.strength === 'strong' ? 'green' : 'gold'}>{y.category}</Pill>
                      {y.planets.length > 0 && <span className="ml-1 text-[10px] text-[#97795a]">({y.planets.join(' + ')})</span>}
                    </p>
                    <p className="text-[10px] leading-snug text-[#7c5a2e]">{y.meaning}</p>
                  </div>
                ))}
              </div>
            </Concept>
      
            <Concept icon={<Scale className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Shadbala — six-fold planetary strength"
                     subtitle={`Ranking in Rupas · day lord ${aa.shadbala.day_lord} · hora lord ${aa.shadbala.hora_lord}`}>
              <Note text={aa.shadbala.plain} />
              <div className="mt-2 space-y-1.5">
                {aa.shadbala.ranked.map(([n, rupas]) => {
                  const req = aa.shadbala.planets[n].required;
                  const pct = Math.min(100, (rupas / 10) * 100);
                  const reqPct = (req / 10) * 100;
                  return (
                    <div key={n}>
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-[#5c4327]">{PLANET_META[n]?.glyph} {n}</span>
                        <span className="font-mono text-[#8a6a3a]">
                          {rupas.toFixed(2)} <span className="text-[10px] text-[#b39a76]">/ {req.toFixed(2)} needed</span>
                        </span>
                      </div>
                      <div className="relative h-1.5 overflow-hidden rounded-full bg-[#f4ead2]">
                        <div className="h-full rounded-full bg-gradient-to-r from-[#8bb5a3] to-[#4a9a7e]" style={{ width: `${pct}%` }} />
                        <div className="absolute top-0 h-full w-px bg-[#c9553f]" style={{ left: `${reqPct}%` }} />
                      </div>
                      <p className="mt-0.5 text-[10px] text-[#97795a]">{aa.shadbala.planets[n].verdict}</p>
                    </div>
                  );
                })}
              </div>
              <div className="mt-2 grid grid-cols-2 gap-1 md:grid-cols-4">
                {Object.entries(aa.shadbala.planets).flatMap(([n, r]) =>
                  Object.entries(r.components).map(([c, v]) => (
                    <div key={n + c} className="rounded border border-[#f0e4cc] bg-[#fffdf6]/80 px-1.5 py-1 text-[9px]">
                      <p className="font-medium text-[#5c4327]">{n} · {c.split(' ')[0]}</p>
                      <p className="font-mono text-[#8a6a3a]">{v}</p>
                    </div>
                  )),
                )}
              </div>
            </Concept>
      
            <Concept icon={<Scale className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Bhavabala — house strength"
                     subtitle={`Strongest: house ${aa.bhavabala.strongest_house.house} (${aa.bhavabala.strongest_house.sign})`}>
              <Note text={aa.bhavabala.plain} />
              <div className="mt-2 grid grid-cols-2 gap-1.5 md:grid-cols-4">
                {aa.bhavabala.houses.map((h) => (
                  <div key={h.house} className={`rounded-lg border px-2 py-1.5 ${h.wealth_flag ? 'border-[#d9b46a] bg-[#fdf3dc]' : 'border-[#f0e4cc] bg-[#fffdf6]/80'}`}>
                    <div className="flex items-center justify-between text-[10px]">
                      <span className="font-semibold text-[#5c4327]">H{h.house} {h.sign}</span>
                      <span className="font-mono text-[#8a6a3a]">{h.score}</span>
                    </div>
                    <div className="mt-1 h-1 overflow-hidden rounded-full bg-[#f4ead2]">
                      <div className="h-full rounded-full bg-gradient-to-r from-[#e8a04c] to-[#c9553f]" style={{ width: `${h.score}%` }} />
                    </div>
                    {h.wealth_flag && <p className="mt-0.5 text-[9px] text-[#a8701a]">wealth house</p>}
                  </div>
                ))}
              </div>
            </Concept>
      
            <Concept icon={<Grid3X3 className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Ashtakvarga — bindu point system"
                     subtitle={`Sarvashtakavarga ${aa.ashtakvarga.sav_total} bindus · prastara ${aa.ashtakvarga.prastara_total}`}>
              <Note text={aa.ashtakvarga.plain} />
              <div className="mt-2 h-40 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={savData} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
                    <XAxis dataKey="sign" tick={{ fontSize: 9, fill: '#97795a' }} interval={0} angle={-35} textAnchor="end" height={44} />
                    <YAxis domain={[0, 40]} tick={{ fontSize: 9, fill: '#97795a' }} />
                    <Tooltip
                      contentStyle={{ background: '#fffdf6', border: '1px solid #ecdec2', borderRadius: 8, fontSize: 11 }}
                      formatter={(v) => [`${v} bindus`, 'SAV']}
                    />
                    <Bar dataKey="bindus" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                      {savData.map((d, i) => (
                        <Cell key={i} fill={d.bindus >= 29 ? '#4a9a7e' : d.bindus >= 25 ? '#c9962e' : '#c9553f'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-1.5 md:grid-cols-3">
                {wealthHouses.map((h) => (
                  <div key={h.house} className="rounded border border-[#f0e4cc] bg-[#fdf8ec] px-2 py-1 text-[10px]">
                    <span className="font-semibold text-[#5c4327]">House {h.house} ({h.sign})</span>
                    <span className="ml-1 font-mono text-[#8a6a3a]">{h.bindus} bindus</span>
                    <span className="ml-1 text-[9px] text-[#97795a]">{h.status}</span>
                  </div>
                ))}
              </div>
            </Concept>
      
            <Concept icon={<Compass className="h-3.5 w-3.5 text-[#c98a2e]" />} title="KP system — star & sub lords (Krishnamurti Paddhati)"
                     subtitle={`Ruling planets: ${aa.kp.ruling_planets.join(', ')} · day lord ${aa.kp.day_lord}`}>
              <Note text={aa.kp.plain} />
              <div className="mt-2 overflow-x-auto">
                <table className="w-full text-left text-[10px]">
                  <thead>
                    <tr className="text-[#b39a76]">
                      <th className="py-1 pr-2">Cusp</th><th className="pr-2">Sign</th><th className="pr-2">Degree</th><th className="pr-2">Star lord</th><th className="pr-2">Sub lord</th>
                    </tr>
                  </thead>
                  <tbody>
                    {aa.kp.cusps.map((c) => (
                      <tr key={c.cusp} className={`border-t border-[#f4ead2] ${[2, 6, 10, 11].includes(c.cusp) ? 'bg-[#fdf3dc]/70' : ''}`}>
                        <td className="py-1 pr-2 font-medium text-[#5c4327]">
                          {c.cusp}{c.cusp_name ? ` · ${c.cusp_name}` : ''}
                        </td>
                        <td className="pr-2 text-[#7c5a2e]">{c.sign}</td>
                        <td className="pr-2 font-mono text-[#7c5a2e]">{c.degree.toFixed(1)}°</td>
                        <td className="pr-2 text-[#97795a]">{c.star_lord}</td>
                        <td className="pr-2 font-medium text-[#6b4e93]">{c.sub_lord}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Concept>
      
            <Concept icon={<Hourglass className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Yogini dasha — the fast 36-year timer"
                     subtitle={`Now: ${aa.yogini.current.yogini} (${aa.yogini.current.lord}) · ${aa.yogini.direction} cycle`}>
              <Note text={aa.yogini.plain} />
              <div className="mt-2 space-y-1">
                {aa.yogini.periods.map((p, i) => (
                  <div key={i} className="flex flex-wrap items-center justify-between rounded border border-[#f0e4cc] bg-[#fdf8ec] px-2 py-1 text-[10px]">
                    <span className="font-medium text-[#5c4327]">{p.yogini} ({p.lord})</span>
                    <span className="font-mono text-[#97795a]">{p.start} → {p.end} · {p.years}y</span>
                  </div>
                ))}
              </div>
            </Concept>
      
            <Concept icon={<Scroll className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Karma Vipaka — nakshatra karmic lens"
                     subtitle={`${aa.karma_vipaka.nakshatra} · deity ${aa.karma_vipaka.deity}`}>
              <Note text={aa.karma_vipaka.plain} icon={<Scroll className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-[#c98a2e]" />} />
            </Concept>
      
            <Concept icon={<TrendingUp className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Transits × Ashtakvarga — is the ground fertile?"
                     subtitle="Saturn / Jupiter / Rahu / Ketu against your bindu map">
              <Note text={aa.transits.plain} />
              <div className="mt-2 space-y-1.5">
                {aa.transits.rows.map((t, i) => (
                  <div key={i} className="rounded-lg border border-[#f0e4cc] bg-[#fdf8ec] px-2.5 py-1.5">
                    <p className="text-[11px] font-semibold text-[#5c4327]">
                      {PLANET_META[t.planet]?.glyph} {t.planet} → {t.sign} (house {t.house})
                      <Pill tone={t.sav_bindus >= 28 ? 'green' : t.sav_bindus >= 25 ? 'gold' : 'rose'}>
                        {t.sav_bindus} SAV bindus
                      </Pill>
                      {t.own_bindus != null && <Pill>own {t.own_bindus}</Pill>}
                    </p>
                    <p className="text-[10px] leading-snug text-[#7c5a2e]">{t.plain}</p>
                  </div>
                ))}
              </div>
            </Concept>
      
            <Concept icon={<ScrollText className="h-3.5 w-3.5 text-[#c98a2e]" />} title="House-by-house synthesis — all 12 bhavas"
                     subtitle="Every house read for its money promise">
              <div className="space-y-1.5">
                {aa.houses.map((h) => (
                  <div key={h.house} className={`rounded-lg border px-2.5 py-1.5 ${h.wealth_flag ? 'border-[#d9b46a] bg-[#fdf3dc]/80' : 'border-[#f0e4cc] bg-[#fffdf6]/80'}`}>
                    <p className="text-[11px] font-semibold text-[#5c4327]">
                      House {h.house} · {h.sign} {h.wealth_flag && <Pill tone="gold">wealth</Pill>}
                      <span className="ml-1 font-mono text-[10px] text-[#97795a]">score {h.score} · {h.bindus} bindus</span>
                    </p>
                    <p className="text-[10px] leading-snug text-[#7c5a2e]">{h.plain}</p>
                  </div>
                ))}
              </div>
            </Concept>

    </div>
  );
}
