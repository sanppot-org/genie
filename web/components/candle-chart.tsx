"use client";

import {
  CandlestickSeries,
  ColorType,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type LogicalRange,
  type WhitespaceData,
} from "lightweight-charts";
import { useEffect, useRef } from "react";

import type { CandlePoint, FundamentalPoint } from "@/lib/types";

interface Props {
  points: CandlePoint[];
  perPoints?: FundamentalPoint[];
  /** 차트를 왼쪽 첫 바 너머로 끌었을 때 (더 넓은 과거 요청). */
  onNeedMore?: () => void;
  /** 아직 더 가져올 과거가 있는지. false면 트리거 안 함. */
  hasMore?: boolean;
}

export function CandleChart({ points, perPoints, onNeedMore, hasMore }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const perRef = useRef<ISeriesApi<"Line"> | null>(null);
  const didFitRef = useRef(false);
  const loadingRef = useRef(false);
  const onNeedMoreRef = useRef<(() => void) | undefined>(undefined);
  const hasMoreRef = useRef(false);

  // 구독 핸들러는 마운트 시 1회만 생성되므로 최신 prop을 ref로 읽는다.
  // 렌더 중 ref 쓰기는 금지 → 매 커밋 후 effect에서 동기화.
  useEffect(() => {
    onNeedMoreRef.current = onNeedMore;
    hasMoreRef.current = hasMore ?? false;
  });

  // Effect A: 차트·캔들 시리즈·구독을 마운트당 1회 생성.
  useEffect(() => {
    const el = ref.current;
    if (!el || points.length === 0) return;

    const chart = createChart(el, {
      width: el.clientWidth,
      height: 480,
      layout: {
        background: { type: ColorType.Solid, color: "white" },
        textColor: "#333",
      },
      grid: {
        horzLines: { color: "#eee" },
        vertLines: { color: "#eee" },
      },
      timeScale: { timeVisible: false },
    });
    chartRef.current = chart;

    // 한국식 색상: 상승=빨강, 하락=파랑
    candleRef.current = chart.addSeries(CandlestickSeries, {
      upColor: "#d24f45",
      downColor: "#1261c4",
      borderVisible: false,
      wickUpColor: "#d24f45",
      wickDownColor: "#1261c4",
    });

    // 왼쪽 끝(첫 바)보다 더 끌면 barsBefore < 0 → 과거 더 요청.
    // 초기 fitContent 직후엔 barsBefore≈0이라 오발동 없음.
    const onRange = (lr: LogicalRange | null) => {
      if (!lr || !candleRef.current) return;
      const bi = candleRef.current.barsInLogicalRange(lr);
      if (bi && bi.barsBefore < -5 && !loadingRef.current && hasMoreRef.current) {
        loadingRef.current = true;
        onNeedMoreRef.current?.();
      }
    };
    chart.timeScale().subscribeVisibleLogicalRangeChange(onRange);

    // contentRect.width = 레이아웃이 정한 컨테이너 박스 폭.
    // chart가 el 안에 table을 주입해도 el(w-full) content-box 폭은
    // 부모 기준이라 영향 없음 → 좁게 고착되는 피드백 루프 방지.
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0;
      if (w > 0) chart.applyOptions({ width: Math.floor(w) });
    });
    ro.observe(el);

    return () => {
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(onRange);
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      perRef.current = null;
      didFitRef.current = false;
    };
    // 마운트당 1회만. points 변경은 Effect B가 처리.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Effect B: 캔들 데이터 갱신. 최초 1회만 fitContent, 이후엔 시간 구간 보존.
  useEffect(() => {
    const chart = chartRef.current;
    const series = candleRef.current;
    if (!chart || !series) return;

    const prev = didFitRef.current ? chart.timeScale().getVisibleRange() : null;
    series.setData(
      points.map((p) => ({
        time: p.date,
        open: p.open,
        high: p.high,
        low: p.low,
        close: p.close,
      })),
    );
    if (!didFitRef.current) {
      chart.timeScale().fitContent();
      didFitRef.current = true;
    } else if (prev) {
      chart.timeScale().setVisibleRange(prev);
    }
    loadingRef.current = false;
  }, [points]);

  // Effect C: PER 라인(pane 1). perPoints는 별 쿼리라 마운트 후 도착 → 지연 생성.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !perPoints || perPoints.length === 0) return;

    if (!perRef.current) {
      perRef.current = chart.addSeries(
        LineSeries,
        {
          color: "#0ea5e9",
          lineWidth: 2,
          priceLineVisible: false,
          title: "PER",
        },
        1,
      );
      // 주가 : PER = 3 : 1
      const panes = chart.panes();
      panes[0]?.setStretchFactor(3);
      panes[1]?.setStretchFactor(1);
    }
    // null은 whitespace로 넣어 갭 유지 (connectNulls=false 동작).
    perRef.current.setData(
      perPoints.map<LineData | WhitespaceData>((p) =>
        p.per == null ? { time: p.date } : { time: p.date, value: p.per },
      ),
    );
  }, [perPoints]);

  if (points.length === 0) {
    return <p className="text-sm text-muted-foreground">데이터 없음</p>;
  }
  return <div ref={ref} className="w-full" style={{ height: 480 }} />;
}
