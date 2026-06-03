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
  IncomeStatementSeries,
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

const FinancialsChart = dynamic(
  () => import("@/components/financials-chart").then((m) => m.FinancialsChart),
  { ssr: false, loading: () => <p className="text-sm text-muted-foreground">불러오는 중...</p> },
);

const PreferredChart = dynamic(
  () => import("@/components/preferred-chart").then((m) => m.PreferredChart),
  { ssr: false, loading: () => <p className="text-sm text-muted-foreground">불러오는 중...</p> },
);

// 차트 좌측 팬 시 단계적으로 넓히는 lookback(년). 마지막 단계 이후는 ALL(from/to 생략).
const STEPS = [1, 3, 10] as const;

function isPreferredTicker(t: Ticker): boolean {
  if (typeof t.is_preferred === "boolean") return t.is_preferred; // 백엔드 제공값 우선
  return t.asset_type === "KR_STOCK" && /^\d{6}$/.test(t.ticker) && t.ticker[5] !== "0";
}
function commonTickerOf(t: Ticker): string | null {
  if (t.common_ticker !== undefined) return t.common_ticker; // 백엔드 제공값 우선(보통주는 null)
  return isPreferredTicker(t) ? t.ticker.slice(0, 5) + "0" : null;
}

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
  const [dividendStepIdx, setDividendStepIdx] = useState<number>(STEPS.length); // ALL 기본
  const [financialPeriod, setFinancialPeriod] = useState<"annual" | "quarter">("annual");
  const [financialSingle, setFinancialSingle] = useState(false);
  const { recent, add: addRecent, remove: removeRecent } = useRecentTickers();

  const preferred = selected ? isPreferredTicker(selected) : false;
  const commonTicker = selected ? commonTickerOf(selected) : null;

  // 첫 hydration 직후 1회 — selected 없고 recent 있으면 최신 종목 자동 선택.
  // 렌더 중 state 조정 패턴 (React 권장, 추가 렌더 없이 동기 반영).
  const [autoSelected, setAutoSelected] = useState(false);
  if (!autoSelected && !selected && recent.length > 0) {
    setAutoSelected(true);
    setSelected(recent[0]);
  }

  // 종목 변경 시 캔들 1Y · 배당 ALL로 리셋 (렌더 중 state 조정 — React 권장 패턴).
  const [prevTicker, setPrevTicker] = useState(selected?.ticker);
  if (selected?.ticker !== prevTicker) {
    setPrevTicker(selected?.ticker);
    setStepIdx(0);
    setDividendStepIdx(STEPS.length);
    setFinancialPeriod("annual");
    setFinancialSingle(false);
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

  const { from: dFrom, to: dTo } = rangeFor(dividendStepIdx);
  const dividends = useQuery({
    queryKey: ["dividends", selected?.ticker, dividendStepIdx],
    queryFn: () =>
      apiGet<GenieResponse<DividendSeries>>("/api/dividends", {
        ticker: selected!.ticker,
        from: dFrom,
        to: dTo,
      }).then((r) => r.data),
    enabled: Boolean(selected),
    placeholderData: keepPreviousData,
  });

  const financials = useQuery({
    queryKey: ["financials", selected?.ticker, financialPeriod, financialSingle],
    queryFn: () =>
      apiGet<GenieResponse<IncomeStatementSeries>>("/api/financials", {
        ticker: selected!.ticker,
        period: financialPeriod,
        single: financialPeriod === "quarter" ? financialSingle : undefined,
      }).then((r) => r.data),
    enabled: Boolean(selected),
    placeholderData: keepPreviousData,
  });

  // 우선주 차트는 전체 기간 1회 fetch (범위 UI는 PreferredChart 내부 소유).
  const prefFundamentals = useQuery({
    queryKey: ["pref-fundamentals", selected?.ticker],
    queryFn: () =>
      apiGet<GenieResponse<FundamentalSeries>>("/api/fundamentals", {
        ticker: selected!.ticker,
        interval: "month",
      }).then((r) => r.data),
    enabled: Boolean(preferred),
    placeholderData: keepPreviousData,
  });

  const prefCandles = useQuery({
    queryKey: ["pref-candles", selected?.ticker],
    queryFn: () =>
      apiGet<GenieResponse<CandleSeries>>("/api/candles/kr-stock", {
        ticker: selected!.ticker,
        interval: "month",
      }).then((r) => r.data),
    enabled: Boolean(preferred),
    placeholderData: keepPreviousData,
  });

  const commonCandles = useQuery({
    queryKey: ["common-candles", commonTicker],
    queryFn: () =>
      apiGet<GenieResponse<CandleSeries>>("/api/candles/kr-stock", {
        ticker: commonTicker!,
        interval: "month",
      }).then((r) => r.data),
    enabled: Boolean(preferred && commonTicker),
    placeholderData: keepPreviousData,
  });

  const commonFundamentals = useQuery({
    queryKey: ["common-fundamentals", commonTicker],
    queryFn: () =>
      apiGet<GenieResponse<FundamentalSeries>>("/api/fundamentals", {
        ticker: commonTicker!,
        interval: "month",
      }).then((r) => r.data),
    enabled: Boolean(preferred && commonTicker),
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
                !preferred && fundamentals.data?.ticker === selected.ticker
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
                <div className="flex gap-1">
                  {(["1Y", "3Y", "10Y", "ALL"] as const).map((label, i) => (
                    <button
                      key={label}
                      type="button"
                      onClick={() => setDividendStepIdx(i)}
                      className={`rounded border px-2 py-0.5 text-xs ${
                        dividendStepIdx === i
                          ? "bg-foreground text-background"
                          : "bg-background hover:bg-muted"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
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

          {preferred ? (
            <section className="space-y-2 pt-2">
              <h3 className="text-sm font-medium">시가배당률 · 괴리율</h3>
              {(prefFundamentals.isLoading || prefCandles.isLoading) && (
                <p className="text-sm text-muted-foreground">불러오는 중...</p>
              )}
              {prefFundamentals.data &&
                prefFundamentals.data.ticker === selected.ticker &&
                prefCandles.data &&
                prefCandles.data.ticker === selected.ticker && (
                  <PreferredChart
                    key={selected.ticker}
                    fundamentals={prefFundamentals.data}
                    candles={prefCandles.data}
                    commonCandles={
                      commonCandles.data?.ticker === commonTicker
                        ? commonCandles.data
                        : null
                    }
                    commonFundamentals={
                      commonFundamentals.data?.ticker === commonTicker
                        ? commonFundamentals.data
                        : null
                    }
                  />
                )}
            </section>
          ) : (
            <section className="space-y-2 pt-2">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                <h3 className="font-medium">재무 요약</h3>
                <div className="flex gap-1">
                  {(["annual", "quarter"] as const).map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setFinancialPeriod(p)}
                      className={`rounded border px-2 py-0.5 text-xs ${
                        financialPeriod === p
                          ? "bg-foreground text-background"
                          : "bg-background hover:bg-muted"
                      }`}
                    >
                      {p === "annual" ? "연간" : "분기"}
                    </button>
                  ))}
                </div>
                {financialPeriod === "quarter" && (
                  <button
                    type="button"
                    onClick={() => setFinancialSingle((v) => !v)}
                    className={`rounded border px-2 py-0.5 text-xs ${
                      financialSingle
                        ? "bg-foreground text-background"
                        : "bg-background hover:bg-muted"
                    }`}
                  >
                    단일분기
                  </button>
                )}
                <span className="text-xs text-muted-foreground">
                  <span style={{ color: "#3b82f6" }}>●</span> 매출
                </span>
                <span className="text-xs text-muted-foreground">
                  <span style={{ color: "#10b981" }}>●</span> 영업이익
                </span>
                <span className="text-xs text-muted-foreground">
                  <span style={{ color: "#f59e0b" }}>●</span> 순이익
                </span>
              </div>
              {financials.isLoading && (
                <p className="text-sm text-muted-foreground">불러오는 중...</p>
              )}
              {financials.isError && (
                <p className="text-sm text-red-600">
                  조회 실패: {(financials.error as Error).message}
                </p>
              )}
              {financials.data && financials.data.ticker === selected.ticker && (
                <FinancialsChart series={financials.data} />
              )}
            </section>
          )}
        </section>
      )}
    </main>
  );
}
