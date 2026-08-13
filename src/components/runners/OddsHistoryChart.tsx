"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface OddsPoint {
  timestamp: string;
  label: string;
  oddsDecimal: number;
  bookmaker: string;
}

export function OddsHistoryChart({ points }: { points: OddsPoint[] }) {
  if (points.length === 0) {
    return <p className="text-sm text-text-muted">No market price history recorded yet.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={points} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#232a38" />
        <XAxis dataKey="label" stroke="#616d80" fontSize={11} tickLine={false} />
        <YAxis stroke="#616d80" fontSize={11} tickLine={false} domain={["auto", "auto"]} />
        <Tooltip
          contentStyle={{ background: "#10141d", border: "1px solid #232a38", fontSize: 12 }}
          labelStyle={{ color: "#9aa4b6" }}
        />
        <Line type="stepAfter" dataKey="oddsDecimal" stroke="#4f8cff" strokeWidth={2} dot={{ r: 2 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
