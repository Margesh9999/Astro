'use client';

import { useEffect, useState } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { DEFAULT_BIRTH, DEFAULT_MONEY, jatakaApi, type BirthInput, type JatakaPlaceV13, type MoneyInputs } from '@/lib/astro/api-jataka';
import { Settings2 } from 'lucide-react';

const LBL = 'text-[10px] uppercase tracking-wide text-[#b39a76]';
const INP = 'mt-1 h-8 border-[#ecdec2] bg-white text-xs';
const SEL = 'mt-1 h-8 w-full rounded-md border border-[#ecdec2] bg-white px-2 text-xs text-[#5c4327]';

const numOrNull = (v: string) => (v.trim() === '' || Number.isNaN(Number(v)) ? null : Number(v));

/** Configurable birth details (default: Margesh) + money inputs + advanced Vedic settings. */
export function JatakaForm({
  birth, money, onApply, loading, resolved,
}: {
  birth: BirthInput;
  money: MoneyInputs;
  onApply: (b: BirthInput, m: MoneyInputs) => void;
  loading: boolean;
  /** what the backend resolved (shown so the user can verify place/time zone) */
  resolved?: { place: string; lat: number; lon: number; tz: number; tz_name: string; dst: boolean; utc: string; place_resolved: boolean } | null;
}) {
  const [b, setB] = useState<BirthInput>(birth);
  const [m, setM] = useState<MoneyInputs>(money);
  const [places, setPlaces] = useState<JatakaPlaceV13[]>([]);
  const [showPlaces, setShowPlaces] = useState(false);

  useEffect(() => {
    if (!showPlaces) return;
    const t = setTimeout(() => {
      jatakaApi.places(b.place).then((r) => setPlaces(r.places ?? [])).catch(() => setPlaces([]));
    }, 220);
    return () => clearTimeout(t);
  }, [b.place, showPlaces]);

  const set = <K extends keyof BirthInput>(k: K, v: BirthInput[K]) => setB((x) => ({ ...x, [k]: v }));
  const setMoney = <K extends keyof MoneyInputs>(k: K, v: number) => setM((x) => ({ ...x, [k]: Math.max(0, v) }));

  return (
    <form
      className="rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/80 p-3"
      onSubmit={(e) => { e.preventDefault(); setShowPlaces(false); onApply(b, m); }}
    >
      <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
        <label className={`${LBL} md:col-span-2`}>
          Name
          <Input value={b.name} onChange={(e) => set('name', e.target.value)} placeholder="Margesh (default)" className={INP} />
        </label>
        <label className={LBL}>
          Birth date
          <Input type="date" value={b.date} onChange={(e) => set('date', e.target.value)} className={INP} />
        </label>
        <label className={LBL}>
          Birth time (local)
          <Input type="time" value={b.time} onChange={(e) => set('time', e.target.value)} className={INP} />
        </label>
        <label className={`relative col-span-2 ${LBL}`}>
          Birth place
          <Input
            value={b.place}
            onChange={(e) => { setB((x) => ({ ...x, place: e.target.value, lat: null, lon: null, tz: null, tz_name: '' })); setShowPlaces(true); }}
            onFocus={() => setShowPlaces(true)}
            onBlur={() => setTimeout(() => setShowPlaces(false), 180)}
            placeholder="Type a city — ~290 built in"
            className={INP}
            autoComplete="off"
          />
          {showPlaces && places.length > 0 && (
            <div className="warm-scroll absolute z-30 mt-1 max-h-48 w-full overflow-y-auto rounded-md border border-[#ecdec2] bg-[#fffdf6] shadow-lg">
              {places.map((p) => (
                <button
                  type="button"
                  key={p.name}
                  className="block w-full px-2 py-1.5 text-left text-xs normal-case tracking-normal text-[#5c4327] hover:bg-[#f9efd8]"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => { setB((x) => ({ ...x, place: p.name, lat: null, lon: null, tz: null, tz_name: '' })); setShowPlaces(false); }}
                >
                  {p.name}
                  <span className="ml-1 font-mono text-[10px] text-[#b39a76]">{p.lat.toFixed(2)}, {p.lon.toFixed(2)} · {p.tz_name}</span>
                </button>
              ))}
            </div>
          )}
        </label>
        <label className={LBL}>
          Capital (£)
          <Input type="number" min={0} step={1000} value={m.capital} onChange={(e) => setMoney('capital', Number(e.target.value))} className={INP} />
        </label>
        <label className={LBL}>
          Target £/week
          <Input type="number" min={0} step={50} value={m.target_weekly} onChange={(e) => setMoney('target_weekly', Number(e.target.value))} className={INP} />
        </label>
        <label className={LBL}>
          Savings £/month
          <Input type="number" min={0} step={50} value={m.monthly_savings} onChange={(e) => setMoney('monthly_savings', Number(e.target.value))} className={INP} />
        </label>
        <label className={LBL}>
          Base return %/yr
          <Input type="number" min={0} max={30} step={0.5} value={Math.round(m.base_return * 1000) / 10}
                 onChange={(e) => setMoney('base_return', Number(e.target.value) / 100)} className={INP} />
        </label>
        <div className="col-span-2 flex items-end gap-2">
          <Button type="submit" size="sm" disabled={loading}
                  className="h-8 flex-1 border-[#d9b46a] bg-gradient-to-b from-[#fbe3bd] to-[#f6d194] text-xs text-[#7c4a12] hover:from-[#f6d194] hover:to-[#eec27f]">
            {loading ? 'Calculating…' : 'Recalculate'}
          </Button>
          <Button type="button" size="sm" variant="outline" disabled={loading}
                  onClick={() => { setB(DEFAULT_BIRTH); setM(DEFAULT_MONEY); onApply(DEFAULT_BIRTH, DEFAULT_MONEY); }}
                  className="h-8 border-[#ecdec2] bg-[#fffdf6] text-[11px] text-[#8a6a3a]">
            Reset to Margesh
          </Button>
        </div>
      </div>

      <details className="mt-2 rounded-lg border border-[#f4ead2] bg-[#fdf8ec]/60 px-2.5 py-1.5">
        <summary className="flex cursor-pointer list-none items-center gap-1.5 text-[11px] font-medium text-[#8a6a3a]">
          <Settings2 className="h-3.5 w-3.5" /> Advanced: exact coordinates, time zone, node &amp; ayanamsa
        </summary>
        <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-6">
          <label className={LBL}>
            Latitude (°N +)
            <Input type="number" step="0.0001" value={b.lat ?? ''} placeholder={resolved ? String(resolved.lat) : 'auto'}
                   onChange={(e) => set('lat', numOrNull(e.target.value))} className={INP} />
          </label>
          <label className={LBL}>
            Longitude (°E +)
            <Input type="number" step="0.0001" value={b.lon ?? ''} placeholder={resolved ? String(resolved.lon) : 'auto'}
                   onChange={(e) => set('lon', numOrNull(e.target.value))} className={INP} />
          </label>
          <label className={LBL}>
            IANA time zone
            <Input value={b.tz_name ?? ''} placeholder={resolved?.tz_name ?? 'auto from place'}
                   onChange={(e) => set('tz_name', e.target.value)} className={INP} />
          </label>
          <label className={LBL}>
            Manual UTC offset (h)
            <Input type="number" step="0.25" value={b.tz ?? ''} placeholder="auto (DST-aware)"
                   onChange={(e) => set('tz', numOrNull(e.target.value))} className={INP} />
          </label>
          <label className={LBL}>
            Rahu/Ketu node
            <select className={SEL} value={b.node} onChange={(e) => set('node', e.target.value as BirthInput['node'])}>
              <option value="mean">Mean node (default)</option>
              <option value="true">True node</option>
            </select>
          </label>
          <label className={LBL}>
            Ayanamsa / zodiac
            <select className={SEL} value={b.ayanamsa} onChange={(e) => set('ayanamsa', e.target.value as BirthInput['ayanamsa'])}>
              <option value="lahiri">Lahiri / Chitrapaksha (default)</option>
              <option value="raman">B.V. Raman</option>
              <option value="kp">Krishnamurti (KP)</option>
              <option value="tropical">Tropical (Western)</option>
            </select>
          </label>
        </div>
        <p className="mt-1.5 text-[10px] leading-snug text-[#97795a]">
          Leave blank to use the gazetteer. A manual UTC offset skips daylight-saving logic — use it only if you know
          the exact offset in force at birth. Vedic sidereal Lahiri + mean node + whole-sign houses is the default.
        </p>
      </details>

      {resolved && (
        <p className="mt-1.5 text-[10px] leading-snug text-[#97795a]">
          Chart cast for <b>{resolved.place}</b> ({resolved.lat.toFixed(4)}°, {resolved.lon.toFixed(4)}°) ·{' '}
          {resolved.tz_name} UTC{resolved.tz >= 0 ? '+' : ''}{resolved.tz}{resolved.dst ? ' (daylight saving in force)' : ''} ·
          birth moment {resolved.utc.replace('T', ' ').slice(0, 16)} UTC
          {!resolved.place_resolved && (
            <span className="text-[#a34332]"> · place not in gazetteer — enter latitude/longitude/time zone under Advanced</span>
          )}
        </p>
      )}
    </form>
  );
}
