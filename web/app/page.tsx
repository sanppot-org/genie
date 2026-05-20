"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { useDeferredValue, useState } from "react";

import { Input } from "@/components/ui/input";
import { apiGet } from "@/lib/api";
import type {
  CandleSeries,
  DividendSeries,
  FundamentalSeries,
  GenieResponse,
  Ticker,
} from "@/lib/types";
import { useRecentTickers } from "@/lib/use-recent-tickers";

const CandleChart = dynamic(
  () => import("@/components/candle-chart").then((m) => m.CandleChart),
  {
    ssr: false,
    loading: () => <p className="text-sm text-muted-foreground">차트 로딩 중...</p>,
  },
);

const DividendChart = dynamic(
  () => import("@/components/dividend-chart").then((m) => m.DividendChart),
  { ssr: false, loading: () => null },
);

// 차트 좌측 팬 시 단계적으로 넓히는 lookback(년). 마지막 단계 이후는 ALL(from/to 생략).
const STEPS = [1, 3, 10] as const;

function rangeFor(stepIdx: number): { from?: string; to?: string } {
  if (stepIdx >= STEPS.length) return {}; // ALL — apiGet이 undefined 파라미터 제외 → 백엔드 전체
  const fmt = (d: Date) =>
    `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`;
  const to = new Date();
  const from = new Date();
  from.setFullYear(from.getFullYear() - STEPS[stepIdx]);
  return { from: fmt(from), to: fmt(to) };
}

