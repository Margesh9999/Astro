import { ensureAstroBackend } from '@/lib/ensure-backend';
import { AstroDashboard } from '@/components/astro/astro-dashboard';

export const dynamic = 'force-dynamic';

export default async function Home() {
  // Boot the FastAPI mini-service (child of the Next server) before first render
  await ensureAstroBackend().catch((e) => {
    console.error('[astro-backend] boot check failed:', e);
  });

  return <AstroDashboard />;
}
