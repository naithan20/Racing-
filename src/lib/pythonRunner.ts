import "server-only";

/**
 * The single place Next.js shells out to the `racingedge_data` Python
 * package — every other spot in the app talks to the database via Prisma
 * only. Two call shapes, matching how `racingedge_data.import_pipeline`
 * itself is split:
 *
 * - `runImportJobCliSync` — a short-lived call (e.g. `--create-only`, a
 *   fast INSERT) whose stdout the caller needs immediately.
 * - `runImportJobCliDetached` / `runPythonModuleDetached` — spawns the
 *   actual (potentially long-running) work and returns without waiting
 *   for it. Progress is never read from this process's output — the
 *   Python job runner writes its own progress directly into `ImportJob`
 *   (see import_pipeline.py's module docstring), and the UI polls that
 *   table via Prisma. This is deliberate: a detached child's stdout is
 *   not a reliable channel to poll from a serverless/multi-instance
 *   Next.js deployment, but the SQLite row always is.
 *
 * **Why the interpreter path comes from `RACINGEDGE_PYTHON_BIN`, not a
 * `path.join(process.cwd(), ".venv", ...)` literal:** `.venv/bin/python`
 * is a symlink pointing at the system interpreter OUTSIDE the project
 * directory. Any statically-derivable reference to a path under `.venv`
 * in this module's source — as `spawn`'s executable argument, in a
 * `PATH`/`VIRTUAL_ENV` env value, wrapped in `fs.realpathSync`, built via
 * `path.join` or plain string concatenation — makes Next's Turbopack
 * build tracer treat `.venv` as a directory asset to walk and bundle,
 * and it panics the instant it hits that escaping symlink ("Symlink
 * [...] points out of the filesystem root"). This reproduces on every
 * `next build` in this repo; it isn't an edge case. Reading the fully-
 * resolved path from an environment variable at runtime is the only
 * approach that leaves nothing for the bundler to statically resolve —
 * see `.env.example` for the default local value.
 */

import { spawn, spawnSync } from "node:child_process";
import path from "node:path";

const PROJECT_ROOT = process.cwd();
const PYTHON_DIR = path.join(PROJECT_ROOT, "python");

function resolvePythonBin(): string {
  const configured = process.env.RACINGEDGE_PYTHON_BIN;
  if (!configured) {
    throw new Error(
      "RACINGEDGE_PYTHON_BIN is not set. Add it to .env (e.g. RACINGEDGE_PYTHON_BIN=.venv/bin/python) " +
        "— see .env.example. This is required so Next's build tracer never has to statically resolve " +
        "a path under .venv itself (see this module's docstring)."
    );
  }
  // turbopackIgnore: this is a deployment-controlled path from an env var,
  // never a project source file — nothing here should be traced/bundled.
  return path.isAbsolute(configured) ? configured : path.join(/*turbopackIgnore: true*/ PROJECT_ROOT, configured);
}

export interface PythonRunResult {
  ok: boolean;
  stdout: string;
  stderr: string;
}

/** Runs `python -m racingedge_data.cli.run_import_job <args>` and waits for it — only for fast, synchronous operations (job creation, mapping confirmation kickoff). */
export function runImportJobCliSync(args: string[], extraEnv: Record<string, string> = {}): PythonRunResult {
  const result = spawnSync(resolvePythonBin(), ["-m", "racingedge_data.cli.run_import_job", ...args], {
    cwd: PYTHON_DIR,
    env: { ...process.env, ...extraEnv },
    encoding: "utf-8",
    timeout: 60_000,
  });
  return {
    ok: result.status === 0,
    stdout: result.stdout ?? "",
    stderr: result.stderr ?? "",
  };
}

/** Spawns `python -m racingedge_data.cli.run_import_job <args>` as a detached background process and returns immediately — the actual import pipeline run. */
export function runImportJobCliDetached(args: string[], extraEnv: Record<string, string> = {}): void {
  runPythonModuleDetached("racingedge_data.cli.run_import_job", args, extraEnv);
}

/** Spawns `python -m <module> <args>` as a detached background process — the general form, used e.g. to trigger `racingedge_model.train` from the "Train Baseline Model" action. */
export function runPythonModuleDetached(module: string, args: string[] = [], extraEnv: Record<string, string> = {}): void {
  const child = spawn(resolvePythonBin(), ["-m", module, ...args], {
    cwd: PYTHON_DIR,
    env: { ...process.env, ...extraEnv },
    detached: true,
    stdio: "ignore",
  });
  child.unref();
}
