"use client";

import { useRouter } from "next/navigation";

function shiftDate(dateValue: string, days: number): string {
  const d = new Date(`${dateValue}T00:00:00`);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export function DateNav({ dateValue }: { dateValue: string }) {
  const router = useRouter();

  const goTo = (value: string) => router.push(`/races?date=${value}`);

  return (
    <div className="flex items-center gap-1 rounded-md border border-border bg-bg-elevated p-1">
      <button
        type="button"
        onClick={() => goTo(shiftDate(dateValue, -1))}
        className="rounded px-2 py-1 text-sm text-text-secondary hover:bg-bg-hover hover:text-text-primary"
        aria-label="Previous day"
      >
        ‹
      </button>
      <input
        type="date"
        value={dateValue}
        onChange={(e) => goTo(e.target.value)}
        className="bg-transparent px-1 py-1 text-sm text-text-primary [color-scheme:dark]"
      />
      <button
        type="button"
        onClick={() => goTo(shiftDate(dateValue, 1))}
        className="rounded px-2 py-1 text-sm text-text-secondary hover:bg-bg-hover hover:text-text-primary"
        aria-label="Next day"
      >
        ›
      </button>
      <button
        type="button"
        onClick={() => goTo(new Date().toISOString().slice(0, 10))}
        className="ml-1 rounded px-2 py-1 text-xs text-accent hover:bg-bg-hover"
      >
        Today
      </button>
    </div>
  );
}
