"use client";

import { useMemo, useState } from "react";
import { ChevronDown, ChevronUp, Plus } from "lucide-react";

import { ConditionRow } from "@/components/filter/condition-row";
import { Button } from "@/components/ui/button";
import {
  defaultCondition,
  METRIC_BY_KEY,
  SCALAR_SORT_KEYS,
} from "@/lib/filter-metrics";
import { useFilterScreening } from "@/lib/use-filter-screening";
import type { FilterCondition, FilterMetricDisplay, ScreeningSortOrder } from "@/lib/types";

const PAGE_SIZE = 50;

// 조건 → 동적 컬럼(지표 기준 dedupe, 조건 순서 보존). 같은 지표 중복 조건은 첫 op로 표시.
interface DynCol {
  metric: string;
  op: string;
  label: string;
  sortable: boolean;
}

function buildColumns(conditions: FilterCondition[]): DynCol[] {
  const seen = new Set<string>();
  const cols: DynCol[] = [];
  for (const c of conditions) {
    if (seen.has(c.metric)) continue;
    seen.add(c.metric);
    const meta = METRIC_BY_KEY[c.metric];
    cols.push({
      metric: c.metric,
      op: c.op,
      label: meta ? meta.label : c.metric,
      sortable: SCALAR_SORT_KEYS.includes(c.metric),
    });
  }
  return cols;
}

function renderMetric(display: FilterMetricDisplay | undefined, op: string): string {
  if (display === undefined || display === null) return "-";
  if (typeof display === "number") {
    return Number.isInteger(display) ? String(display) : display.toFixed(2);
  }
  // 객체형: count → {count,window}, cagr/streak/avg → {[op]:value}
  if (op === "count") return `${display.count ?? "-"}/${display.window ?? "-"}`;
  if (op === "cagr") {
    const v = display.cagr;
    return v == null ? "-" : `${(Number(v) * 100).toFixed(1)}%`;
  }
  if (op === "streak") return display.streak == null ? "-" : `${String(display.streak)}년`;
  if (op === "avg") return display.avg == null ? "-" : Number(display.avg).toFixed(2);
  return "-";
}

