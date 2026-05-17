"use client";

import {
  CandlestickSeries,
  ColorType,
  LineSeries,
  createChart,
  type LineData,
  type WhitespaceData,
} from "lightweight-charts";
import { useEffect, useRef } from "react";

import type { CandlePoint, FundamentalPoint } from "@/lib/types";

interface Props {
  points: CandlePoint[];
  perPoints?: FundamentalPoint[];
}

export function CandleChart({ points, perPoints }: Props) {
  const ref = useRef<HTMLDivElement>(null);

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

    // pane 0: 캔들 (한국식 색상: 상승=빨강, 하락=파랑)
    const candle = chart.addSeries(CandlestickSeries, {
      upColor: "#d24f45",
      downColor: "#1261c4",
      borderVisible: false,
      wickUpColor: "#d24f45",
      wickDownColor: "#1261c4",
    });
    candle.setData(
      points.map((p) => ({
        time: p.date,
        open: p.open,
        high: p.high,
        low: p.low,
        close: p.close,
      })),
    );

    // pane 1: PER 라인 (MACD/거래량처럼 아래 페인). null은 whitespace로
    // 넣어 갭 유지 (Recharts connectNulls={false} 동작과 동일).
    if (perPoints && perPoints.length > 0) {
      const per = chart.addSeries(
        LineSeries,
        {
          color: "#0ea5e9",
          lineWidth: 2,
          priceLineVisible: false,
          title: "PER",
        },
        1,
      );
      per.setData(
        perPoints.map<LineData | WhitespaceData>((p) =>
          p.per == null ? { time: p.date } : { time: p.date, value: p.per },
        ),
      );
      // 주가 : PER = 3 : 1
      const panes = chart.panes();
      panes[0]?.setStretchFactor(3);
      panes[1]?.setStretchFactor(1);
    }

    chart.timeScale().fitContent();

    // contentRect.width = 레이아웃이 정한 컨테이너 박스 폭.
    // lightweight-charts가 el 안에 table을 주입해도 el 자체(w-full)의
    // content-box 폭은 부모 기준이라 영향 없음 → 좁게 고착되는 피드백 루프 방지.
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0;
      if (w > 0) chart.applyOptions({ width: Math.floor(w) });
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [points, perPoints]);

  if (points.length === 0) {
    return <p className="text-sm text-muted-foreground">데이터 없음</p>;
  }
  return <div ref={ref} className="w-full" style={{ height: 480 }} />;
}
