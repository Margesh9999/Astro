/**
 * Shared planet & sign metadata for the pastel Vedic UI.
 */
export const SIGNS = [
  'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
  'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces',
];

export const SIGN_GLYPHS = ['♈', '♉', '♊', '♋', '♌', '♍', '♎', '♏', '♐', '♑', '♒', '♓'];

export const SIGN_SHORTS = ['Ar', 'Ta', 'Ge', 'Cn', 'Le', 'Vi', 'Li', 'Sc', 'Sg', 'Cp', 'Aq', 'Pi'];

/** Festival-pastel planet palette — tuned for the ivory canvas. */
export const PLANET_META: Record<string, { glyph: string; color: string }> = {
  Sun: { glyph: '☉', color: '#d9822b' },
  Moon: { glyph: '☽', color: '#86a69d' },
  Mercury: { glyph: '☿', color: '#6fa96f' },
  Venus: { glyph: '♀', color: '#d96f85' },
  Mars: { glyph: '♂', color: '#c9553f' },
  Jupiter: { glyph: '♃', color: '#db8a3a' },
  Saturn: { glyph: '♄', color: '#7a6a58' },
  Uranus: { glyph: '♅', color: '#4fa8a0' },
  Neptune: { glyph: '♆', color: '#5ca88f' },
  Pluto: { glyph: '♇', color: '#a5698f' },
  Rahu: { glyph: '☊', color: '#8b7bb8' },
  Ketu: { glyph: '☋', color: '#9a6b5c' },
  Lagna: { glyph: 'As', color: '#b0763a' },
  Ascendant: { glyph: 'As', color: '#b0763a' },
};

export function fmtDeg(deg: number, withMinutes = true) {
  const d = Math.floor(deg);
  const m = Math.round((deg - d) * 60);
  if (!withMinutes) return `${d}°`;
  return `${d}°${String(m === 60 ? 0 : m).padStart(2, '0')}'`;
}

// ───────────── T6: plain-English planet & house guides for popups ─────────────

export interface PlanetGuide {
  /** what this planet means in a birth chart / the sky, in one friendly line */
  meaning: string;
  /** market themes this planet rules */
  market: string;
  /** what to do when this planet is strong/active */
  action: string;
}

export const PLANET_GUIDES: Record<string, PlanetGuide> = {
  Sun: {
    meaning: 'Your ego, vitality and authority — how you lead and get recognised.',
    market: 'Government-linked stocks, energy, gold, large-cap "king" companies.',
    action: 'Sun days suit bold, visible decisions — but check the ego at the door.',
  },
  Moon: {
    meaning: 'Your emotions, habits and inner mood — how you feel safe.',
    market: 'FMCG, pharma, consumer staples, silver, anything people buy daily.',
    action: 'Moon days move with crowd sentiment — follow liquidity, avoid impulsive trades.',
  },
  Mercury: {
    meaning: 'Your analytical brain — communication, trade, numbers and speed.',
    market: 'IT, telecom, media, logistics, trading firms, edtech.',
    action: 'Mercury days are perfect for research, spreadsheets and calculated entries.',
  },
  Venus: {
    meaning: 'What you enjoy — beauty, comfort, love and the good life.',
    market: 'Luxury goods, autos, entertainment, financial services, textiles.',
    action: 'Venus days favour patient accumulation of quality names.',
  },
  Mars: {
    meaning: 'Your drive and aggression — energy, competition and courage.',
    market: 'Energy, metals, defence, real estate, cement — fast movers.',
    action: 'Mars days reward decisive momentum trades with tight stops.',
  },
  Jupiter: {
    meaning: 'Your wisdom and expansion — luck, ethics and long-term growth.',
    market: 'Banking, insurance, education, gold — the compounding sectors.',
    action: 'Jupiter days favour steady accumulation; think in years, not hours.',
  },
  Saturn: {
    meaning: 'Your discipline and limits — hard work, time and structure.',
    market: 'Infrastructure, mining, oil services, BFSI — slow and steady.',
    action: 'Saturn days reward systematic plans and punish shortcuts.',
  },
  Rahu: {
    meaning: 'Your obsession and innovation — unconventional appetite, foreign flavour.',
    market: 'Tech/AI, semiconductors, EV, crypto-adjacent, foreign listings.',
    action: 'Rahu days create manias — ride trends but always with an exit plan.',
  },
  Ketu: {
    meaning: 'Your detachment — where you release, research and go deep within.',
    market: 'Pharma research, wellness, niche technology.',
    action: 'Ketu days are for closing loose ends, not opening new positions.',
  },
  Lagna: {
    meaning: 'Your ascendant — the lens through which the world sees you.',
    market: 'Sets the overall tone of your personal trading style.',
    action: 'The Lagna sign colours every house meaning in your chart.',
  },
  Uranus: {
    meaning: 'Sudden shocks and breakthroughs — the disruptor.',
    market: 'Innovation, tech disruptions, volatility spikes.',
    action: 'Expect the unexpected on strong Uranus days.',
  },
  Neptune: {
    meaning: 'Dreams and illusions — inspiration or confusion.',
    market: 'Oil, chemicals, pharma, media narratives.',
    action: 'Verify facts twice — Neptune blurs reality.',
  },
  Pluto: {
    meaning: 'Deep transformation — power, control and rebirth.',
    market: 'Debt cycles, restructuring, hidden forces.',
    action: 'Long-wave regime changes show up here.',
  },
};

export const HOUSE_GUIDES: Record<number, string> = {
  1: 'Self, body, first impressions',
  2: 'Savings, speech, family wealth',
  3: 'Communication, courage, siblings',
  4: 'Home, property, emotional base',
  5: 'Speculation, children, creativity',
  6: 'Service, debt, health routines',
  7: 'Partnerships, contracts, the public',
  8: "Other people's money, insurance, research",
  9: 'Fortune, higher learning, long journeys',
  10: 'Career, status, public action',
  11: 'Gains, network, income streams',
  12: 'Foreign lands, expenses, letting go',
};

export const DIGNITY_GUIDES: Record<string, string> = {
  exalted: 'at maximum strength — the planet delivers its best',
  moolatrikona: 'in its power zone — very strong',
  'own sign': 'at home — comfortable and reliable',
  'friendly sign': 'among friends — supportive',
  neutral: 'neutral — neither helped nor harmed',
  debilitated: 'weakened — results come with struggle',
  'neutral node': 'the shadow node works in mysterious ways',
  reference: 'the chart reference point',
};