export default function FilterScreeningPage() {
  const [draft, setDraft] = useState<FilterCondition[]>([defaultCondition("bsop_prti")]);
  const [applied, setApplied] = useState<FilterCondition[]>([]);
  const [sortBy, setSortBy] = useState<string>("total_score");
  const [order, setOrder] = useState<ScreeningSortOrder>("desc");
  const [offset, setOffset] = useState(0);

  const query = useFilterScreening(applied, sortBy, order, PAGE_SIZE, offset);
  const data = query.data;
  const columns = useMemo(() => buildColumns(applied), [applied]);

  const apply = () => {
    setOffset(0);
    setApplied(draft);
  };

  const updateRow = (i: number, c: FilterCondition) =>
    setDraft((rows) => rows.map((r, j) => (j === i ? c : r)));
  const removeRow = (i: number) => setDraft((rows) => rows.filter((_, j) => j !== i));
  const addRow = () => setDraft((rows) => [...rows, defaultCondition("per")]);

  const toggleSort = (key: string) => {
    if (sortBy === key) {
      setOrder((o) => (o === "desc" ? "asc" : "desc"));
    } else {
      setSortBy(key);
      setOrder("desc");
    }
    setOffset(0);
  };

  const total = data?.total ?? 0;

  return (
    <main className="mx-auto w-full max-w-6xl space-y-6 p-6">
      <div>
        <h1 className="text-lg font-semibold">조건 필터 스크리너</h1>
        <p className="text-sm text-muted-foreground">
          영업이익·EPS 등 연간 시계열 조건과 PER·PBR 등을 조합(AND)해 종목을 추려냅니다.
        </p>
      </div>

      {/* 빌더 */}
      <div className="space-y-2 rounded-lg border border-border p-3">
        {draft.map((c, i) => (
          <ConditionRow
            key={i}
            condition={c}
            onChange={(nc) => updateRow(i, nc)}
            onRemove={() => removeRow(i)}
          />
        ))}
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={addRow}>
            <Plus className="size-4" /> 조건 추가
          </Button>
          <Button size="sm" onClick={apply} disabled={draft.length === 0}>
            필터 적용
          </Button>
        </div>
      </div>

      {/* 에러 */}
      {query.isError && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {(query.error as Error).message}
        </div>
      )}

      {/* 결과 */}
      {applied.length > 0 && (
        <div className="rounded-lg border border-border">
          <div className="border-b border-border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
            {query.isLoading ? "조회 중…" : `총 ${total}종목`}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <SortableTh
                    label="종목"
                    sortKey="ticker"
                    sortBy={sortBy}
                    order={order}
                    onSort={toggleSort}
                  />
                  <SortableTh
                    label="종합점수"
                    sortKey="total_score"
                    sortBy={sortBy}
                    order={order}
                    onSort={toggleSort}
                    align="text-right"
                  />
                  {columns.map((col) => (
                    <Th key={col.metric} align="text-right">
                      {col.sortable ? (
                        <button
                          type="button"
                          className="inline-flex items-center gap-1"
                          onClick={() => toggleSort(col.metric)}
                        >
                          {col.label}
                          {sortBy === col.metric &&
                            (order === "desc" ? (
                              <ChevronDown className="size-3" />
                            ) : (
                              <ChevronUp className="size-3" />
                            ))}
                        </button>
                      ) : (
                        <span title="시계열 지표는 정렬 불가">{col.label}</span>
                      )}
                    </Th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data?.rows.map((row) => (
                  <tr
                    key={row.ticker}
                    className="border-b border-border last:border-0 hover:bg-muted/40"
                  >
                    <td className="px-3 py-2">
                      <span className="font-mono">{row.ticker}</span>{" "}
                      <span>{row.name}</span>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {row.total_score ?? "-"}
                    </td>
                    {columns.map((col) => (
                      <td key={col.metric} className="px-3 py-2 text-right tabular-nums">
                        {renderMetric(row.metrics[col.metric], col.op)}
                      </td>
                    ))}
                  </tr>
                ))}
                {!query.isLoading && data && data.rows.length === 0 && (
                  <tr>
                    <td
                      className="px-3 py-6 text-center text-muted-foreground"
                      colSpan={2 + columns.length}
                    >
                      조건에 맞는 종목이 없습니다.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {/* 페이지네이션 */}
          <div className="flex items-center justify-between border-t border-border px-3 py-2 text-sm">
            <span className="text-muted-foreground">
              {total === 0 ? 0 : offset + 1}–{Math.min(offset + PAGE_SIZE, total)} / {total}
            </span>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={offset === 0}
                onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
              >
                이전
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={offset + PAGE_SIZE >= total}
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
              >
                다음
              </Button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

function Th({
  children,
  align = "text-left",
}: {
  children: React.ReactNode;
  align?: string;
}) {
  return <th className={`px-3 py-2 font-medium ${align}`}>{children}</th>;
}

function SortableTh({
  label,
  sortKey,
  sortBy,
  order,
  onSort,
  align = "text-left",
}: {
  label: string;
  sortKey: string;
  sortBy: string;
  order: ScreeningSortOrder;
  onSort: (k: string) => void;
  align?: string;
}) {
  return (
    <th className={`px-3 py-2 font-medium ${align}`}>
      <button
        type="button"
        className="inline-flex items-center gap-1"
        onClick={() => onSort(sortKey)}
      >
        {label}
        {sortBy === sortKey &&
          (order === "desc" ? (
            <ChevronDown className="size-3" />
          ) : (
            <ChevronUp className="size-3" />
          ))}
      </button>
    </th>
  );
}
