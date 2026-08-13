"use client";

import { useRouter } from "next/navigation";

export function BacktestDatePicker({ dates, selected }: { dates: string[]; selected: string }) {
  const router = useRouter();
  const index = dates.indexOf(selected);

  function goTo(date: string) {
    router.push(`/backtest?date=${date}`);
  }

  return (
    <div className="flex items-center gap-1 rounded-md border border-border bg-bg-elevated p-1">
      <button
        type="button"
        disabled={index <= 0}
        onClick={() => goTo(dates[Math.max(index - 1, 0)])}
        className="rounded px-2 py-1 text-sm text-text-secondary hover:bg-bg-hover hover:text-text-primary disabled:opacity-30"
        aria-label="Earlier date"
      >
        ‹
      </button>
      <select
        value={selected}
        onChange={(e) => goTo(e.target.value)}
        className="bg-transparent px-1 py-1 text-sm text-text-primary [color-scheme:dark]"
      >
        {dates.map((d) => (
          <option key={d} value={d}>
            {d}
          </option>
        ))}
      </select>
      <button
        type="button"
        disabled={index >= dates.length - 1}
        onClick={() => goTo(dates[Math.min(index + 1, dates.length - 1)])}
        className="rounded px-2 py-1 text-sm text-text-secondary hover:bg-bg-hover hover:text-text-primary disabled:opacity-30"
        aria-label="Later date"
      >
        ›
      </button>
    </div>
  );
}
