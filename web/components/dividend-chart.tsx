"use client";

import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { DividendKind, DividendPoint } from "@/lib/types";

const COLOR: Record<DividendKind, string> = {
  SETTLE: "#f59e0b",
  INTERIM: "#6366f1",
  QUARTERLY: "#14b8a6",
};

const KIND_LABEL: Record<DividendKind, string> = {
  SETTLE: "결산",
  INTERIM: "중간/반기",
  QUARTERLY: "분기",
};

export function DividendChart({ points }: { points: DividendPoint[] }) {
  if (points.length === 0) {
    return <p className="text-sm text-muted-foreground">배당 내역 없음</p>;
  }
  // 같은 record_date에 종류가 다른 배당이 공존할 수 있어 (kind 포함) 합성 키를
  // x축에 사용. tick·tooltip label에는 record_date만 노출.
  const data = points.map((p) => ({ ...p, _x: `${p.record_date}|${p.kind}` }));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <XAxis
          dataKey="_x"
          tick={{ fontSize: 11 }}
          tickFormatter={(v: string) => v.split("|")[0]}
        />
        <YAxis
          tick={{ fontSize: 11 }}
          tickFormatter={(v: number) => `${v.toLocaleString("ko-KR")}원`}
          width={72}
        />
        <Tooltip
          formatter={(value, _name, item) => {
            const v = typeof value === "number" ? value : Number(value);
            const kind = (item.payload as DividendPoint).kind;
            return [`${v.toLocaleString("ko-KR")}원`, KIND_LABEL[kind]];
          }}
          labelFormatter={(d) => `기준일: ${String(d ?? "").split("|")[0]}`}
          cursor={{ fill: "rgba(0,0,0,0.04)" }}
        />
        <Bar dataKey="dps">
          {data.map((p) => (
            <Cell key={p._x} fill={COLOR[p.kind]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
