import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Phase 3D: src/lib/pythonRunner.ts spawns the project's Python venv
  // interpreter (`.venv/bin/python`) to run the racingedge_data import
  // pipeline. `.venv/bin/python` is a symlink pointing at the system
  // interpreter OUTSIDE the project directory, and Next's output-file
  // tracer (which normally bundles files referenced by spawn()/readFile()
  // calls for serverless deployment) panics trying to resolve it. Nothing
  // under `.venv` needs to be traced/bundled — it's not part of the
  // Next.js server bundle, it's invoked as a separate OS process — so
  // excluding it here is correct, not just a workaround.
  outputFileTracingExcludes: {
    "*": [".venv/**"],
  },
};

export default nextConfig;