export default function Home() {
  const [q, setQ] = useState("");
  const [searchFocused, setSearchFocused] = useState(false);
  const deferredQ = useDeferredValue(q);
  const [selected, setSelected] = useState<Ticker | null>(null);
  const [stepIdx, setStepIdx] = useState(0);
  const { recent, add: addRecent, remove: removeRecent } = useRecentTickers();

  // 종목 변경 시 1Y로 리셋 (렌더 중 state 조정 — React 권장 패턴, effect 불필요).
  const [prevTicker, setPrevTicker] = useState(selected?.ticker);
  if (selected?.ticker !== prevTicker) {
    setPrevTicker(selected?.ticker);
    setStepIdx(0);
  }

  const tickers = useQuery({
    queryKey: ["tickers", deferredQ],
    queryFn: () =>
      apiGet<GenieResponse<Ticker[]>>("/api/tickers", { q: deferredQ, limit: 10 }).then(
        (r) => r.data,
      ),
    enabled: deferredQ.trim().length > 0,
  });

  const { from, to } = rangeFor(stepIdx);
  const fundamentals = useQuery({
    queryKey: ["fundamentals", selected?.ticker, stepIdx],
    queryFn: () =>
      apiGet<GenieResponse<FundamentalSeries>>("/api/fundamentals", {
        ticker: selected!.ticker,
        from,
        to,
      }).then((r) => r.data),
    enabled: Boolean(selected),
    // stepIdx 변경 시 이전 데이터 유지 → CandleChart 언마운트 방지(구간 보존 동작).
    placeholderData: keepPreviousData,
  });

  const candles = useQuery({
    queryKey: ["candles", selected?.ticker, stepIdx],
    queryFn: () =>
      apiGet<GenieResponse<CandleSeries>>("/api/candles/kr-stock", {
        ticker: selected!.ticker,
        from,
        to,
      }).then((r) => r.data),
    enabled: Boolean(selected),
    placeholderData: keepPreviousData,
  });

  const dividends = useQuery({
    queryKey: ["dividends", selected?.ticker, stepIdx],
    queryFn: () =>
      apiGet<GenieResponse<DividendSeries>>("/api/dividends", {
        ticker: selected!.ticker,
        from,
        to,
      }).then((r) => r.data),
    enabled: Boolean(selected),
    placeholderData: keepPreviousData,
  });

  return (
    <main className="w-full p-6 space-y-6">
      <h1 className="text-2xl font-semibold">Genie — 종목 차트</h1>

      <div className="relative max-w-3xl">
        <Input
          placeholder="ticker 또는 종목명 (예: 005930, 삼성)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => setSearchFocused(true)}
          onBlur={() => setSearchFocused(false)}
        />

        {searchFocused && deferredQ.trim().length > 0 && (
          <section className="absolute inset-x-0 top-full z-20 mt-1 max-h-80 overflow-auto rounded-md border bg-background p-1 shadow-lg">
            {tickers.isLoading && (
              <p className="px-3 py-2 text-sm text-muted-foreground">불러오는 중...</p>
            )}
            {tickers.isError && (
              <p className="px-3 py-2 text-sm text-red-600">
                검색 실패: {(tickers.error as Error).message}
              </p>
            )}
            {tickers.data && tickers.data.length === 0 && (
              <p className="px-3 py-2 text-sm text-muted-foreground">결과 없음</p>
            )}
            <ul>
              {tickers.data?.map((t) => (
                <li key={t.id}>
                  <button
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => {
                      setSelected(t);
                      addRecent(t);
                      setSearchFocused(false);
                      (document.activeElement as HTMLElement | null)?.blur();
                    }}
                    className={`w-full rounded-md px-3 py-2 text-left hover:bg-muted ${
                      selected?.id === t.id ? "bg-muted" : ""
                    }`}
                  >
                    <span className="font-mono text-sm">{t.ticker}</span>
                    <span className="ml-2">{t.name}</span>
                    <span className="ml-2 text-xs text-muted-foreground">{t.asset_type}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      {recent.length > 0 && (
        <div className="flex max-w-3xl flex-wrap gap-2">
          {recent.map((t) => (
            <span
              key={t.id}
              className="inline-flex items-center rounded-full border bg-background pl-3 text-sm"
            >
              <button
                type="button"
                onClick={() => {
                  setSelected(t);
                  addRecent(t);
                }}
                className="py-1 hover:text-foreground"
              >
                <span className="font-mono">{t.ticker}</span>
                <span className="ml-1.5">{t.name}</span>
              </button>
              <button
                type="button"
                aria-label={`${t.name} 최근 검색 삭제`}
                onClick={() => removeRecent(t.ticker)}
                className="px-2 py-1 text-muted-foreground hover:text-foreground"
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}

      {selected && (
        <section className="space-y-2 border-t pt-4">
          <h2 className="text-lg font-medium">
            {selected.name}{" "}
            <span className="font-mono text-sm text-muted-foreground">({selected.ticker})</span>
          </h2>
          <p className="text-xs text-muted-foreground">
            주가 + PER · 차트를 왼쪽으로 끌면 과거 더 불러옴
            {candles.isFetching && !candles.isLoading && (
              <span className="ml-2 text-muted-foreground">과거 불러오는 중…</span>
            )}
          </p>
          {(candles.isLoading || fundamentals.isLoading) && (
            <p className="text-sm text-muted-foreground">불러오는 중...</p>
          )}
          {candles.isError && (
            <p className="text-sm text-red-600">조회 실패: {(candles.error as Error).message}</p>
          )}
          {fundamentals.isError && (
            <p className="text-sm text-red-600">
              PER 조회 실패: {(fundamentals.error as Error).message}
            </p>
          )}
          {candles.data && candles.data.ticker === selected.ticker && (
            <CandleChart
              key={selected.ticker}
              points={candles.data.points}
              perPoints={
                fundamentals.data?.ticker === selected.ticker
                  ? fundamentals.data.points
                  : undefined
              }
              hasMore={stepIdx < STEPS.length}
              onNeedMore={() => setStepIdx((i) => Math.min(i + 1, STEPS.length))}
            />
          )}
          {dividends.data && dividends.data.ticker === selected.ticker && (
            <section className="space-y-2 pt-2">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                <h3 className="font-medium">배당 내역</h3>
                <span className="text-xs text-muted-foreground">
                  <span style={{ color: "#f59e0b" }}>●</span> 결산
                </span>
                <span className="text-xs text-muted-foreground">
                  <span style={{ color: "#14b8a6" }}>●</span> 분기
                </span>
                <span className="text-xs text-muted-foreground">
                  <span style={{ color: "#6366f1" }}>●</span> 중간/반기
                </span>
              </div>
              <DividendChart points={dividends.data.points} />
            </section>
          )}
        </section>
      )}
    </main>
  );
}
