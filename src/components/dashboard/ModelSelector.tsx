"use client";

import { useRouter } from "next/navigation";

export interface ModelOption {
  id: string;
  name: string;
  version: string;
  algorithm: string;
  isSynthetic: boolean;
}

export function ModelSelector({ models, selectedId }: { models: ModelOption[]; selectedId: string }) {
  const router = useRouter();

  return (
    <select
      value={selectedId}
      onChange={(e) => router.push(`/dashboard?model=${e.target.value}`)}
      className="rounded-md border border-border bg-bg-elevated px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent [color-scheme:dark]"
    >
      {models.map((m) => (
        <option key={m.id} value={m.id}>
          {m.name} · {m.version} {m.isSynthetic ? "(synthetic)" : ""}
        </option>
      ))}
    </select>
  );
}
