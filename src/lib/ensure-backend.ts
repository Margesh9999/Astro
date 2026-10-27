/**
 * Ensures the AstroTrader FastAPI backend (uvicorn :8000) is running.
 * Called from the root server component on first request; the spawned
 * process becomes a child of the Next.js server so it persists.
 */
import { spawn, type ChildProcess } from 'child_process';
import { existsSync } from 'fs';
import path from 'path';

const BACKEND_PORT = 8000;

async function isBackendUp(): Promise<boolean> {
  try {
    const res = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/v1/health`, {
      signal: AbortSignal.timeout(1500),
    });
    return res.ok;
  } catch {
    return false;
  }
}

const g = globalThis as unknown as {
  __astroBackendSpawned?: boolean;
  __astroBackendChild?: ChildProcess;
};

function clearChild() {
  g.__astroBackendSpawned = false;
  g.__astroBackendChild = undefined;
}

function spawnBackend(): ChildProcess | null {
  const backendDir = path.join(process.cwd(), 'mini-services', 'astro-backend');
  const pythonBin = path.join(backendDir, 'venv', 'bin', 'python');
  if (!existsSync(pythonBin)) {
    console.warn('[astro-backend] venv python not found at', pythonBin);
    return null;
  }

  const child = spawn(
    pythonBin,
    ['-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', String(BACKEND_PORT)],
    {
      cwd: backendDir,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
    }
  );

  child.stdout?.on('data', (d: Buffer) => {
    const line = d.toString().trim();
    if (line) console.log(`[astro-backend] ${line}`);
  });
  child.stderr?.on('data', (d: Buffer) => {
    const line = d.toString().trim();
    if (line) console.error(`[astro-backend] ${line}`);
  });
  child.on('error', (err) => {
    console.error(`[astro-backend] spawn error: ${err.message}`);
    clearChild();
  });
  child.on('exit', (code) => {
    console.warn(`[astro-backend] exited with code ${code}`);
    clearChild();
  });

  g.__astroBackendSpawned = true;
  g.__astroBackendChild = child;
  return child;
}

function childAlive(): boolean {
  const c = g.__astroBackendChild;
  return !!c && !c.killed && c.exitCode === null && c.signalCode === null;
}

export async function ensureAstroBackend(): Promise<boolean> {
  // Fast path: already up (spawned by us, by dev.sh, or manually)
  if (await isBackendUp()) {
    g.__astroBackendSpawned = true;
    return true;
  }

  if (g.__astroBackendSpawned && childAlive()) {
    // We spawned it and the process is still alive; give it a few
    // seconds to bind the port.
    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 500));
      if (await isBackendUp()) return true;
    }
    return false;
  }

  // Not up and no live child — (re)spawn.
  if (g.__astroBackendSpawned && !childAlive()) {
    console.warn('[astro-backend] previous child is gone; respawning');
    clearChild();
  }

  const child = spawnBackend();
  if (!child) return false;

  // Wait for it to become healthy
  for (let i = 0; i < 30; i++) {
    await new Promise((r) => setTimeout(r, 500));
    if (await isBackendUp()) return true;
  }
  return false;
}
