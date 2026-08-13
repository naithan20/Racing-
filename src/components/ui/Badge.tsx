import { type ReactNode } from "react";
import clsx from "clsx";

type Tone = "neutral" | "positive" | "negative" | "warning" | "accent";

const TONE_CLASSES: Record<Tone, string> = {
  neutral: "bg-bg-hover text-text-secondary",
  positive: "bg-positive-soft text-positive",
  negative: "bg-negative-soft text-negative",
  warning: "bg-warning-soft text-warning",
  accent: "bg-accent-soft text-accent",
};

export function Badge({ children, tone = "neutral", className }: { children: ReactNode; tone?: Tone; className?: string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium leading-none",
        TONE_CLASSES[tone],
        className
      )}
    >
      {children}
    </span>
  );
}

/** Renders a signed value edge with automatic positive/negative tone. */
export function ValueEdgeBadge({ value }: { value: number | null }) {
  if (value === null) return <span className="text-xs text-text-muted">—</span>;
  const tone: Tone = value > 0 ? "positive" : value < 0 ? "negative" : "neutral";
  const pct = (value * 100).toFixed(1);
  const sign = value > 0 ? "+" : "";
  return (
    <Badge tone={tone} className="font-tabular">
      {sign}
      {pct}%
    </Badge>
  );
}

/** Confidence is a separate concept from probability — rendered distinctly. */
export function ConfidenceBadge({ value }: { value: number | null }) {
  if (value === null) return <span className="text-xs text-text-muted">—</span>;
  const tone: Tone = value >= 0.66 ? "accent" : value >= 0.33 ? "neutral" : "warning";
  return (
    <Badge tone={tone} className="font-tabular">
      {(value * 100).toFixed(0)}%
    </Badge>
  );
}
