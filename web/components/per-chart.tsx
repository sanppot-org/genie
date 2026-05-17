"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { FundamentalPoint } from "@/lib/types";

interface Props {
  points: FundamentalPoint[];
}

export function PerChart({ points }: Props) {
  if (points.length === 0) {
    return <p className="text-sm text-muted-foreground">데이터 없음</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={points} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
        <XAxis dataKey="date" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} domain={["auto", "auto"]} />
        <Tooltip
          contentStyle={{ fontSize: 12 }}
          formatter={(v) => (typeof v === "number" ? v.toFixed(2) : "—")}
        />
        <Line
          type="monotone"
          dataKey="per"
          stroke="#0ea5e9"
          strokeWidth={2}
          dot={false}
          connectNulls={false}
          name="PER"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
