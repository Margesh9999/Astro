/**
 * v1.5 Astrologer Signals client: public YouTube feeds of financial astrologers, tagged and
 * scored against real prices, plus grading of calls the user logs themselves.
 */
export type Direction = 'bullish' | 'bearish' | 'volatile' | 'neutral';

export interface TaggedVideo {
  video_id: string;
  title: string;
  published: string;
  url: string;
  views?: number | null;
  instruments: { symbol: string; label: string; inferred?: boolean }[];
  direction: Direction;
  score: number;
  status?: 'graded' | 'pending' | 'no data';
  ret_pct?: number;
  from?: string;
  to?: string;
  hit?: boolean | null;
  source_name?: string;
}

export interface TrackRecord {
  horizon_days: number;
  graded: number;
  hits: number;
  hit_rate: number | null;
  expected_by_chance: number | null;
  z?: number;
  verdict: string;
}

export interface SourceFeed {
  id: string;
  name: string;
  handle: string;
  url: string;
  focus: string;
  ok: boolean;
  error?: string;
  channel_title?: string;
  videos?: TaggedVideo[];
  track_record?: TrackRecord;
}

export interface Insights {
  count: number;
  directions?: Record<Direction, number>;
  lean?: string;
  instruments?: [string, number][];
  planets?: [string, number][];
  themes?: [string, number][];
  months?: [string, number][];
  summary: string;
}

export interface DiscoveredItem extends TaggedVideo {
  channel: string;
  channel_url: string;
  platform: 'YouTube' | 'Reddit';
  published_text?: string;
}

export interface Discover {
  success: boolean;
  items: DiscoveredItem[];
  insights: Insights;
  consensus: AstrologerFeed['consensus'];
  errors: string[];
  sources_searched: string[];
  note: string;
  disclaimer: string;
}

export interface AstrologerFeed {
  success: boolean;
  symbol: string;
  horizon_days: number;
  sources: SourceFeed[];
  consensus: {
    symbol: string;
    window_days: number;
    net: number;
    lean: string;
    calls: { title: string; url: string; published: string; direction: Direction; source?: string; weight: number }[];
  };
  insights?: Insights;
  method: string;
  disclaimer: string;
}

export interface LoggedCall {
  id: string;
  source: string;
  symbol: string;
  direction: Direction;
  start: string;
  end: string;
  note?: string;
  link?: string;
}
export interface ScoredCall extends LoggedCall {
  status: string;
  ret_pct?: number;
  hit?: boolean | null;
  max_move_pct?: number;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const d = await res.json();
      if (d?.detail) detail = typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const astrologersApi = {
  feed: (handles: string[], symbol: string, horizon = 5) =>
    fetch(
      `/api/astro/astrologers/feed?${new URLSearchParams({ handles: handles.join(','), symbol, horizon: String(horizon) })}`,
      { cache: 'no-store' },
    ).then((r) => json<AstrologerFeed>(r)),
  discover: (symbol: string) =>
    fetch(`/api/astro/astrologers/discover?${new URLSearchParams({ symbol })}`, { cache: 'no-store' }).then((r) =>
      json<Discover>(r),
    ),
  score: (calls: LoggedCall[]) =>
    fetch('/api/astro/astrologers/score', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ calls }),
    }).then((r) => json<{ calls: ScoredCall[]; by_source: Record<string, { graded: number; hits: number; hit_rate: number }> }>(r)),
};
