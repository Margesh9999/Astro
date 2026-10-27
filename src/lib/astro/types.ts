export interface PlanetaryPosition {
  name?: string;
  longitude: number;
  latitude?: number;
  distance?: number;
  speed_longitude?: number;
  speed_latitude?: number;
  speed_distance?: number;
  sign: string;
  sign_number: number;
  degree_within_sign: number;
  is_retrograde: boolean;
  nakshatra?: string;
  nakshatra_index?: number;
  pada?: number;
  house?: number;
  dignity?: string;
  dignity_score?: number;
  tropical_longitude?: number;
  ayanamsa?: number;
}

export interface Aspect {
  aspect: string;
  angle_exact: number;
  angle_actual: number;
  orb_used: number;
  planet1: string;
  planet2: string;
  is_applying: boolean;
  strength: number;
}

export interface SparkPoint {
  date: string;
  close: number;
  volume: number;
}

export interface MarketQuote {
  symbol: string;
  name: string;
  currency: string;
  price: number;
  previous_close: number;
  change: number;
  change_percent: number;
  day_high: number;
  day_low: number;
  open: number;
  volume: number;
  timestamp: string;
  sparkline: SparkPoint[];
}

export interface SymbolInfo {
  symbol: string;
  name: string;
  market: string;
  flag: string;
}

export interface TrainResult {
  success: boolean;
  symbol: string;
  samples: number;
  date_range: string;
  linear_r2: number;
  rf_r2: number;
  feature_importance: Record<string, number>;
}

export interface PredictResult {
  success: boolean;
  symbol: string;
  current_price: number;
  prediction_days: number;
  dates: string[];
  daily_returns: number[];
  cumulative_returns: number[];
  projected_prices: number[];
  model_used: string;
  vedic: boolean;
}

export interface StrategyMetrics {
  total_return: number;
  annual_return: number;
  sharpe: number;
  max_drawdown: number;
  win_rate?: number;
}

export interface BacktestResult {
  success: boolean;
  symbol: string;
  vedic: boolean;
  train_samples: number;
  test_samples: number;
  test_range: string;
  strategy: StrategyMetrics;
  buy_hold: StrategyMetrics;
  equity_curve: Array<{ date: string; strategy: number; buy_hold: number }>;
}

export interface AstroEvent {
  date: string;
  event: string;
  type: string;
  planets: string[];
  significance: string;
  description: string;
}

export interface PlanetaryResponse {
  date: string;
  julian_day: number;
  ayanamsa: number | null;
  vedic: boolean;
  planetary_positions: Record<string, PlanetaryPosition>;
  aspects: Aspect[];
}

export interface NatalResponse {
  success: boolean;
  native: string;
  birth: string;
  ayanamsa: number;
  ayanamsa_mode: string;
  positions: Record<string, PlanetaryPosition>;
}

// ---------------------------------------------------------------------------
// Suri-inspired astro-signal engine
// ---------------------------------------------------------------------------
export interface SuriMood {
  date: string;
  mood_index: number;
  mood_label: string;
  phase_angle: number;
  lunar: string;
  retrogrades: number;
  components: Record<string, number>;
}

export interface SuriScore {
  date: string;
  reversal_score?: number;
  volatility_score?: number;
  drivers: Array<{ type?: string; detail: string; weight: number }>;
}

export interface SuriTimingAlert {
  date: string;
  kind: string;
  title: string;
  note: string;
  strength: number;
  score?: number;
}

export interface SuriFiveDayRange {
  symbol: string;
  spot: number;
  horizon_days: number;
  ewma_daily_vol: number;
  horizon_sigma: number;
  astro_multiplier: number;
  bands: Record<string, { high: number; low: number }>;
  support: number;
  resistance: number;
}

export interface SuriComposite {
  symbol: string;
  date: string;
  technical_score: number;
  astro_score: number;
  composite: number;
  zone: string;
  rsi14: number;
  trend_pct: number;
  vol20_annualised: number;
  vol_percentile: number;
  mood: SuriMood;
}

export interface AstroSignalResponse {
  success: boolean;
  symbol: string;
  date: string;
  spot: number;
  mood: SuriMood;
  reversal: SuriScore;
  volatility: SuriScore;
  timing_alerts: SuriTimingAlert[];
  five_day_range: SuriFiveDayRange;
  composite: SuriComposite;
  inspired_by: string;
  disclaimer: string;
}

