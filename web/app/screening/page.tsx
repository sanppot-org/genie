"use client";

import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ScreeningRow, ScreeningSortBy, ScreeningSortOrder } from "@/lib/types";
import { useScreening } from "@/lib/use-screening";
import { formatNumber, formatPercent } from "@/lib/utils";

const PAGE_SIZE = 50;

function scoreCell(primary: string, score: number) {
  return (
    <span className="tabular-nums">
      {primary} <span className="text-muted-foreground">({score})</span>
    </span>
  );
}

function renderPer(row: ScreeningRow) {
  return scoreCell(formatNumber(row.per, 2), row.scores.per);
}

function renderPbr(row: ScreeningRow) {
  return scoreCell(formatNumber(row.pbr, 2), row.scores.pbr);
}

function renderDividendYield(row: ScreeningRow) {
  return scoreCell(formatPercent(row.dividend_yield, 2), row.scores.dividend_yield);
}

function renderQuarterly(row: ScreeningRow) {
  return scoreCell(row.quarterly_dividend ? "예" : "아니오", row.scores.quarterly_dividend);
}

function renderConsecutive(row: ScreeningRow) {
  return scoreCell(`${row.consecutive_increase_years}년`, row.scores.consecutive_increase_years);
}

type Column = {
  key: string;
  label: string;
  align: string;
  sortKey: ScreeningSortBy | null;
};

const COLUMNS: readonly Column[] = [
  { key: "rank", label: "#", align: "text-right", sortKey: null },
  { key: "ticker", label: "종목", align: "text-left", sortKey: null },
  { key: "per", label: "PER", align: "text-right", sortKey: "per" },
  { key: "pbr", label: "PBR", align: "text-right", sortKey: "pbr" },
  { key: "div", label: "배당%", align: "text-right", sortKey: "dividend_yield" },
  { key: "quarterly", label: "분기", align: "text-right", sortKey: "quarterly_dividend" },
  { key: "consecutive", label: "연속", align: "text-right", sortKey: "consecutive_years" },
  { key: "total", label: "총점", align: "text-right", sortKey: "total_score" },
];

export default function ScreeningPage() {
  const [date, setDate] = useState("");
  const [offset, setOffset] = useState(0);
  const [sortBy, setSortBy] = useState<ScreeningSortBy>("total_score");
  const [order, setOrder] = useState<ScreeningSortOrder>("desc");

  const query = useScreening(date || undefined, PAGE_SIZE, offset, sortBy, order);
  const data = query.data;

  const total = data?.total ?? 0;
  const hasPrev = offset > 0;
  const hasNext = offset + PAGE_SIZE < total;
  const startIdx = total === 0 ? 0 : offset + 1;
  const endIdx = Math.min(offset + PAGE_SIZE, total);

  function handleHeaderClick(col: ScreeningSortBy) {
    if (sortBy === col) {
      if (order === "desc") {
        setOrder("asc");
      } else {
        // ASC 상태에서 한 번 더 클릭 → 정렬 해제 (ticker ASC = 자연 순서)
        setSortBy("ticker");
        setOrder("asc");
      }
    } else {
      setSortBy(col);
      setOrder("desc");
    }
    setOffset(0);
  }

  return (
    <main className="mx-auto w-full max-w-6xl p-6 space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">KR 주식 스크리닝</h1>
        <p className="text-sm text-muted-foreground">
          PER · PBR · 배당수익률 · 분기 배당 · 연속 인상 5개 지표 점수 합산 (45점 만점). 컬럼 헤더 클릭으로 정렬.
        </p>
      </header>

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">기준 일자</span>
          <Input
            type="date"
            value={date}
            onChange={(e) => {
              setDate(e.target.value);
              setOffset(0);
            }}
            className="w-44"
          />
        </label>
        {data?.target_date && (
          <span className="text-sm text-muted-foreground">
            적용 기준일: <span className="font-mono">{data.target_date}</span>
          </span>
        )}
      </div>

      <section className="rounded-lg border border-border">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                {COLUMNS.map((c) => (
                  <th
                    key={c.key}
                    className={`px-3 py-2 font-medium text-muted-foreground ${c.align}`}
                  >
                    {c.sortKey ? (
                      <button
                        type="button"
                        onClick={() => handleHeaderClick(c.sortKey!)}
                        className="inline-flex items-center gap-1 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
                      >
                        {c.label}
                        {sortBy === c.sortKey &&
                          (order === "desc" ? (
                            <ChevronDown className="h-3 w-3" />
                          ) : (
                            <ChevronUp className="h-3 w-3" />
                          ))}
                      </button>
                    ) : (
                      c.label
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {query.isLoading && !data && (
                <SkeletonRows />
              )}
              {query.isError && (
                <tr>
                  <td colSpan={COLUMNS.length} className="px-3 py-6 text-center text-destructive">
                    조회 실패: {(query.error as Error).message}
                    <div className="mt-2">
                      <Button size="sm" variant="outline" onClick={() => query.refetch()}>
                        다시 시도
                      </Button>
                    </div>
                  </td>
                </tr>
              )}
              {data && data.rows.length === 0 && (
                <tr>
                  <td colSpan={COLUMNS.length} className="px-3 py-6 text-center text-muted-foreground">
                    기준일자 데이터가 없습니다.
                  </td>
                </tr>
              )}
              {data?.rows.map((row, i) => (
                <tr key={row.ticker} className="border-b border-border last:border-0 hover:bg-muted/40">
                  <td className="px-3 py-2 text-right text-muted-foreground tabular-nums">
                    {offset + i + 1}
                  </td>
                  <td className="px-3 py-2">
                    <div className="font-mono text-xs text-muted-foreground">{row.ticker}</div>
                    <div className="font-medium">{row.name}</div>
                  </td>
                  <td className="px-3 py-2 text-right">{renderPer(row)}</td>
                  <td className="px-3 py-2 text-right">{renderPbr(row)}</td>
                  <td className="px-3 py-2 text-right">{renderDividendYield(row)}</td>
                  <td className="px-3 py-2 text-right">{renderQuarterly(row)}</td>
                  <td className="px-3 py-2 text-right">{renderConsecutive(row)}</td>
                  <td className="px-3 py-2 text-right font-semibold tabular-nums">
                    {row.total_score}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <footer className="flex flex-wrap items-center justify-between gap-3 text-sm">
        <span className="text-muted-foreground">
          {total > 0 ? (
            <>
              전체 <span className="font-mono">{total.toLocaleString("ko-KR")}</span>건 ·{" "}
              <span className="font-mono">{startIdx}</span>–<span className="font-mono">{endIdx}</span>
            </>
          ) : (
            "결과 없음"
          )}
          {query.isFetching && data && (
            <span className="ml-2 text-muted-foreground">갱신 중…</span>
          )}
        </span>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={!hasPrev}
            onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
          >
            ← 이전
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!hasNext}
            onClick={() => setOffset((o) => o + PAGE_SIZE)}
          >
            다음 →
          </Button>
        </div>
      </footer>
    </main>
  );
}

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 8 }).map((_, i) => (
        <tr key={i} className="border-b border-border last:border-0">
          {COLUMNS.map((c) => (
            <td key={c.key} className="px-3 py-3">
              <div className="h-3 w-full animate-pulse rounded bg-muted" />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}
