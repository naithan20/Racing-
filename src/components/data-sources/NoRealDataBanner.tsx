import Link from "next/link";

/** First-run onboarding — Phase 3D section 10. Shown whenever there is no REAL race data yet, pointing straight at the source selector rather than a terminal command. */
export function NoRealDataBanner() {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-accent/40 bg-accent-soft p-4">
      <div>
        <p className="text-sm font-medium text-text-primary">RacingEdge needs historical racing data.</p>
        <p className="mt-0.5 text-xs text-text-secondary">
          Every model here is currently trained on synthetic/sample data — connect a free source to start building a real dataset.
        </p>
      </div>
      <Link
        href="/data-sources"
        className="shrink-0 rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
      >
        Add Free Racing Data
      </Link>
    </div>
  );
}
