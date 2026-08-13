import { MODEL_NOT_CONFIGURED_LABEL } from "@/models/types";

/** Consistent placeholder for any field the future probability model will populate. */
export function NotConfigured({ compact = false }: { compact?: boolean }) {
  return (
    <span className={compact ? "text-xs text-text-muted" : "text-sm text-text-muted"} title={MODEL_NOT_CONFIGURED_LABEL}>
      {compact ? "—" : MODEL_NOT_CONFIGURED_LABEL}
    </span>
  );
}
