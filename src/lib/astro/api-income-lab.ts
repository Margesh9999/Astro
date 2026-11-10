/**
 * v1.7 Income Strategy Lab client: weekly premium-selling back-test, with and without each
 * astrological filter, each judged against skipping the same number of random weeks.
 */
export type LabStrategy = 'put_spread' | 'call_spread' | 'iron_condor';

export interface LabResult {
  key: string;
  label: string;
  weeks: number;
  weeks_traded: number;
  skipped: number;
  win_rate_pct: number | null;
  avg_week_on_margin_pct: number | null;
  worst_week_on_margin_pct: number | null;
  cagr_pct: number;
  max_drawdown_pct: number;
  sharpe: number;
  positive_months_pct: number | null;
  worst_month_pct: number | null;
  equity: { d: string; v: number }[];
  verdict: string;
  vs_random_pct?: number;
  skipped_avg_week_on_margin_pct?: number;
  skipped_win_rate_pct?: number;
}

export interface IncomeLab {
  success: boolean;
  error?: string;
  symbol: string;
  strategy: LabStrategy;
  strategy_label: string;
  risk_pct: number;
  from: string;
  to: string;
  vol_source: Record<string, number>;
  vol_index: string | null;
  results: LabResult[];
  summary: string;
  this_week: {
    spot: number;
    iv_pct: number;
    as_of: string;
    legs: Record<string, number>;
    credit_pts: number;
    max_loss_pts: number;
    flags: Record<string, boolean>;
    advice: string;
  };
  method: string;
  disclaimer: string;
}

export const incomeLabApi = {
  run: async (symbol: string, strategy: LabStrategy, risk: number): Promise<IncomeLab> => {
    const p = new URLSearchParams({ symbol, strategy, risk: String(risk) });
    const res = await fetch(`/api/astro/income-lab?${p}`, { cache: 'no-store' });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        detail = (await res.json()).detail ?? detail;
      } catch {
        /* keep status */
      }
      throw new Error(detail);
    }
    return res.json();
  },
};
