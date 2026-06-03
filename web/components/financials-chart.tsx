"use client";

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { IncomeStatementPoint, IncomeStatementSeries } from "@/lib/types";

// ── 색상 ────────────────────────────────────────────────────────────────────
const COLOR_REVENUE = "#3b82f6"; // blue-500
const COLOR_OP = "#10b981"; // emerald-500
const COLOR_NET = "#f59e0b"; // amber-500
const COLOR_PRICE = "#475569"; // slate-600
const COLOR_EPS = "#8b5cf6"; // violet-500
const COLOR_DPS = "#14b8a6"; // teal-500

// 결산기(3계열 막대) 한 그룹당 최소 폭(px). 좁은 화면에서 막대가 뭉개지지 않게 가로 스크롤 기준.
const PX_PER_GROUP = 46;

// ── 포맷터 ──────────────────────────────────────────────────────────────────
/** 억원 → "조" / "억" 단위 축약 문자열 */
function fmtAmount(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  const abs = Math.abs(v);
  if (abs >= 10000) return `${(v / 10000).toFixed(1)}조`;
  return `${v.toLocaleString("ko-KR")}억`;
}

/** YAxis tick 포맷 (짧게) */
function yAxisTick(v: number): string {
  return fmtAmount(v);
}

/** YYYYMM → 표시용 레이블 */
function fmtPeriod(yymm: string, isAnnual: boolean): string {
  if (yymm.length !== 6) return yymm;
  const year = yymm.slice(0, 4);
  const month = yymm.slice(4, 6);
  if (isAnnual) return year;
  // 분기 추정 (03→1Q, 06→2Q, 09→3Q, 12→4Q)
  const quarterMap: Record<string, string> = { "03": "1Q", "06": "2Q", "09": "3Q", "12": "4Q" };
  const q = quarterMap[month] ?? month;
  return `${year.slice(2)}.${q}`;
}

// ── 요약 표 ──────────────────────────────────────────────────────────────────
function calcYoy(curr: number | null, prev: number | null): number | null {
  if (curr === null || prev === null || prev === 0) return null;
  return ((curr - prev) / Math.abs(prev)) * 100;
}