// ---------------------------------------------------------------------------
// Institutional quant analytics
// ---------------------------------------------------------------------------
export interface QuantStats {
  total_return: number | null;
  cagr: number | null;
  ann_vol: number | null;
  sharpe: number | null;
  sortino: number | null;
  calmar: number | null;
  max_drawdown: number | null;
  max_dd_length_days: number;
  hit_rate: number | null;
  best_day: number | null;
  worst_day: number | null;
  skew: number | null;
  kurtosis: number | null;
}

export interface QuantStatsResponse {
  success: boolean;
  symbol: string;
  stats: QuantStats;
  drawdown: Array<{ date: string; dd_pct: number }>;
  monthly: { months: Array<Record<string, number | null>> };
  observations: number;
}

export interface QuantRiskResponse {
  success: boolean;
  symbol: string;
  risk: {
    confidence: number;
    var_hist_pct: number;
    cvar_hist_pct: number;
    var_param_pct: number;
    cvar_param_pct: number;
    var_hist_usd: number;
    cvar_hist_usd: number;
    position_value: number;
    observations: number;
  };
}

export interface OptionsPriceResponse {
  success: boolean;
  model: string;
  price: number;
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  rho?: number;
  stderr?: number;
  paths?: number;
  heston_price?: number;
  effective_vol?: number;
  inputs: Record<string, number | string>;
}

export interface SabrResponse {
  success: boolean;
  forward: number;
  T: number;
  atm_vol: number;
  beta: number;
  rho: number;
  nu: number;
  alpha: number;
  smile: Array<{ moneyness: number; strike: number; vol: number }>;
}

// ---------------------------------------------------------------------------
// Instrument universe (searchable picker)
// ---------------------------------------------------------------------------
export interface UniverseEntry {
  symbol: string;
  name: string;
  market: string;
  market_label: string;
  flag: string;
  type: string;
  type_label: string;
  sector: string;
  currency: string;
  has_options: boolean;
}

export interface UniverseMeta {
  total: number;
  options_enabled: number;
  markets: Array<{ market: string; label: string; flag: string; count: number }>;
  types: Array<{ type: string; label: string; count: number }>;
}

// ---------------------------------------------------------------------------
// Institutional Options Lab
// ---------------------------------------------------------------------------
export interface OptionQuote {
  mid: number;
  bid: number;
  ask: number;
  iv: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  volume: number;
  open_interest: number;
  tradable: boolean;
  quoted: boolean;
}

export interface OptionChainRow {
  strike: number;
  moneyness: number;
  call: OptionQuote;
  put: OptionQuote;
}

export interface OptionExpirationsResponse {
  success: boolean;
  symbol: string;
  spot: number | null;
  currency: string;
  atm_vol: number | null;
  expirations: string[];
  dte: Array<number | null>;
  risk_free: number;
}

export interface OptionChainResponse {
  success: boolean;
  symbol: string;
  expiry: string;
  dte: number;
  spot: number;
  currency: string;
  atm_vol: number;
  div_yield: number;
  risk_free: number;
  source: 'live' | 'synthetic';
  rows: OptionChainRow[];
  disclaimer: string;
}

export interface StrategyMeta {
  key: string;
  name: string;
  view: string;
  risk: string;
  complexity: string;
  income?: boolean;
  two_expiries?: boolean;
  desc: string;
  defaults: Record<string, number>;
}

export interface StrategyLeg {
  action: 'buy' | 'sell';
  cp: 'call' | 'put' | 'stock';
  strike: number;
  expiry: string;
  qty: number;
  entry: number;
  bid: number;
  ask: number;
  iv: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  signed: number;
}

export interface ScenarioRow {
  spot_pct: number;
  [key: string]: number;
}

export interface StrategyAnalysis {
  success: boolean;
  symbol: string;
  strategy: string;
  strategy_name: string;
  view: string;
  risk_class: string;
  complexity: string;
  spot: number;
  currency: string;
  expiry: string;
  expiry_far: string | null;
  dte: number;
  qty: number;
  legs: StrategyLeg[];
  net_credit: number;
  net_debit: number;
  stock_notional: number;
  capital_required: number;
  margin_basis: string;
  max_profit: number | null;
  max_loss: number | null;
  max_profit_unlimited: boolean;
  max_loss_unlimited: boolean;
  breakevens: number[];
  pop: number;
  prob_max_loss: number;
  expected_pl: number;
  net_greeks: { delta: number; gamma: number; theta: number; vega: number };
  premium_per_week: number;
  theta_per_day: number;
  roc_cycle: number | null;
  roc_annualised: number | null;
  scenarios: ScenarioRow[];
  payoff_curve: Array<{ spot: number; pl: number }>;
  atm_vol: number;
  chain_source: 'live' | 'synthetic';
  exit_dte: number;
  expirations_available?: string[];
  disclaimer: string;
}

