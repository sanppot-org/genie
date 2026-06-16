"use client";

import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  CMP_LABELS,
  conditionForOp,
  METRICS,
  OP_LABELS,
  opsForMetric,
} from "@/lib/filter-metrics";
import type { FilterComparator, FilterCondition, FilterOp } from "@/lib/types";

const SELECT_CLASS =
  "h-8 rounded-lg border border-input bg-transparent px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
const CMPS: FilterComparator[] = ["lt", "lte", "gt", "gte", "eq"];

// 그룹 순서 보존용.
const GROUPS = ["스냅샷", "손익계산서", "재무비율", "점수"] as const;

function numOrUndef(s: string): number | undefined {
  if (s.trim() === "") return undefined;
  const n = Number(s);
  return Number.isNaN(n) ? undefined : n;
}

function CmpSelect({ value, onChange }: { value: FilterComparator; onChange: (c: FilterComparator) => void }) {
  return (
    <select className={SELECT_CLASS} value={value} onChange={(e) => onChange(e.target.value as FilterComparator)}>
      {CMPS.map((c) => (
        <option key={c} value={c}>
          {CMP_LABELS[c]}
        </option>
      ))}
    </select>
  );
}

export function ConditionRow({
  condition,
  onChange,
  onRemove,
}: {
  condition: FilterCondition;
  onChange: (c: FilterCondition) => void;
  onRemove: () => void;
}) {
  const ops = opsForMetric(condition.metric);

  const setMetric = (metric: string) => {
    // 지표 변경 시: 새 지표가 시계열/스칼라가 바뀌면 op도 호환되게 재설정.
    const nextOps = opsForMetric(metric);
    const op = nextOps.includes(condition.op) ? condition.op : nextOps[0];
    onChange(conditionForOp(metric, op));
  };
  const setOp = (op: FilterOp) => onChange(conditionForOp(condition.metric, op));
  const patch = (p: Partial<FilterCondition>) => onChange({ ...condition, ...p });
  const patchPred = (p: Partial<{ cmp: FilterComparator; value: number | undefined }>) =>
    onChange({
      ...condition,
      predicate: {
        cmp: p.cmp ?? condition.predicate?.cmp ?? "gt",
        value: (p.value ?? condition.predicate?.value ?? 0) as number,
      },
    });

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border px-3 py-2">
      {/* 지표 */}
      <select className={SELECT_CLASS} value={condition.metric} onChange={(e) => setMetric(e.target.value)}>
        {GROUPS.map((g) => (
          <optgroup key={g} label={g}>
            {METRICS.filter((m) => m.group === g).map((m) => (
              <option key={m.key} value={m.key}>
                {m.label}
              </option>
            ))}
          </optgroup>
        ))}
      </select>

      {/* 연산 */}
      <select className={SELECT_CLASS} value={condition.op} onChange={(e) => setOp(e.target.value as FilterOp)}>
        {ops.map((op) => (
          <option key={op} value={op}>
            {OP_LABELS[op]}
          </option>
        ))}
      </select>

      {/* op별 파라미터 */}
      {condition.op === "cmp" && (
        <>
          <CmpSelect value={condition.cmp ?? "lt"} onChange={(c) => patch({ cmp: c })} />
          <Input
            type="number"
            step="any"
            inputMode="decimal"
            className="h-8 w-24"
            placeholder="값"
            value={condition.value ?? ""}
            onChange={(e) => patch({ value: numOrUndef(e.target.value) })}
          />
        </>
      )}

      {condition.op === "count" && (
        <>
          <span className="text-sm text-muted-foreground">최근</span>
          <Input type="number" min="1" max="20" className="h-8 w-16" value={condition.window ?? 5}
            onChange={(e) => patch({ window: numOrUndef(e.target.value) })} />
          <span className="text-sm text-muted-foreground">년 중</span>
          <Input type="number" min="1" className="h-8 w-16" value={condition.min_count ?? 4}
            onChange={(e) => patch({ min_count: numOrUndef(e.target.value) })} />
          <span className="text-sm text-muted-foreground">년 이상</span>
          <CmpSelect value={condition.predicate?.cmp ?? "gt"} onChange={(c) => patchPred({ cmp: c })} />
          <Input type="number" step="any" inputMode="decimal" className="h-8 w-20" placeholder="기준"
            value={condition.predicate?.value ?? 0}
            onChange={(e) => patchPred({ value: numOrUndef(e.target.value) })} />
        </>
      )}

      {condition.op === "streak" && (
        <>
          <span className="text-sm text-muted-foreground">최근</span>
          <Input type="number" min="1" max="20" className="h-8 w-16" value={condition.window ?? 5}
            onChange={(e) => patch({ window: numOrUndef(e.target.value) })} />
          <span className="text-sm text-muted-foreground">년 연속</span>
          <CmpSelect value={condition.predicate?.cmp ?? "gt"} onChange={(c) => patchPred({ cmp: c })} />
          <Input type="number" step="any" inputMode="decimal" className="h-8 w-20" placeholder="기준"
            value={condition.predicate?.value ?? 0}
            onChange={(e) => patchPred({ value: numOrUndef(e.target.value) })} />
        </>
      )}

      {(condition.op === "cagr" || condition.op === "avg") && (
        <>
          <span className="text-sm text-muted-foreground">최근</span>
          <Input type="number" min={condition.op === "cagr" ? "2" : "1"} max="20" className="h-8 w-16"
            value={condition.window ?? 5}
            onChange={(e) => patch({ window: numOrUndef(e.target.value) })} />
          <span className="text-sm text-muted-foreground">년 {condition.op === "cagr" ? "CAGR" : "평균"}</span>
          <CmpSelect value={condition.cmp ?? "gt"} onChange={(c) => patch({ cmp: c })} />
          <Input type="number" step="any" inputMode="decimal" className="h-8 w-24"
            placeholder={condition.op === "cagr" ? "% (예: 0)" : "값"}
            value={condition.value ?? ""}
            onChange={(e) => patch({ value: numOrUndef(e.target.value) })} />
          {condition.op === "cagr" && <span className="text-sm text-muted-foreground">%</span>}
        </>
      )}

      <Button size="icon-sm" variant="ghost" className="ml-auto" onClick={onRemove} aria-label="조건 삭제">
        <X className="size-4" />
      </Button>
    </div>
  );
}
