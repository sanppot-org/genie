"use client";

import { CandlestickSeries, ColorType, createChart } from "lightweight-charts";
import { useEffect, useRef } from "react";

import type { CandlePoint } from "@/lib/types";

interface Props {
  points: CandlePoint[];
}

export function CandleChart({ points }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || points.length === 0) return;

    const chart = createChart(el, {
      width: el.clientWidth,
      height: 360,
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

    // 한국식 색상: 상승=빨강, 하락=파랑
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#d24f45",
      downColor: "#1261c4",
      borderVisible: false,
      wickUpColor: "#d24f45",
      wickDownColor: "#1261c4",
    });
    series.setData(
      points.map((p) => ({
        time: p.date,
        open: p.open,
        high: p.high,
        low: p.low,
        close: p.close,
      })),
    );
    chart.timeScale().fitContent();

    // contentRect.width = 레이아웃이 정한 컨테이너 박스 폭.
    // lightweight-charts가 el 안에 table을 주입해도 el 자체(w-full)의
    // content-box 폭은 부모 기준이라 영향 없음 → 좁게 고착되는 피드백 루프 방지.
    // ResizeObserver는 observe() 시 현재 크기로 콜백을 1회 즉시 실행하므로
    // 초기 폭도 여기서 보정된다.
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0;
      if (w > 0) chart.applyOptions({ width: Math.floor(w) });
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [points]);

  if (points.length === 0) {
    return <p className="text-sm text-muted-foreground">데이터 없음</p>;
  }
  return <div ref={ref} className="w-full" style={{ height: 360 }} />;
}