export interface IncomeTicket {
  underlying: string;
  strategy: string;
  strategy_name: string;
  expiry: string;
  dte: number;
  qty: number;
  fits_allocation: boolean;
  legs: Array<{ action: string; cp: string; strike: number; entry: number }>;
  net_credit: number;
  credit_per_unit: number;
  margin_per_unit: number;
  capital_required: number;
  gross_premium_capture_weekly: number;
  weekly_premium: number;
  pop: number;
  max_loss: number | null;
  currency: string;
  chain_source: 'live' | 'synthetic';
  note: string;
}

export interface IncomePlanResponse {
  success: boolean;
  inputs: { capital: number; currency: string; target_weekly: number; focus: string; gbpusd: number };
  annual_target: number;
  verdict: 'achievable' | 'stretch' | 'below_base_regime';
  required_capital_total_base: number;
  capital_table: Array<{
    key: string; label: string; basis: string; dte: string; risk: string;
    yield_range: { conservative: number; base: number; aggressive: number };
    capital_required: { conservative: number | null; base: number | null; aggressive: number | null };
  }>;
  ladder: Array<{
    key: string; label: string; weight: number; allocation: number;
    target_weekly: number; yield_base: number; ticket: IncomeTicket | null;
  }>;
  est_weekly_from_ladder_yields: number;
  gross_premium_capture_weekly_gbp: number;
  gross_premium_capture_note: string;
  max_sustainable_weekly: number;
  notes: string[];
  disclaimer: string;
}

// ───────────────────────── T1–T13 enhancement types ─────────────────────────

export interface JatakaPlace { name: string; lat: number; lon: number; tz: number; }

export interface JatakaPosition {
  longitude: number; sign: string; sign_number: number; degree_within_sign: number;
  is_retrograde: boolean; nakshatra: string; nakshatra_index: number; pada: number;
  house: number; dignity: string; dignity_score: number;
}

export interface JatakaDashaMD {
  lord: string; glyph: string; start: string; end: string; years: number;
  antardashas: { lord: string; glyph: string; start: string; end: string; years: number }[];
}

export interface JatakaIncomeForecast {
  strategy: string; capital: number; dasha_factor: number;
  weekly: { low: number; mid: number; high: number };
  monthly: { low: number; mid: number; high: number };
  annual: { low: number; mid: number; high: number };
  target_weekly: number; target_feasible: boolean;
  target_capital_needed: { at_mid_yield: number; at_low_yield: number };
  honesty: string;
}

export interface JatakaLifetimeStage {
  lord: string; age_from: number; age_to: number; start: string; end: string;
  wealth_index: number; phase: string; note: string;
}

