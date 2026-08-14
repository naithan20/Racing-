/**
 * Dataset size labels — Phase 3C section 16: preferred 100,000+ runners,
 * minimum useful 25,000+. Purely descriptive of size; never a claim about
 * model performance ("no model should be described as proven profitable").
 */
export type DatasetLevel = "EXPERIMENTAL" | "RESEARCH" | "LARGE_RESEARCH";

export function classifyDatasetLevel(runnerCount: number): DatasetLevel {
  if (runnerCount >= 100_000) return "LARGE_RESEARCH";
  if (runnerCount >= 25_000) return "RESEARCH";
  return "EXPERIMENTAL";
}

export function datasetLevelLabel(level: DatasetLevel): string {
  switch (level) {
    case "LARGE_RESEARCH":
      return "Large research";
    case "RESEARCH":
      return "Research";
    case "EXPERIMENTAL":
      return "Experimental";
  }
}
