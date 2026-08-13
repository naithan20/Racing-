"use client";

import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { CalibrationBucket } from "@/backtesting/scoring";

export function CalibrationChart({ buckets }: { buckets: CalibrationBucket[] }) {
  const data = buckets.map((b) => ({
    label: b.bucketLabel,
    predicted: b.meanPredictedProbability !== null ? Math.round(b.meanPredictedProbability * 1000) / 10 : null,
    observed: b.observedFrequency !== null ? Math.round(b.observedFrequency * 1000) / 10 : null,
    sampleSize: b.sampleSize,
  }));

  const hasData = data.some((d) => d.sampleSize > 0);
  if (!hasData) {
    return <p className="text-sm text-text-muted">No settled predictions yet for this model — nothing to calibrate against.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#232a38" />
        <XAxis dataKey="label" stroke="#616d80" fontSize={11} tickLine={false} />
        <YAxis yAxisId="left" stroke="#616d80" fontSize={11} tickLine={false} unit="%" domain={[0, 100]} />
        <YAxis yAxisId="right" hide />
        <Tooltip
          contentStyle={{ background: "#10141d", border: "1px solid #232a38", fontSize: 12 }}
          labelStyle={{ color: "#9aa4b6" }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar yAxisId="right" dataKey="sampleSize" name="Sample size" fill="#1c2b47" />
        <Line yAxisId="left" type="monotone" dataKey="predicted" name="Mean predicted %" stroke="#4f8cff" strokeWidth={2} dot={{ r: 3 }} />
        <Line yAxisId="left" type="monotone" dataKey="observed" name="Observed strike rate %" stroke="#2fbf83" strokeWidth={2} dot={{ r: 3 }} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