/* ── Astro Analysis master-guide pack (BPHS + Jaimini + Ashtakvarga + KP + Yogini) ── */
export interface AstroVerdict {
  score: number; headline: string; reasons: string[]; risks: string[]; plain: string;
}
export interface AstroYoga {
  name: string; category: string; planets: string[]; meaning: string; strength: string;
}
export interface AstroAnalysisPack {
  vargas: {
    planets: Record<string, { vargas: Record<string, { sign: string; dignity: string }> }>;
    info: Record<string, { title: string; meaning: string }>;
    navamsa_focus: string; dasamsa_focus: string; plain: string;
  };
  jaimini: {
    karakas: { key: string; label: string; planet: string; degree: number; sign: string; house: number; money_meaning: string; plain: string }[];
    atmakaraka: string; karakamsa_sign: string; arudha_lagna_sign: string; upapada_sign: string; plain: string;
  };
  avasthas: { planets: Record<string, { state: string; capacity: string; sign: string; degree: number }>; plain: string };
  yogas: { found: AstroYoga[]; plain: string };
  shadbala: {
    planets: Record<string, { rupas: number; required: number; verdict: string; components: Record<string, number> }>;
    ranked: [string, number][]; day_lord: string; hora_lord: string; plain: string;
  };
  bhavabala: {
    houses: { house: number; sign: string; lord: string; score: number; bindus: number; wealth_flag: boolean }[];
    ranked: { house: number; sign: string; lord: string; score: number; bindus: number; wealth_flag: boolean }[];
    strongest_house: { house: number; sign: string; score: number };
    plain: string;
  };
  ashtakvarga: {
    sav: number[]; sav_total: number; sav_reduced: number[]; prastara_total: number;
    wealth: Record<string, { bindus: number; sign: string; status: string }>;
    strongest_signs: { sign: string; bindus: number }[];
    saturn_bav: number[]; jupiter_bav: number[];
    plain: string;
  };
  kp: {
    cusps: { cusp: number; sign: string; degree: number; star_lord: string; sub_lord: string; cusp_name: string }[];
    planets: { planet: string; sign: string; star_lord: string; sub_lord: string }[];
    ruling_planets: string[]; asc_star_lord: string; asc_sub_lord: string; day_lord: string; plain: string;
  };
  yogini: {
    direction: string; first_yogini: string; balance_years: number;
    periods: { yogini: string; lord: string; start: string; end: string; years: number }[];
    current: { yogini: string; lord: string; sub_yogini: string; sub_lord: string; money_note: string };
    plain: string;
  };
  karma_vipaka: {
    nakshatra: string; deity: string; symbol: string; theme: string;
    lord: string; lord_house: number; lord_sign: string; plain: string;
  };
  transits: {
    rows: { planet: string; sign: string; house: number; sav_bindus: number; own_bindus: number | null; verdict: string; plain: string }[];
    plain: string;
  };
  houses: {
    house: number; sign: string; lord: string; lord_house: number; occupants: string[];
    bindus: number; score: number; wealth_flag: boolean; plain: string;
  }[];
  verdict: AstroVerdict;
  planetary_notes: Record<string, string>;
  blueprint: {
    style: string;
    allocation: { market: string; weight_pct: number; driven_by: string }[];
    timing_windows: { period: string; end: string; note: string }[];
    next_mahadasha: { lord: string; start: string } | null;
    income: {
      weekly: { low: number; mid: number; high: number };
      monthly: { low: number; mid: number; high: number };
      annual: { low: number; mid: number; high: number };
      capital: number; target_weekly: number; target_feasible: boolean;
      capital_needed: { at_mid_yield: number; at_low_yield: number };
    };
    risk_flags: string[];
    remedies: { planet: string; practice: string }[];
    plan: { window: string; action: string }[];
    plain: string;
  };
}

export interface JatakaReport {
  success: boolean;
  birth: { name: string; date: string; time: string; place: string; lat: number; lon: number; tz: number; utc: string };
  ayanamsa_mode: string;
  ayanamsa?: number;
  lagna_sign: number;
  positions: Record<string, JatakaPosition>;
  strengths: { scores: Record<string, number>; notes: Record<string, string>; ranked: [string, number][] };
  dasha_tree: {
    first_lord: string; balance_years: number; moon_nakshatra_index: number; pada: number;
    mahadashas: JatakaDashaMD[];
  };
  current_dasha: {
    mahadasha: string | null; antardasha: string | null; pratyantardasha: string | null;
    md_start: string | null; md_end: string | null; ad_start: string | null; ad_end: string | null;
    interpretation: { headline: string; detail: string; md_theme: string; ad_theme: string };
  };
  market_recommendations: {
    allocation: { market: string; weight_pct: number; driven_by: string }[];
    sectors: { sector: string; weight_pct: number }[];
    strategies: { key: string; label: string; desc: string; fit_score: number }[];
    rationale: string;
  };
  income_forecast: JatakaIncomeForecast;
  lifetime_wealth: { stages: JatakaLifetimeStage[]; peak: JatakaLifetimeStage; headline: string };
  transits_today: {
    transits: Record<string, { sign: string; degree: number; nakshatra: string }>;
    activations: { transit: string; natal: string; separation: number; meaning: string }[];
  };
  synthesis: {
    natal_headline: string;
    current_dasha: { headline: string; detail: string };
    transit_activations: { transit: string; natal: string; separation: number; meaning: string }[];
    market_fit: JatakaReport['market_recommendations'];
    income: JatakaIncomeForecast;
    plan: { window: string; action: string }[];
    bottom_line: string;
  };
  verdict?: AstroVerdict;
  planetary_notes?: Record<string, string>;
  astro_analysis?: AstroAnalysisPack;
}

