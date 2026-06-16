import type { FilterComparator, FilterCondition, FilterOp } from "@/lib/types";

export type MetricGroup = "스냅샷" | "손익계산서" | "재무비율" | "점수";

export interface MetricMeta {
  key: string;
  label: string;
  group: MetricGroup;
  isTimeseries: boolean;
  unit: string;
}

// 백엔드 METRIC_REGISTRY와 1:1 (키/시계열 동기화 필수).
export const METRICS: MetricMeta[] = [
  { key: "per", label: "PER", group: "스냅샷", isTimeseries: false, unit: "배" },
  { key: "pbr", label: "PBR", group: "스냅샷", isTimeseries: false, unit: "배" },
  { key: "div", label: "배당수익률", group: "스냅샷", isTimeseries: false, unit: "%" },
  { key: "dps", label: "주당배당금", group: "스냅샷", isTimeseries: false, unit: "원" },
  { key: "eps_snapshot", label: "EPS(스냅샷)", group: "스냅샷", isTimeseries: false, unit: "원" },
  { key: "bps_snapshot", label: "BPS(스냅샷)", group: "스냅샷", isTimeseries: false, unit: "원" },
  { key: "sale_account", label: "매출액", group: "손익계산서", isTimeseries: true, unit: "억원" },
  { key: "bsop_prti", label: "영업이익", group: "손익계산서", isTimeseries: true, unit: "억원" },
  { key: "thtr_ntin", label: "당기순이익", group: "손익계산서", isTimeseries: true, unit: "억원" },
  { key: "sale_totl_prfi", label: "매출총이익", group: "손익계산서", isTimeseries: true, unit: "억원" },
  { key: "op_prfi", label: "경상이익", group: "손익계산서", isTimeseries: true, unit: "억원" },
  { key: "eps", label: "EPS", group: "재무비율", isTimeseries: true, unit: "원" },
  { key: "bps", label: "BPS", group: "재무비율", isTimeseries: true, unit: "원" },
  { key: "sps", label: "주당매출액", group: "재무비율", isTimeseries: true, unit: "원" },
  { key: "roe", label: "ROE", group: "재무비율", isTimeseries: true, unit: "%" },
  { key: "debt_ratio", label: "부채비율", group: "재무비율", isTimeseries: true, unit: "%" },
  { key: "reserve_rate", label: "유보율", group: "재무비율", isTimeseries: true, unit: "%" },
  { key: "revenue_growth", label: "매출증가율", group: "재무비율", isTimeseries: true, unit: "%" },
  { key: "op_growth", label: "영업이익증가율", group: "재무비율", isTimeseries: true, unit: "%" },
  { key: "net_growth", label: "순이익증가율", group: "재무비율", isTimeseries: true, unit: "%" },
  { key: "total_score", label: "종합점수", group: "점수", isTimeseries: false, unit: "점" },
];

export const METRIC_BY_KEY: Record<string, MetricMeta> = Object.fromEntries(
  METRICS.map((m) => [m.key, m]),
);

export const SCALAR_SORT_KEYS: string[] = METRICS.filter((m) => !m.isTimeseries).map((m) => m.key);

export const OP_LABELS: Record<FilterOp, string> = {
  cmp: "비교",
  count: "N년중 M년",
  cagr: "CAGR",
  streak: "N년 연속",
  avg: "N년 평균",
};

export const TIMESERIES_OPS: FilterOp[] = ["count", "cagr", "streak", "avg"];
export const SCALAR_OPS: FilterOp[] = ["cmp"];

export function opsForMetric(metricKey: string): FilterOp[] {
  const m = METRIC_BY_KEY[metricKey];
  if (!m) return SCALAR_OPS;
  return m.isTimeseries ? TIMESERIES_OPS : SCALAR_OPS;
}

export const CMP_LABELS: Record<FilterComparator, string> = {
  lt: "<",
  lte: "≤",
  gt: ">",
  gte: "≥",
  eq: "=",
};

// 지표/연산 선택 시 합리적 기본 조건 생성.
export function defaultCondition(metricKey = "per"): FilterCondition {
  const ops = opsForMetric(metricKey);
  return conditionForOp(metricKey, ops[0]);
}

// 연산 변경 시 op에 맞는 파라미터 기본값으로 재구성(다른 필드는 비움).
export function conditionForOp(metricKey: string, op: FilterOp): FilterCondition {
  switch (op) {
    case "cmp":
      return { metric: metricKey, op, cmp: "lt", value: undefined };
    case "count":
      return { metric: metricKey, op, window: 5, min_count: 4, predicate: { cmp: "gt", value: 0 } };
    case "streak":
      return { metric: metricKey, op, window: 5, predicate: { cmp: "gt", value: 0 } };
    case "cagr":
      return { metric: metricKey, op, window: 5, cmp: "gt", value: undefined };
    case "avg":
      return { metric: metricKey, op, window: 5, cmp: "gte", value: undefined };
  }
}
