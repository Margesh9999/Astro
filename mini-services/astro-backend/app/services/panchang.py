"""v1.4 Panchang (five limbs of the Hindu almanac) + forward "market weather" calendar.

Everything is computed locally with Swiss Ephemeris (sidereal / Lahiri, the app default):

* **Vara**      weekday, counted from local sunrise (the Vedic day starts at sunrise)
* **Tithi**     lunar day: each 12 deg of Moon-minus-Sun elongation (30 per lunar month)
* **Nakshatra** Moon's lunar mansion: 27 x 13 deg 20 min of sidereal longitude
* **Yoga**      27 x 13 deg 20 min of (sidereal Sun + sidereal Moon)
* **Karana**    half a tithi (6 deg elongation); 60 per month, 11 names
* Rahu Kaal / Yamaganda / Gulika Kaal (1/8th day-part blocks) and Abhijit muhurta

Every limb also carries its *end time* (found by bisection), so the UI can say
"Shukla Panchami until 14:32".

Market notes are plain-English folklore of Indian traders (Amavasya caution, etc.) and are
labelled as such. They are NOT a validated edge; the per-symbol statistics shown next to them
come from the v1.3 cycle-statistics engine and are historical, illustrative only.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import swisseph as swe

from app.core.vedic import VedicCalculator

swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
_SID = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED

NAKSHATRAS = VedicCalculator.NAKSHATRAS
NAK_W = 360.0 / 27.0

TITHI_NAMES = ["Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami",
               "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi"]
YOGA_NAMES = ["Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda", "Sukarma",
              "Dhriti", "Shula", "Ganda", "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra",
              "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva", "Siddha", "Sadhya", "Shubha",
              "Shukla", "Brahma", "Indra", "Vaidhriti"]
# Yogas traditionally avoided for new ventures
INAUSPICIOUS_YOGAS = {"Vishkambha", "Atiganda", "Shula", "Ganda", "Vyaghata", "Vajra",
                      "Vyatipata", "Parigha", "Vaidhriti"}
MOVABLE_KARANAS = ["Bava", "Balava", "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti"]
VARA = [  # Python weekday() order: Monday = 0
    ("Somavara", "Moon"), ("Mangalavara", "Mars"), ("Budhavara", "Mercury"),
    ("Guruvara", "Jupiter"), ("Shukravara", "Venus"), ("Shanivara", "Saturn"), ("Ravivara", "Sun"),
]
# 1/8th-of-daytime block index (1-based) per weekday, Monday = 0
RAHU_KAAL = [2, 7, 5, 6, 4, 3, 8]
YAMAGANDA = [4, 3, 2, 1, 7, 6, 5]
GULIKA = [6, 5, 4, 3, 2, 1, 7]

GANDANTA_NAK = {"Ashlesha", "Jyeshtha", "Revati", "Ashwini", "Magha", "Mula"}

TRADER_FOLKLORE = {
    "Amavasya": "New Moon. Indian trader folklore treats Amavasya as a low-energy, choppy day; many "
                "avoid fresh positions and keep size small.",
    "Purnima": "Full Moon. Folklore links Purnima to emotional, high-volume sessions; expect bigger "
               "intraday swings and avoid chasing gaps.",
    "Ekadashi": "Ekadashi (11th lunar day). Considered a day for discipline: review, trim and plan "
                "rather than add risk.",
    "Vishti": "Vishti (Bhadra) karana is traditionally avoided for starting anything new, including "
              "fresh trades.",
    "Gandanta": "Moon is near a water-fire junction (Gandanta). Tradition reads this as an unstable "
                "transition; a day for tight stops.",
    "BadYoga": "An inauspicious yoga is running; tradition advises against initiating long-term "
               "commitments today.",
}


# ----------------------------------------------------------------------------- primitives

def _jd(dt: datetime) -> float:
    dt = dt.astimezone(timezone.utc)
    return swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute / 60 + dt.second / 3600)


def _dt(jd: float, tz_hours: float) -> datetime:
    y, m, d, h = swe.revjul(jd)
    base = datetime(y, m, d, tzinfo=timezone.utc) + timedelta(hours=h)
    return base.astimezone(timezone(timedelta(hours=tz_hours)))


def _sun_moon(jd: float) -> Tuple[float, float]:
    s = swe.calc_ut(jd, swe.SUN, _SID)[0][0]
    m = swe.calc_ut(jd, swe.MOON, _SID)[0][0]
    return s % 360.0, m % 360.0


def _elong(jd: float) -> float:
    s, m = _sun_moon(jd)
    return (m - s) % 360.0


def _moon(jd: float) -> float:
    return _sun_moon(jd)[1]


def _yoga_lon(jd: float) -> float:
    s, m = _sun_moon(jd)
    return (s + m) % 360.0


def _next_boundary(fn, jd: float, width: float, max_days: float = 2.0) -> float:
    """JD at which monotonically-increasing angle ``fn`` crosses its next multiple of ``width``."""
    v0 = fn(jd)
    target = (math.floor(v0 / width) + 1) * width
    unwrap = lambda v: v + 360.0 if v < v0 - 1e-9 else v  # noqa: E731
    lo, hi = jd, jd + 0.05
    while unwrap(fn(hi)) < target and hi - jd < max_days:
        lo, hi = hi, hi + 0.1
    for _ in range(40):
        mid = (lo + hi) / 2
        if unwrap(fn(mid)) < target:
            lo = mid
        else:
            hi = mid
    return hi


def _sunrise_sunset(day: date, lat: float, lon: float, tz_hours: float) -> Tuple[float, float, float]:
    """(sunrise_jd, sunset_jd, next_sunrise_jd) for the local civil date ``day``."""
    local_midnight = datetime(day.year, day.month, day.day, tzinfo=timezone(timedelta(hours=tz_hours)))
    jd0 = _jd(local_midnight)
    geo = (lon, lat, 0.0)
    flag = 0  # standard: upper limb + atmospheric refraction (as most panchangs)

    def rise(jd_start: float, what: int) -> float:
        try:
            res = swe.rise_trans(jd_start, swe.SUN, what | flag, geo, 1013.25, 15.0, swe.FLG_SWIEPH)
            if res[0] == 0:
                return res[1][0]
        except Exception:
            pass
        return jd_start + (0.25 if what == swe.CALC_RISE else 0.75)  # polar fallback: 06:00 / 18:00

    sr = rise(jd0, swe.CALC_RISE)
    ss = rise(sr, swe.CALC_SET)
    nsr = rise(ss, swe.CALC_RISE)
    return sr, ss, nsr


def _fmt(jd: float, tz: float) -> str:
    return _dt(jd, tz).strftime("%Y-%m-%d %H:%M")


def _hm(jd: float, tz: float) -> str:
    return _dt(jd, tz).strftime("%H:%M")


def tithi_label(t: int) -> Tuple[str, str]:
    """t in 1..30 -> (paksha, name)."""
    if t == 15:
        return "Shukla", "Purnima"
    if t == 30:
        return "Krishna", "Amavasya"
    return ("Shukla" if t < 15 else "Krishna"), TITHI_NAMES[(t - 1) % 15]


def karana_name(k: int) -> str:
    """k in 1..60 (half-tithi index over the lunar month)."""
    if k == 1:
        return "Kimstughna"
    if k >= 58:
        return {58: "Shakuni", 59: "Chatushpada", 60: "Naga"}[k]
    return MOVABLE_KARANAS[(k - 2) % 7]


# ----------------------------------------------------------------------------- panchang

def panchang(day: date, lat: float = 19.076, lon: float = 72.8777, tz_hours: float = 5.5,
             place: str = "Mumbai (NSE / BSE)") -> Dict:
    """Full panchang for local civil ``day`` at the observer, evaluated at local sunrise."""
    sr, ss, nsr = _sunrise_sunset(day, lat, lon, tz_hours)
    s_lon, m_lon = _sun_moon(sr)
    el = (m_lon - s_lon) % 360.0

    t_idx = int(el // 12) + 1
    paksha, t_name = tithi_label(t_idx)
    t_end = _next_boundary(_elong, sr, 12.0)

    n_idx = int(m_lon // NAK_W)
    n_end = _next_boundary(_moon, sr, NAK_W)
    pada = int((m_lon % NAK_W) / (NAK_W / 4)) + 1

    y_lon = (s_lon + m_lon) % 360.0
    y_idx = int(y_lon // NAK_W)
    y_end = _next_boundary(_yoga_lon, sr, NAK_W)

    k_idx = int(el // 6) + 1
    k_end = _next_boundary(_elong, sr, 6.0)
    k_name = karana_name(k_idx)

    wd = _dt(sr, tz_hours).weekday()
    vara, vara_lord = VARA[wd]
    part = (ss - sr) / 8.0

    def block(i: int) -> Dict:
        a = sr + (i - 1) * part
        return {"start": _hm(a, tz_hours), "end": _hm(a + part, tz_hours)}

    noon = (sr + ss) / 2
    abhijit = {"start": _hm(noon - (ss - sr) / 30, tz_hours), "end": _hm(noon + (ss - sr) / 30, tz_hours)}

    moon_sign = int(m_lon // 30)
    sun_sign = int(s_lon // 30)
    signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
             "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    nak_name = NAKSHATRAS[n_idx]
    pos_in_nak = (m_lon % NAK_W) / NAK_W
    gandanta = nak_name in GANDANTA_NAK and (pos_in_nak > 0.875 if nak_name in {"Ashlesha", "Jyeshtha", "Revati"}
                                            else pos_in_nak < 0.125)

    flags: List[str] = []
    if t_name in ("Amavasya", "Purnima", "Ekadashi"):
        flags.append(t_name)
    if k_name == "Vishti":
        flags.append("Vishti")
    if gandanta:
        flags.append("Gandanta")
    if YOGA_NAMES[y_idx] in INAUSPICIOUS_YOGAS:
        flags.append("BadYoga")

    tone = "caution" if any(f in ("Amavasya", "Vishti", "Gandanta") for f in flags) else (
        "mixed" if flags else "favourable")
    return {
        "date": day.isoformat(),
        "place": place, "lat": lat, "lon": lon, "tz_hours": tz_hours,
        "sunrise": _fmt(sr, tz_hours), "sunset": _fmt(ss, tz_hours), "next_sunrise": _fmt(nsr, tz_hours),
        "vara": {"name": vara, "lord": vara_lord, "weekday": _dt(sr, tz_hours).strftime("%A")},
        "tithi": {"index": t_idx, "paksha": paksha, "name": t_name, "label": f"{paksha} {t_name}",
                  "ends": _fmt(t_end, tz_hours), "elongation": round(el, 3)},
        "nakshatra": {"index": n_idx, "name": nak_name, "pada": pada, "ends": _fmt(n_end, tz_hours),
                      "lord": _NAK_LORDS[n_idx % 9]},
        "yoga": {"index": y_idx, "name": YOGA_NAMES[y_idx], "ends": _fmt(y_end, tz_hours),
                 "auspicious": YOGA_NAMES[y_idx] not in INAUSPICIOUS_YOGAS},
        "karana": {"index": k_idx, "name": k_name, "ends": _fmt(k_end, tz_hours)},
        "moon_sign": signs[moon_sign], "sun_sign": signs[sun_sign],
        "rahu_kaal": block(RAHU_KAAL[wd]), "yamaganda": block(YAMAGANDA[wd]), "gulika": block(GULIKA[wd]),
        "abhijit": abhijit,
        "flags": flags, "tone": tone,
        "notes": [TRADER_FOLKLORE[f] for f in flags],
        "plain_english": _plain_english(paksha, t_name, nak_name, YOGA_NAMES[y_idx], k_name, flags, wd),
    }


_NAK_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]


def _plain_english(paksha: str, tithi: str, nak: str, yoga: str, karana: str, flags: List[str],
                   wd: int) -> str:
    phase = ("the Moon is growing (Shukla paksha), which tradition reads as a building, "
             "accumulating phase" if paksha == "Shukla" else
             "the Moon is shrinking (Krishna paksha), which tradition reads as a releasing, "
             "profit-taking phase")
    s = f"Today is {tithi} and {phase}. The Moon is in {nak}; the yoga is {yoga} and the karana is {karana}. "
    if not flags:
        s += ("None of the classical warning markers is active, so tradition sees no special reason "
              "to stand aside. ")
    else:
        s += "Watch-outs: " + ", ".join(
            {"BadYoga": "an inauspicious yoga"}.get(f, f) for f in flags) + ". "
    s += ("Most traditional traders also skip opening new positions during Rahu Kaal. "
          "This is cultural context, not a trading signal.")
    return s


# ----------------------------------------------------------------------------- calendar

def _refine(key, a: float, b: float) -> float:
    """Bisect the instant in (a, b] at which ``key(jd)`` changes value (~1 minute precision)."""
    ka = key(a)
    for _ in range(12):
        m = (a + b) / 2
        if key(m) == ka:
            a = m
        else:
            b = m
    return b


def _events_between(jd_a: float, jd_b: float, tz: float) -> List[Dict]:
    """Sidereal sign ingresses, retrograde/direct stations and eclipses in [jd_a, jd_b)."""
    out: List[Dict] = []
    bodies = {"Mercury": swe.MERCURY, "Venus": swe.VENUS, "Mars": swe.MARS,
              "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Sun": swe.SUN}
    signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
             "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    step = 0.25
    for name, pid in bodies.items():
        prev = swe.calc_ut(jd_a, pid, _SID)[0]
        jd = jd_a + step
        while jd <= jd_b:
            cur = swe.calc_ut(jd, pid, _SID)[0]
            if int(prev[0] // 30) != int(cur[0] // 30):
                out.append({"jd": _refine(lambda j: int(swe.calc_ut(j, pid, _SID)[0][0] // 30), jd - step, jd), "kind": "ingress", "body": name,
                            "title": f"{name} enters {signs[int(cur[0] // 30)]}",
                            "meaning": f"{name}'s themes shift to a new sign; sector rotation narratives "
                                       f"often change around ingresses (folklore)."})
            if name != "Sun" and (prev[3] > 0) != (cur[3] > 0):
                retro = cur[3] < 0
                out.append({"jd": _refine(lambda j: swe.calc_ut(j, pid, _SID)[0][3] > 0, jd - step, jd),
                            "kind": "station", "body": name,
                            "title": f"{name} stations {'retrograde' if retro else 'direct'}",
                            "meaning": ("Stations are when a planet appears to stand still; traders "
                                        "who follow cycles watch for trend pauses or reversals "
                                        "within a few sessions (illustrative).")})
            prev = cur
            jd += step
    # eclipses
    for kind, fn in (("solar eclipse", swe.sol_eclipse_when_glob), ("lunar eclipse", swe.lun_eclipse_when)):
        try:
            jd = jd_a
            while True:
                res = fn(jd, swe.FLG_SWIEPH, 0, False)
                t = res[1][0]
                if t >= jd_b or t <= 0:
                    break
                out.append({"jd": t, "kind": "eclipse", "body": "Sun" if kind.startswith("solar") else "Moon",
                            "title": kind.title(),
                            "meaning": "Eclipses are the most-watched 'volatility windows' in astro-trading "
                                       "folklore; consider smaller size a few days either side."})
                jd = t + 10
        except Exception:
            pass
    for e in out:
        e["when"] = _fmt(e.pop("jd"), tz)
    out.sort(key=lambda e: e["when"])
    return out


def market_calendar(start: date, days: int = 30, lat: float = 19.076, lon: float = 72.8777,
                    tz_hours: float = 5.5, place: str = "Mumbai (NSE / BSE)") -> Dict:
    days = max(1, min(int(days), 120))
    rows = []
    for i in range(days):
        d = start + timedelta(days=i)
        p = panchang(d, lat, lon, tz_hours, place)
        rows.append({
            "date": p["date"], "weekday": p["vara"]["weekday"], "tithi": p["tithi"]["label"],
            "nakshatra": p["nakshatra"]["name"], "yoga": p["yoga"]["name"], "karana": p["karana"]["name"],
            "rahu_kaal": f'{p["rahu_kaal"]["start"]}-{p["rahu_kaal"]["end"]}',
            "flags": p["flags"], "tone": p["tone"], "is_weekend": d.weekday() >= 5,
        })
    tzinfo = timezone(timedelta(hours=tz_hours))
    jd_a = _jd(datetime(start.year, start.month, start.day, tzinfo=tzinfo))
    events = _events_between(jd_a, jd_a + days, tz_hours)
    counts = {"favourable": 0, "mixed": 0, "caution": 0}
    for r in rows:
        if not r["is_weekend"]:
            counts[r["tone"]] += 1
    return {
        "start": start.isoformat(), "days": days, "place": place, "tz_hours": tz_hours, "rows": rows, "events": events,
        "weekday_tone_counts": counts,
        "how_to_read": ("Green = no classical warning marker, amber = one mild marker, red = a "
                        "traditional 'stand aside' marker (Amavasya, Vishti karana or Gandanta). "
                        "Events list ingresses, retrograde/direct stations and eclipses. This is "
                        "cultural and astronomical context only, not financial advice."),
    }


def calendar_ics(cal: Dict) -> str:
    """Render the calendar as an iCalendar feed (all-day panchang rows + timed sky events)."""
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//AstroTrader//Panchang//EN", "CALSCALE:GREGORIAN"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for r in cal["rows"]:
        d = r["date"].replace("-", "")
        nd = (date.fromisoformat(r["date"]) + timedelta(days=1)).strftime("%Y%m%d")
        mark = {"favourable": "🟢", "mixed": "🟡", "caution": "🔴"}[r["tone"]]
        lines += ["BEGIN:VEVENT", f"UID:pan-{d}@astrotrader", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{d}", f"DTEND;VALUE=DATE:{nd}",
                  f"SUMMARY:{mark} {r['tithi']} · {r['nakshatra']}",
                  f"DESCRIPTION:Yoga {r['yoga']}\\, karana {r['karana']}\\, Rahu Kaal {r['rahu_kaal']}. "
                  f"Flags: {', '.join(r['flags']) or 'none'}. Cultural context only\\, not advice.",
                  "END:VEVENT"]
    for i, e in enumerate(cal["events"]):
        dt = datetime.strptime(e["when"], "%Y-%m-%d %H:%M").replace(
            tzinfo=timezone(timedelta(hours=cal.get("tz_hours", 5.5)))).astimezone(timezone.utc)
        s = dt.strftime("%Y%m%dT%H%M%SZ")
        en = (dt + timedelta(minutes=30)).strftime("%Y%m%dT%H%M%SZ")
        lines += ["BEGIN:VEVENT", f"UID:sky-{i}-{s}@astrotrader", f"DTSTAMP:{stamp}",
                  f"DTSTART:{s}", f"DTEND:{en}", f"SUMMARY:✨ {e['title']}",
                  f"DESCRIPTION:{e['meaning'].replace(',', chr(92) + ',')}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
