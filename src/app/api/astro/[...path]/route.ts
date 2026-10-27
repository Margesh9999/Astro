import { NextRequest, NextResponse } from 'next/server';

/**
 * Same-origin proxy to the AstroTrader FastAPI backend on :8000.
 * GET /api/astro/<path>?<query>  ->  http://127.0.0.1:8000/api/v1/<path>?<query>
 * POST works the same way with a JSON body.
 */
const BACKEND = 'http://127.0.0.1:8000/api/v1';

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const search = new URLSearchParams(req.nextUrl.searchParams);
  search.delete('XTransformPort'); // gateway artifact — backend doesn't need it
  const qs = search.toString();
  const url = `${BACKEND}/${path.map(encodeURIComponent).join('/')}${qs ? `?${qs}` : ''}`;

  const method = req.method.toUpperCase();
  const init: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store',
    signal: AbortSignal.timeout(180_000), // training/backtest can take a while
  };
  if (method !== 'GET' && method !== 'HEAD') {
    init.body = await req.text();
  }

  try {
    const res = await fetch(url, init);
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: {
        'Content-Type': res.headers.get('content-type') ?? 'application/json',
        'Cache-Control': 'no-store',
      },
    });
  } catch (e) {
    return NextResponse.json(
      { detail: `Backend unreachable: ${e instanceof Error ? e.message : String(e)}` },
      { status: 502 },
    );
  }
}

export { proxy as GET, proxy as POST };
