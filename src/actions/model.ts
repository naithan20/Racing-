"use server";

/** Triggers `racingedge_model.train` from the UI — Phase 3D's "Train Baseline
 * Model" post-import action. Deliberately requires an explicit user click
 * (never triggered automatically after an import completes) and is
 * fire-and-forget: training writes its own ModelVersion/DatasetVersion rows
 * directly, visible on /dashboard and /backtest once done, the same
 * "Python writes SQLite, Next.js reads it" pattern the import pipeline
 * uses. This does not track its own job/progress state — unlike an import
 * job, a completed training run is self-evident from a new ModelVersion
 * row appearing.
 */

import { runPythonModuleDetached } from "@/lib/pythonRunner";

export async function trainBaselineModelAction(featureProfile?: string): Promise<{ ok: boolean; message: string }> {
  const args: string[] = [];
  if (featureProfile) args.push("--feature-profile", featureProfile);

  runPythonModuleDetached("racingedge_model.train", args);

  return {
    ok: true,
    message: "Training started in the background — check the Model Performance Dashboard shortly for the new model version.",
  };
}