function pct(v: number | null): string {
  if (v === null) return "-";
  const sign = v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(1)}%`;
}

function ratio(rev: number | null, val: number | null): number | null {
  if (!rev || val === null) return null;
  return (val / rev) * 100;
}

// 배당성향 = DPS / EPS × 100. KIS 기타주요비율 payout_rate는 명세상 "비정상, 무시" 필드라
// 쓰지 않고, 공시값과 일치하는 DPS/EPS 파생으로 계산. 적자/무이익(EPS<=0)이면 정의 안 됨.
function payoutRatio(dps: number | null, eps: number | null): number | null {
  if (dps === null || eps === null || eps <= 0) return null;
  return (dps / eps) * 100;
}

interface SummaryRow {
  label: string;
  revenue: number | null;
  op: number | null;
  net: number | null;
  revYoy: number | null;
  opYoy: number | null;
  netYoy: number | null;
  opMargin: number | null;
  netMargin: number | null;
  price: number | null;
  eps: number | null;
  per: number | null;
  dps: number | null;
  div: number | null;
  isEstimate: boolean;
}

// 음수(적자)면 빨강
function amountCls(v: number | null): string {
  return v !== null && v < 0 ? "text-red-500" : "";
}

// YoY 증감률 → 색상 클래스
function yoyCls(v: number | null): string {
  if (v === null) return "text-muted-foreground";
  return v >= 0 ? "text-emerald-500" : "text-red-500";
}

function SummaryTable({ points, isAnnual }: { points: IncomeStatementPoint[]; isAnnual: boolean }) {
  if (points.length === 0) return null;
  // YoY 비교 거리: 연간 1기 전(작년), 분기 4기 전(전년 동기).
  const offset = isAnnual ? 1 : 4;

  // points는 오름차순 → YoY는 i-offset과 비교, 표시는 최신순(내림차순).
  const rows: SummaryRow[] = points
    .map((p, i) => {
      const base = i - offset >= 0 ? points[i - offset] : null;
      return {
        label: fmtPeriod(p.stac_yymm, isAnnual),
        revenue: p.revenue,
        op: p.operating_profit,
        net: p.net_income,
        revYoy: calcYoy(p.revenue, base?.revenue ?? null),
        opYoy: calcYoy(p.operating_profit, base?.operating_profit ?? null),
        netYoy: calcYoy(p.net_income, base?.net_income ?? null),
        opMargin: ratio(p.revenue, p.operating_profit),
        netMargin: ratio(p.revenue, p.net_income),
        price: p.price,
        eps: p.eps,
        per: p.per,
        dps: p.dps,
        div: p.div,
        isEstimate: p.is_estimate,
      };
    })
    .reverse();

  // 세로 스크롤 시 제목행 고정(sticky top-0). 스크롤되는 본문이 비쳐 보이지 않게 불투명 bg-muted.
  const th = "sticky top-0 z-10 bg-muted px-3 py-1.5 text-right font-normal whitespace-nowrap";
  const thYoy = "sticky top-0 z-10 bg-muted px-2 py-1.5 text-right font-normal whitespace-nowrap text-[10px]";
  const td = "px-3 py-1.5 text-right tabular-nums whitespace-nowrap";
  const tdYoy = "px-2 py-1.5 text-right tabular-nums whitespace-nowrap text-[11px]";

  return (
    // resize-x: 우하단 핸들을 드래그해 사용자가 표 폭을 직접 조절. 넓히면 표가 채워지고,
    // 좁히면(셀은 nowrap) 가로 스크롤. 시작 폭은 내용 너비(w-fit).
    <div className="max-h-80 w-fit min-w-[16rem] max-w-full resize-x overflow-auto rounded-md border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-xs text-muted-foreground">
            <th className="sticky left-0 top-0 z-20 bg-muted px-3 py-1.5 text-left font-normal">결산기</th>
            <th className={th}>매출</th>
            <th className={thYoy}>YoY</th>
            <th className={th}>영업이익</th>
            <th className={thYoy}>YoY</th>
            <th className={th}>순이익</th>
            <th className={thYoy}>YoY</th>
            <th className={th}>영업이익률</th>
            <th className={th}>순이익률</th>
            <th className={th}>주가</th>
            <th className={th}>EPS</th>
            <th className={th}>PER</th>
            <th className={th}>DPS</th>
            <th className={th}>시가배당율</th>
            <th className={th}>배당성향</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            // rows는 최신순(추정행이 상단). 추정 블록과 확정 블록 경계에 굵은 구분선.
            const isBoundary = row.isEstimate && i + 1 < rows.length && !rows[i + 1].isEstimate;
            const rowCls = [
              "border-b last:border-0",
              row.isEstimate ? "italic text-muted-foreground bg-muted/20" : "",
              isBoundary ? "border-b-2 border-b-border" : "",
            ].join(" ");
            return (
            <tr key={row.label} className={rowCls}>
              <td className="sticky left-0 z-10 bg-background px-3 py-1.5 text-left font-medium whitespace-nowrap">
                {row.isEstimate ? (
                  <span className="flex items-center gap-1">
                    {row.label}
                    <span className="rounded bg-amber-500/15 px-1 py-0.5 text-[10px] font-normal not-italic text-amber-600 dark:text-amber-400">
                      예상
                    </span>
                  </span>
                ) : (
                  row.label
                )}
              </td>
              <td className={`${td} font-medium`}>{fmtAmount(row.revenue)}</td>
              <td className={`${tdYoy} ${yoyCls(row.revYoy)}`}>{pct(row.revYoy)}</td>
              <td className={`${td} ${amountCls(row.op)}`}>{fmtAmount(row.op)}</td>
              <td className={`${tdYoy} ${yoyCls(row.opYoy)}`}>{pct(row.opYoy)}</td>
              <td className={`${td} ${amountCls(row.net)}`}>{fmtAmount(row.net)}</td>
              <td className={`${tdYoy} ${yoyCls(row.netYoy)}`}>{pct(row.netYoy)}</td>
              <td className={`${td} text-xs text-muted-foreground`}>
                {row.opMargin !== null ? `${row.opMargin.toFixed(1)}%` : "-"}
              </td>
              <td className={`${td} text-xs text-muted-foreground`}>
                {row.netMargin !== null ? `${row.netMargin.toFixed(1)}%` : "-"}
              </td>
              <td className={td}>
                {row.price !== null ? `${Math.round(row.price).toLocaleString("ko-KR")}원` : "-"}
              </td>
              <td className={td}>
                {row.eps !== null ? `${Math.round(row.eps).toLocaleString("ko-KR")}원` : "-"}
              </td>
              <td className={td}>{row.per !== null ? `${row.per.toFixed(1)}배` : "-"}</td>
              <td className={td}>
                {row.dps !== null ? `${Math.round(row.dps).toLocaleString("ko-KR")}원` : "-"}
              </td>
              <td className={`${td} text-xs text-muted-foreground`}>
                {row.div !== null ? `${row.div.toFixed(2)}%` : "-"}
              </td>
              <td className={`${td} text-xs text-muted-foreground`}>
                {payoutRatio(row.dps, row.eps) !== null
                  ? `${payoutRatio(row.dps, row.eps)!.toFixed(1)}%`
                  : "-"}
              </td>
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── 주가·EPS·DPS 전용 툴팁 ──────────────────────────────────────────────────
interface PerShareTooltipProps {
  active?: boolean;
  payload?: { name: string; value: number | null; color: string }[];
  label?: string;
  isAnnual: boolean;
}

function PerShareTooltip({ active, payload, label, isAnnual }: PerShareTooltipProps) {
  if (!active || !payload || payload.length === 0 || !label) return null;

  const find = (name: string) => payload.find((p) => p.name === name)?.value ?? null;
  const 주가 = find("주가");
  const 배당 = find("배당");
  const 유보 = find("유보");
  // 유보(=EPS-DPS)가 null이면 그 행의 EPS 자체가 null. 유보가 있을 때만 EPS=유보+배당으로 역산.
  const eps = 유보 !== null ? 유보 + (배당 ?? 0) : null;

  function fmtWon(v: number | null): string {
    if (v === null || v === undefined) return "-";
    return `${Math.round(v).toLocaleString("ko-KR")}원`;
  }

  return (
    <div className="rounded-md border bg-background px-3 py-2 text-sm shadow-md">
      <p className="mb-1 font-medium">{fmtPeriod(label, isAnnual)}</p>
      <p className="flex justify-between gap-4 tabular-nums">
        <span style={{ color: COLOR_PRICE }}>주가</span>
        <span>{fmtWon(주가)}</span>
      </p>
      <p className="flex justify-between gap-4 tabular-nums">
        <span style={{ color: COLOR_EPS }}>EPS</span>
        <span>{fmtWon(eps)}</span>
      </p>
      <p className="flex justify-between gap-4 tabular-nums">
        <span style={{ color: COLOR_DPS }}>배당(DPS)</span>
        <span>{fmtWon(배당)}</span>
      </p>
      {(() => {
        const pr = payoutRatio(배당, eps);
        return (
          <p className="flex justify-between gap-4 tabular-nums">
            <span className="text-muted-foreground">배당성향</span>
            <span>{pr !== null ? `${pr.toFixed(1)}%` : "-"}</span>
          </p>
        );
      })()}
    </div>
  );
}

// ── 커스텀 툴팁 ──────────────────────────────────────────────────────────────
interface TooltipPayloadItem {
  name: string;
  value: number | null;
  color: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
  isAnnual: boolean;
}

function CustomTooltip({ active, payload, label, isAnnual }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0 || !label) return null;
  return (
    <div className="rounded-md border bg-background px-3 py-2 text-sm shadow-md">
      <p className="mb-1 font-medium">{fmtPeriod(label, isAnnual)}</p>
      {payload.map((item) => (
        <p key={item.name} className="flex justify-between gap-4 tabular-nums">
          <span style={{ color: item.color }}>{item.name}</span>
          <span>{fmtAmount(item.value)}</span>
        </p>
      ))}
    </div>
  );
}

// ── 메인 컴포넌트 ────────────────────────────────────────────────────────────
export function FinancialsChart({ series }: { series: IncomeStatementSeries }) {
  const { points, period_type } = series;
  const isAnnual = period_type === "ANNUAL";

  if (points.length === 0) {
    return <p className="text-sm text-muted-foreground">재무 데이터 없음</p>;
  }

  // 차트는 확정 실적만(추정치는 표에만 표시).
  const data = points
    .filter((p) => !p.is_estimate)
    .map((p) => ({
      stac_yymm: p.stac_yymm,
      매출: p.revenue,
      영업이익: p.operating_profit,
      순이익: p.net_income,
    }));

  const perShareData = points
    .filter((p) => !p.is_estimate)
    .map((p) => ({
      stac_yymm: p.stac_yymm,
      주가: p.price,
      배당: p.dps,
      유보: p.eps !== null && p.eps !== undefined ? p.eps - (p.dps ?? 0) : null,
    }));

  const hasOverPayout = perShareData.some((d) => d.유보 !== null && d.유보 < 0);

  // 좁은 화면에서 막대가 뭉개지지 않도록 데이터 기수에 비례한 최소 폭을 주고,
  // 부모보다 넓어지면 가로 스크롤. 데스크톱(넓은 부모)에서는 w-full로 채운다.
  const minWidth = Math.max(320, data.length * PX_PER_GROUP);

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto">
        <div className="w-full" style={{ minWidth }}>
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={data} margin={{ top: 8, right: 68, bottom: 0, left: 8 }} barCategoryGap="25%">
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(128,128,128,0.15)" vertical={false} />
              <XAxis
                dataKey="stac_yymm"
                tick={{ fontSize: 11 }}
                tickFormatter={(v: string) => fmtPeriod(v, isAnnual)}
                interval={0}
              />
              <YAxis
                yAxisId="left"
                tick={{ fontSize: 11 }}
                tickFormatter={yAxisTick}
                width={68}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                tick={{ fontSize: 11 }}
                tickFormatter={yAxisTick}
                width={68}
              />
              <Tooltip
                content={
                  <CustomTooltip isAnnual={isAnnual} />
                }
                cursor={{ fill: "rgba(0,0,0,0.04)" }}
              />
              <Legend
                iconType="square"
                iconSize={10}
                wrapperStyle={{ fontSize: 12 }}
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="매출"
                stroke={COLOR_REVENUE}
                strokeWidth={2}
                dot={{ r: 3 }}
              />
              <Bar yAxisId="right" dataKey="영업이익" fill={COLOR_OP} radius={[2, 2, 0, 0]} />
              <Bar yAxisId="right" dataKey="순이익" fill={COLOR_NET} radius={[2, 2, 0, 0]} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <p className="text-sm text-muted-foreground">주가 · EPS · 배당</p>
      <div className="overflow-x-auto">
        <div className="w-full" style={{ minWidth }}>
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={perShareData} margin={{ top: 8, right: 68, bottom: 0, left: 8 }} barCategoryGap="25%">
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(128,128,128,0.15)" vertical={false} />
              <XAxis
                dataKey="stac_yymm"
                tick={{ fontSize: 11 }}
                tickFormatter={(v: string) => fmtPeriod(v, isAnnual)}
                interval={0}
              />
              <YAxis
                yAxisId="price"
                tick={{ fontSize: 11 }}
                tickFormatter={(v: number) => v.toLocaleString("ko-KR")}
                width={68}
              />
              <YAxis
                yAxisId="pershare"
                orientation="right"
                tick={{ fontSize: 11 }}
                tickFormatter={(v: number) => v.toLocaleString("ko-KR")}
                width={68}
              />
              <Tooltip
                content={<PerShareTooltip isAnnual={isAnnual} />}
                cursor={{ fill: "rgba(0,0,0,0.04)" }}
              />
              <Legend
                iconType="square"
                iconSize={10}
                wrapperStyle={{ fontSize: 12 }}
              />
              <Bar yAxisId="pershare" dataKey="배당" stackId="eps" fill={COLOR_DPS} />
              <Bar yAxisId="pershare" dataKey="유보" stackId="eps" fill={COLOR_EPS} radius={[2, 2, 0, 0]} />
              <Line
                yAxisId="price"
                type="monotone"
                dataKey="주가"
                stroke={COLOR_PRICE}
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {hasOverPayout && (
        <p className="text-xs text-muted-foreground">
          ※ 배당이 EPS를 초과하거나 적자인 기간은 막대 높이가 EPS와 다르게 보일 수 있습니다.
        </p>
      )}

      <SummaryTable points={points} isAnnual={isAnnual} />
    </div>
  );
}