export interface AnalyticsPack {
  success: boolean;
  symbol: string;
  history_days: number;
  start: string;
  price: {
    series: { dates: string[]; close: number[]; sma20: (number | null)[]; sma50: (number | null)[]; sma200: (number | null)[] };
    interpretation: string;
  };
  drawdown: { series: { dates: string[]; dd: number[] }; current: number; max: number; interpretation: string };
  volatility: { series: { dates: string[]; vol: (number | null)[] }; now_pct: number; median_pct: number; interpretation: string };
  rsi: { series: { dates: string[]; rsi: (number | null)[] }; now: number; interpretation: string };
  heatmap: { years: number[]; months: number[]; values: (number | null)[][]; interpretation: string };
  performance: Record<string, number>;
  seasonality: { by_month: number[]; best_month: string; worst_month: string; best_month_ever: string; worst_month_ever: string };
  // ── round-3 extensions (optional for backward safety) ──
  macd?: { series: { dates: string[]; macd: (number | null)[]; signal: (number | null)[]; hist: (number | null)[] }; macd_now: number; signal_now: number; hist_now: number; interpretation: string };
  bollinger?: { series: { dates: string[]; close: number[]; upper: (number | null)[]; mid: (number | null)[]; lower: (number | null)[] }; upper_now: number; lower_now: number; pct_b: number; interpretation: string };
  stochastic?: { series: { dates: string[]; k: (number | null)[]; d: (number | null)[] }; k_now: number; d_now: number; interpretation: string };
  atr?: { series: { dates: string[]; atr_pct: (number | null)[] }; now_pct: number; interpretation: string };
  obv?: { series: { dates: string[]; obv: number[] }; trend_20d: string; interpretation: string };
  rolling_sharpe?: { series: { dates: string[]; sharpe: (number | null)[] }; now: number; interpretation: string };
  distribution?: { bins: { center: number; count: number }[]; sigma_pct: number; var95_daily_pct: number; best_day_pct: number; worst_day_pct: number; interpretation: string };
  memory?: { acf: { lag: number; value: number }[]; acf1: number; hurst: number; regime: string; interpretation: string };
  correlations?: { pairs: { symbol: string; name: string; corr: number }[]; matrix: { symbols: string[]; values: (number | null)[][] }; observation_days: number; interpretation: string };
  forecast?: {
    mc?: { dates: string[]; p5: number[]; p25: number[]; p50: number[]; p75: number[]; p95: number[]; last: number; prob_up_1w: number; prob_up_1m: number; expected_1m_pct: number; range_low_1w: number; range_high_1w: number; range_low_1m: number; range_high_1m: number; paths: number; days: number; method: string };
    signal: { score: number; label: string; pillars: { name: string; reading: string; stance: string; weight: number }[]; headline: string; n_bull: number; n_bear: number };
    levels: { level: string; value: number }[];
    invalidation: string;
    bull_case: string;
    bear_case: string;
    analogs?: { count: number; code: number; description: string; interpretation: string; '5d'?: AnalogStat; '10d'?: AnalogStat; '21d'?: AnalogStat };
    horizons: { horizon: string; bias: string; range_low: number; range_high: number; note: string }[];
    forecast_interpretation: string;
  };
}

export interface AnalogStat {
  count: number; hit_rate: number; mean_pct: number; median_pct: number; best_pct: number; worst_pct: number;
}

export interface ForecastEvent extends AstroEvent { meaning: string; }

export interface EventsForecast {
  success: boolean; symbol: string; symbol_name: string; trend: string; vol_state: string;
  days: number; events: ForecastEvent[]; count: number;
}

export interface SuriCycles {
  success: boolean; symbol: string; date: string; spot: number;
  lunar_journey: { date: string; angle: number; phase: string; note: string }[];
  ingresses: { date: string; planet: string; into: string }[];
  stations: { date: string; planet: string; event: string; meaning: string }[];
  playbook: string;
  mood: SuriMood; composite: SuriComposite; five_day_range: SuriFiveDayRange;
  timing_alerts: SuriTimingAlert[];
}

export interface AgentsAnalysis {
  success: boolean; symbol: string; symbol_name: string;
  agents: { agent: string; role: string; stance: string; view: string }[];
  manager: { verdict: string; score: number; view: string };
  disclaimer: string;
}

export interface ConceptRepo {
  repo: string; url: string;
  concepts: { name: string; status: 'implemented' | 'partial' | 'reference'; where: string; meaning: string }[];
}

export interface ConceptsResponse {
  success: boolean;
  summary: { repos: number; concepts: number; implemented: number; partial: number; reference: number; coverage_pct: number };
  repos: ConceptRepo[];
}

export interface ZooLeaderboardEntry {
  model: string; cv_r2: number; cv_r2_folds: number[]; note: string;
}

export interface ZooTrainResult {
  success: boolean;
  status?: string;
  stage?: string;
  progress?: number;
  error?: string;
  symbol?: string;
  mode?: string;
  samples?: number;
  history_start?: string;
  history_end?: string;
  years_covered?: number;
  zoo?: {
    leaderboard: ZooLeaderboardEntry[];
    best_model: string;
    best_cv_r2: number;
    feature_importance: { feature: string; importance: number }[];
    analysis: string;
    samples: number;
  };
}
