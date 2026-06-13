"use client";

import { keepPreviousData, useQueries, useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { useDeferredValue, useMemo, useState } from "react";

import { colorFor } from "@/lib/compare-colors";
import { Input } from "@/components/ui/input";
import { apiGet } from "@/lib/api";
import type { CandleSeries, GenieResponse, Ticker } from "@/lib/types";
import { useRecentTickers } from "@/lib/use-recent-tickers";

const CompareChart = dynamic(
  () => import("@/components/compare-chart").then((m) => m.CompareChart),
  {
    ssr: false,
    loading: () => <p className="text-sm text-muted-foreground">차트 로딩 중...</p>,
  },
);

// 비교 가능한 최대 종목 수(색 팔레트·가독성 한도).
const MAX_COMPARE = 8;

export default function ComparePage() {
  const [q, setQ] = useState("");
  const [searchFocused, setSearchFocused] = useState(false);
  const deferredQ = useDeferredValue(q);
  const [selected, setSelected] = useState<Ticker[]>([]);
  const { recent, add: addRecent, remove: removeRecent } = useRecentTickers();

  const tickers = useQuery({
    queryKey: ["tickers", deferredQ],
    queryFn: () =>
      apiGet<GenieResponse<Ticker[]>>("/api/tickers", { q: deferredQ, limit: 10 }).then(
        (r) => r.data,
      ),
    enabled: deferredQ.trim().length > 0,
  });

  // 종목별 캔들을 병렬 fetch. 멀티심볼 엔드포인트가 없어 클라에서 fan-out.
  // from/to 생략 → 전체 기간 1회 조회. 기간 조절은 차트 휠 줌/드래그로(서버 재조회 없음).
  const candleQueries = useQueries({
    queries: selected.map((t) => ({
      queryKey: ["compare-candles", t.ticker],
      queryFn: () =>
        apiGet<GenieResponse<CandleSeries>>("/api/candles/kr-stock", {
          ticker: t.ticker,
          price: "adjusted", // 액면분할 보정 — 정규화 왜곡 방지.
        }).then((r) => r.data),
      placeholderData: keepPreviousData,
    })),
  });

  const isLoading = candleQueries.some((qr) => qr.isLoading);
  const errored = selected.filter((_, i) => candleQueries[i]?.isError);

  // 종목·구간·로드상태가 실제로 바뀔 때만 변하는 시그니처(마지막 날짜+개수).
  const seriesSig = selected
    .map((t, i) => {
      const pts = candleQueries[i]?.data?.points;
      return `${t.ticker}:${pts?.length ?? 0}:${pts?.[pts.length - 1]?.date ?? ""}`;
    })
    .join("|");

  // selected와 1:1 정렬 유지(결측은 빈 points 자리표시) → 차트 색 인덱스가 칩 색과 일치.
  // 빈 시리즈는 clipToCommon이 건너뛰되, colorFor(i)가 원본 인덱스 i를 쓰므로 칩 색과 정합.
  // 시그니처로 메모이즈 → 검색 입력 등 무관 렌더에서 차트 재생성·줌 리셋 방지.
  const seriesList = useMemo<CandleSeries[]>(
    () =>
      selected.map((t, i) => {
        const d = candleQueries[i]?.data;
        return d && d.points.length > 0 ? d : { ticker: t.ticker, name: t.name, points: [] };
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [seriesSig],
  );
  const hasData = seriesList.some((s) => s.points.length > 0);

  const addTicker = (t: Ticker) => {
    setSelected((prev) =>
      prev.some((p) => p.ticker === t.ticker) || prev.length >= MAX_COMPARE
        ? prev
        : [...prev, t],
    );
    addRecent(t); // "차트" 탭과 동일 최근 기록(genie:recentTickers) 공유.
    setQ("");
    setSearchFocused(false);
    (document.activeElement as HTMLElement | null)?.blur();
  };

  const removeTicker = (ticker: string) =>
    setSelected((prev) => prev.filter((p) => p.ticker !== ticker));

  return (
    <main className="w-full p-6 space-y-6">
      <h1 className="text-2xl font-semibold">종목 비교 — 상대 수익률</h1>
      <p className="text-sm text-muted-foreground">
        여러 종목을 같은 기간 동안 누가 더/덜 올랐는지 비교 (보이는 구간 시작점 0% 기준 정규화).
      </p>

      <div className="relative max-w-3xl">
        <Input
          placeholder={
            selected.length >= MAX_COMPARE
              ? `최대 ${MAX_COMPARE}개까지 비교 가능`
              : "ticker 또는 종목명 추가 (예: 005930, 삼성)"
          }
          value={q}
          disabled={selected.length >= MAX_COMPARE}
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
              {tickers.data?.map((t) => {
                const picked = selected.some((p) => p.ticker === t.ticker);
                return (
                  <li key={t.ticker}>
                    <button
                      type="button"
                      disabled={picked}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => addTicker(t)}
                      className={`w-full rounded-md px-3 py-2 text-left hover:bg-muted disabled:opacity-40 ${
                        picked ? "bg-muted" : ""
                      }`}
                    >
                      <span className="font-mono text-sm">{t.ticker}</span>
                      <span className="ml-2">{t.name}</span>
                      <span className="ml-2 text-xs text-muted-foreground">{t.asset_type}</span>
                      {picked && <span className="ml-2 text-xs text-muted-foreground">추가됨</span>}
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        )}
      </div>

      {selected.length > 0 && (
        <div className="flex max-w-3xl flex-wrap gap-2">
          {selected.map((t, i) => (
            <span
              key={t.ticker}
              className="inline-flex items-center rounded-full border bg-background pl-3 text-sm"
            >
              <span style={{ color: colorFor(i) }} className="mr-1.5">
                ●
              </span>
              <span className="font-mono">{t.ticker}</span>
              <span className="ml-1.5">{t.name}</span>
              <button
                type="button"
                aria-label={`${t.name} 비교 제거`}
                onClick={() => removeTicker(t.ticker)}
                className="px-2 py-1 text-muted-foreground hover:text-foreground"
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}

      {recent.some((t) => !selected.some((s) => s.ticker === t.ticker)) && (
        <div className="flex max-w-3xl flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground">최근</span>
          {recent
            .filter((t) => !selected.some((s) => s.ticker === t.ticker))
            .map((t) => (
              <span
                key={t.ticker}
                className="inline-flex items-center rounded-full border bg-background pl-3 text-sm"
              >
                <button
                  type="button"
                  disabled={selected.length >= MAX_COMPARE}
                  onClick={() => addTicker(t)}
                  className="py-1 hover:text-foreground disabled:opacity-40"
                >
                  <span className="font-mono">{t.ticker}</span>
                  <span className="ml-1.5">{t.name}</span>
                </button>
                <button
                  type="button"
                  aria-label={`${t.name} 최근 기록 삭제`}
                  onClick={() => removeRecent(t.ticker)}
                  className="px-2 py-1 text-muted-foreground hover:text-foreground"
                >
                  ✕
                </button>
              </span>
            ))}
        </div>
      )}

      {errored.length > 0 && (
        <p className="text-sm text-red-600">
          조회 실패: {errored.map((t) => t.name).join(", ")}
        </p>
      )}

      {selected.length === 0 ? (
        <p className="text-sm text-muted-foreground border-t pt-4">
          종목을 2개 이상 추가하면 비교 차트가 표시됩니다.
        </p>
      ) : (
        <section className="border-t pt-4">
          {isLoading && !hasData ? (
            <p className="text-sm text-muted-foreground">불러오는 중...</p>
          ) : (
            <CompareChart seriesList={seriesList} />
          )}
        </section>
      )}
    </main>
  );
}
