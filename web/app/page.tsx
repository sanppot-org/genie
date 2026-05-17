"use client";

import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { useDeferredValue, useState } from "react";

import { Input } from "@/components/ui/input";
import { apiGet } from "@/lib/api";
import type { CandleSeries, FundamentalSeries, GenieResponse, Ticker } from "@/lib/types";

const CandleChart = dynamic(
  () => import("@/components/candle-chart").then((m) => m.CandleChart),
  {
    ssr: false,
    loading: () => <p className="text-sm text-muted-foreground">차트 로딩 중...</p>,
  },
);

function lastYearRange(): { from: string; to: string } {
  const to = new Date();
  const from = new Date();
  from.setFullYear(to.getFullYear() - 1);
  const fmt = (d: Date) =>
    `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`;
  return { from: fmt(from), to: fmt(to) };
}

export default function Home() {
  const [q, setQ] = useState("");
  const deferredQ = useDeferredValue(q);
  const [selected, setSelected] = useState<Ticker | null>(null);

  const tickers = useQuery({
    queryKey: ["tickers", deferredQ],
    queryFn: () =>
      apiGet<GenieResponse<Ticker[]>>("/api/tickers", { q: deferredQ, limit: 10 }).then(
        (r) => r.data,
      ),
    enabled: deferredQ.trim().length > 0,
  });

  const { from, to } = lastYearRange();
  const fundamentals = useQuery({
    queryKey: ["fundamentals", selected?.ticker, from, to],
    queryFn: () =>
      apiGet<GenieResponse<FundamentalSeries>>("/api/fundamentals", {
        ticker: selected!.ticker,
        from,
        to,
      }).then((r) => r.data),
    enabled: Boolean(selected),
  });

  const candles = useQuery({
    queryKey: ["candles", selected?.ticker, from, to],
    queryFn: () =>
      apiGet<GenieResponse<CandleSeries>>("/api/candles/kr-stock", {
        ticker: selected!.ticker,
        from,
        to,
      }).then((r) => r.data),
    enabled: Boolean(selected),
  });

  return (
    <main className="w-full p-6 space-y-6">
      <h1 className="text-2xl font-semibold">Genie — 종목 차트</h1>

      <Input
        className="max-w-3xl"
        placeholder="ticker 또는 종목명 (예: 005930, 삼성)"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />

      {deferredQ.trim().length > 0 && (
        <section className="max-w-3xl space-y-1">
          {tickers.isLoading && <p className="text-sm text-muted-foreground">불러오는 중...</p>}
          {tickers.isError && (
            <p className="text-sm text-red-600">검색 실패: {(tickers.error as Error).message}</p>
          )}
          {tickers.data && tickers.data.length === 0 && (
            <p className="text-sm text-muted-foreground">결과 없음</p>
          )}
          <ul className="space-y-1">
            {tickers.data?.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => setSelected(t)}
                  className={`w-full text-left rounded-md border px-3 py-2 hover:bg-muted ${
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

      {selected && (
        <section className="space-y-2 border-t pt-4">
          <h2 className="text-lg font-medium">
            {selected.name}{" "}
            <span className="font-mono text-sm text-muted-foreground">({selected.ticker})</span>
          </h2>
          <p className="text-xs text-muted-foreground">최근 1년 주가 + PER</p>
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
          {candles.data && (
            <CandleChart points={candles.data.points} perPoints={fundamentals.data?.points} />
          )}
        </section>
      )}
    </main>
  );
}
