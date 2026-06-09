"use client";

import {
  ColorType,
  LineSeries,
  LineStyle,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type MouseEventParams,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

import { colorFor } from "@/lib/compare-colors";
import type { CandleSeries } from "@/lib/types";

const CHART_HEIGHT = 560;

interface NormSeries {
  ticker: string;
  name: string;
  color: string;
  data: LineData[]; // 정규화 수익률(%) 시계열
  changePct: number; // 구간 전체 수익률(마지막 값)
}

/** 공통 구간(겹치는 시작일) 기준 0% 리베이스.
 *
 * 각 시리즈 첫 날짜의 최댓값을 공통 시작일로 잡아 그 이전은 잘라내고,
 * 공통 시작일 종가를 기준(0%)으로 (close/base - 1)*100 계산.
 * → 모든 선이 좌측 끝에서 0%로 출발 → 같은 기간 상대 비교가 공정.
 */
function normalize(seriesList: CandleSeries[]): { series: NormSeries[]; commonStart: string | null } {
  const withPts = seriesList.filter((s) => s.points.length > 0);
  if (withPts.length === 0) return { series: [], commonStart: null };

  // points는 백엔드가 날짜 오름차순 보장(캔들·SMA 동작 전제와 동일).
  const commonStart = withPts
    .map((s) => s.points[0].date)
    .reduce((a, b) => (a > b ? a : b));

  const out: NormSeries[] = [];
  seriesList.forEach((s, i) => {
    if (s.points.length === 0) return;
    const pts = s.points.filter((p) => p.date >= commonStart);
    if (pts.length === 0) return;
    const base = pts[0].close;
    if (!base) return;
    const data = pts.map<LineData>((p) => ({
      time: p.date,
      value: (p.close / base - 1) * 100,
    }));
    out.push({
      ticker: s.ticker,
      name: s.name,
      color: colorFor(i),
      data,
      changePct: data[data.length - 1].value,
    });
  });
  return { series: out, commonStart };
}

const pctFmt = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

interface LegendRow {
  ticker: string;
  name: string;
  color: string;
  value: number;
}

interface Props {
  /** 비교할 종목 캔들 시리즈(정렬·색은 입력 순서 기준). */
  seriesList: CandleSeries[];
}

export function CompareChart({ seriesList }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  // 현재 그려진 시리즈 API + 메타(crosshair 레전드 조회용).
  const drawnRef = useRef<{ api: ISeriesApi<"Line">; meta: NormSeries }[]>([]);
  const [legend, setLegend] = useState<{ date: string | null; rows: LegendRow[] }>({
    date: null,
    rows: [],
  });

  const { series: normalized, commonStart } = useMemo(
    () => normalize(seriesList),
    [seriesList],
  );

  // Effect A: 차트·구독을 마운트당 1회 생성.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const chart = createChart(el, {
      width: el.clientWidth,
      height: CHART_HEIGHT,
      layout: {
        background: { type: ColorType.Solid, color: "white" },
        textColor: "#333",
      },
      grid: {
        horzLines: { color: "#eee" },
        vertLines: { color: "#eee" },
      },
      rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } },
      localization: { priceFormatter: pctFmt },
      timeScale: { timeVisible: false },
    });
    chartRef.current = chart;

    const onCrosshair = (param: MouseEventParams) => {
      const drawn = drawnRef.current;
      if (drawn.length === 0) return;
      const hovering = param.time != null;
      const rows: LegendRow[] = drawn.map(({ api, meta }) => {
        let value = meta.changePct; // hover 밖이면 구간 전체 수익률
        if (hovering) {
          const d = param.seriesData.get(api);
          if (d && "value" in d) value = d.value as number;
        }
        return { ticker: meta.ticker, name: meta.name, color: meta.color, value };
      });
      const date = hovering ? (param.time as string) : null;
      setLegend({ date, rows });
    };
    chart.subscribeCrosshairMove(onCrosshair);

    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0;
      if (w > 0) chart.applyOptions({ width: Math.floor(w) });
    });
    ro.observe(el);

    return () => {
      chart.unsubscribeCrosshairMove(onCrosshair);
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      drawnRef.current = [];
    };
  }, []);

  // Effect B: 시리즈 재구성. 종목·데이터 변경 시 기존 선 제거 후 다시 그림.
  // 비교 대상 개수가 가변이라 매번 재생성(추적 비용보다 단순함 우선).
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    for (const { api } of drawnRef.current) chart.removeSeries(api);
    drawnRef.current = [];

    normalized.forEach((s, i) => {
      const api = chart.addSeries(LineSeries, {
        color: s.color,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerVisible: true,
      });
      api.setData(s.data);
      // 0% 기준선은 첫 시리즈에만 1회(차트 폭 전체에 그려짐).
      if (i === 0) {
        api.createPriceLine({
          price: 0,
          color: "#999",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: false,
          title: "",
        });
      }
      drawnRef.current.push({ api, meta: s });
    });

    if (normalized.length > 0) chart.timeScale().fitContent();

    // hover 전 기본 레전드: 각 종목 구간 전체 수익률.
    setLegend({
      date: null,
      rows: normalized.map((s) => ({
        ticker: s.ticker,
        name: s.name,
        color: s.color,
        value: s.changePct,
      })),
    });
  }, [normalized]);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        {legend.rows.length === 0 ? (
          <span className="text-muted-foreground">비교할 종목을 선택하세요</span>
        ) : (
          <>
            {legend.date && (
              <span className="font-medium tabular-nums">{legend.date}</span>
            )}
            {legend.rows.map((r) => (
              <span key={r.ticker} className="inline-flex items-center gap-1.5 tabular-nums">
                <span style={{ color: r.color }}>●</span>
                <span>{r.name}</span>
                <span style={{ color: r.color }} className="font-medium">
                  {pctFmt(r.value)}
                </span>
              </span>
            ))}
          </>
        )}
      </div>
      {commonStart && normalized.length > 0 && (
        <p className="text-xs text-muted-foreground">
          공통 시작일 <span className="tabular-nums">{commonStart}</span> 기준 0% 리베이스
          (수정주가)
        </p>
      )}
      <div ref={ref} className="w-full" style={{ height: CHART_HEIGHT }} />
    </div>
  );
}
