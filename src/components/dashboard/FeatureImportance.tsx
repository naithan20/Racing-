interface ImportanceItem {
  feature: string;
  importance?: number;
  importance_normalized?: number;
  coefficient?: number;
  abs_coefficient?: number;
}

export function FeatureImportance({ items }: { items: ImportanceItem[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-text-muted">No feature importance recorded for this model version.</p>;
  }

  const top = items.slice(0, 15);
  const maxValue = Math.max(...top.map((i) => Math.abs(i.importance_normalized ?? i.coefficient ?? i.importance ?? 0)), 1e-9);

  return (
    <div className="flex flex-col gap-1.5">
      {top.map((item) => {
        const value = item.importance_normalized ?? item.coefficient ?? item.importance ?? 0;
        const widthPct = (Math.abs(value) / maxValue) * 100;
        const isNegative = value < 0;
        return (
          <div key={item.feature} className="flex items-center gap-2 text-xs">
            <span className="w-56 shrink-0 truncate text-text-secondary" title={item.feature}>
              {item.feature}
            </span>
            <div className="h-3 flex-1 rounded bg-bg-hover">
              <div
                className={`h-3 rounded ${isNegative ? "bg-negative" : "bg-accent"}`}
                style={{ width: `${Math.max(widthPct, 2)}%` }}
              />
            </div>
            <span className="w-16 shrink-0 text-right font-tabular text-text-muted">{value.toFixed(3)}</span>
          </div>
        );
      })}
      <p className="mt-2 text-xs text-text-muted">
        Model association / importance, not causal effect.
      </p>
    </div>
  );
}
