"use client";

import {
  ColorType,
  LineSeries,
  MismatchDirection,
  PriceScaleMode,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type MouseEventParams,
} from "lightweight-charts";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { colorFor } from "@/lib/compare-colors";
import type { CandleSeries } from "@/lib/types";

const CHART_HEIGHT = 560;
// 초기 표시 구간(거래일). 데이터는 전체를 받되 처음엔 최근 ~1년만 보여줌(휠로 더 확대 가능).
const DEFAULT_VISIBLE_BARS = 252;

interface DrawnMeta {
  ticker: string;
  name: string;
  color: string;
  data: LineData[]; // raw 종가 시계열(시간 오름차순) — % 환산은 차트(Percentage 모드)가 담당.
}

/** 공통 구간(겹치는 시작일) 기준으로 시리즈를 클립.
 *
 * 각 시리즈 첫 날짜의 최댓값을 공통 시작일로 잡아 그 이전은 잘라낸다.
 * → 전체 줌 상태에서 모든 선이 같은 x(공통 시작일)에서 출발 → 공정 비교.
 * 값은 raw 종가 그대로. 0% 리베이스는 차트 Percentage 모드가 "보이는 구간
 * 첫 값" 기준으로 자동 수행하므로, 줌/드래그 시 좌측 끝이 항상 0%가 된다.
 */
function clipToCommon(seriesList: CandleSeries[]): { series: DrawnMeta[]; commonStart: string | null } {
  const withPts = seriesList.filter((s) => s.points.length > 0);
  if (withPts.length === 0) return { series: [], commonStart: null };

  // points는 백엔드가 날짜 오름차순 보장.
  const commonStart = withPts.map((s) => s.points[0].date).reduce((a, b) => (a > b ? a : b));

  const out: DrawnMeta[] = [];
  seriesList.forEach((s, i) => {
    if (s.points.length === 0) return;
    const pts = s.points.filter((p) => p.date >= commonStart);
    if (pts.length === 0) return;
    const data = pts
      .filter((p) => p.close) // 0/null 종가 제외(% 환산 baseline 오류 방지).
      .map<LineData>((p) => ({ time: p.date, value: p.close }));
    if (data.length === 0) return;
    out.push({ ticker: s.ticker, name: s.name, color: colorFor(i), data });
  });
  return { series: out, commonStart };
}

const pctFmt = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

/** 보이는 구간 첫 값(base) 대비 상대 수익률(%). base 0/누락이면 0. */
function pct(value: number, base: number | undefined): number {
  return base ? (value / base - 1) * 100 : 0;
}

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
  // 현재 그려진 시리즈 API + 메타(레전드/리베이스 조회용).
  const drawnRef = useRef<{ api: ISeriesApi<"Line">; meta: DrawnMeta }[]>([]);
  const hoveringRef = useRef(false); // hover 중에는 visible-range 갱신이 레전드 date를 지우지 않도록.
  // 종목 추가/제거 후 초기 줌(최근 1년)을 단 1회만 적용 — 이후엔 사용자의 줌/패닝 보존.
  const didInitViewRef = useRef(false);
  const [legend, setLegend] = useState<{ date: string | null; rows: LegendRow[] }>({
    date: null,
    rows: [],
  });

  const { series: drawnList, commonStart } = useMemo(() => clipToCommon(seriesList), [seriesList]);

  // 레전드 = "보이는 구간 첫 값" 기준 상대 수익률. hover 시 십자선 값, 아니면 보이는 우측 끝 값.
  // 차트가 Percentage 모드로 그리는 % 와 동일 기준이라 축·레전드가 일관됨. (read-only — setData 없음)
  const buildLegend = useCallback((param: MouseEventParams | null) => {
    const chart = chartRef.current;
    const drawn = drawnRef.current;
    if (!chart || drawn.length === 0) {
      setLegend({ date: null, rows: [] });
      return;
    }
    const lr = chart.timeScale().getVisibleLogicalRange();
    const hovering = param != null && param.time != null;
    hoveringRef.current = hovering;
    const rows: LegendRow[] = drawn.map(({ api, meta }) => {
      let base: number | undefined;
      let current: number | undefined;
      if (lr) {
        // 보이는 구간 첫 봉(좌)이 base, 마지막 봉(우)이 기본 current. NearestRight/Left로 결측 보정.
        const left = api.dataByIndex(Math.ceil(lr.from), MismatchDirection.NearestRight);
        if (left && "value" in left) base = left.value as number;
        const right = api.dataByIndex(Math.floor(lr.to), MismatchDirection.NearestLeft);
        if (right && "value" in right) current = right.value as number;
      }
      // base·current를 독립적으로 폴백(좌측 봉만 결측 시 current를 전체 마지막값으로 덮지 않도록).
      base ??= meta.data[0]?.value;
      current ??= meta.data[meta.data.length - 1]?.value;
      if (hovering) {
        const d = param.seriesData.get(api);
        if (d && "value" in d) current = d.value as number;
      }
      return {
        ticker: meta.ticker,
        name: meta.name,
        color: meta.color,
        value: current !== undefined ? pct(current, base) : 0,
      };
    });
    setLegend({ date: hovering ? (param.time as string) : null, rows });
  }, []);

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
      // Percentage 모드: 보이는 구간 첫 값을 0%로 자동 리베이스(줌/드래그 시 좌측 끝 0%).
      rightPriceScale: { mode: PriceScaleMode.Percentage, scaleMargins: { top: 0.1, bottom: 0.1 } },
      localization: { percentageFormatter: pctFmt },
      timeScale: { timeVisible: false },
    });
    chartRef.current = chart;

    const onCrosshair = (param: MouseEventParams) => buildLegend(param);
    const onVisibleRange = () => {
      if (!hoveringRef.current) buildLegend(null); // hover 중엔 십자선 핸들러가 갱신.
    };
    chart.subscribeCrosshairMove(onCrosshair);
    // 줌/드래그(마우스 이동 없이도) 시 기본 레전드를 보이는 구간 기준으로 갱신.
    chart.timeScale().subscribeVisibleLogicalRangeChange(onVisibleRange);

    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0;
      if (w > 0) chart.applyOptions({ width: Math.floor(w) });
    });
    ro.observe(el);

    return () => {
      chart.unsubscribeCrosshairMove(onCrosshair);
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(onVisibleRange);
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      drawnRef.current = [];
    };
  }, [buildLegend]);

  // Effect B: 시리즈 재구성. 종목·데이터 변경 시 기존 선 제거 후 다시 그림.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const ts = chart.timeScale();

    // 재구성 전 현재 보이는 시간 범위 보존(종목 추가/제거 시 줌 유지용).
    const prevRange = didInitViewRef.current ? ts.getVisibleRange() : null;

    for (const { api } of drawnRef.current) chart.removeSeries(api);
    drawnRef.current = [];

    drawnList.forEach((s) => {
      const api = chart.addSeries(LineSeries, {
        color: s.color,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerVisible: true,
        baseLineVisible: true, // Percentage 모드의 0% 기준선.
        baseLineColor: "#999",
        baseLineWidth: 1,
      });
      api.setData(s.data);
      drawnRef.current.push({ api, meta: s });
    });

    if (drawnList.length === 0) {
      didInitViewRef.current = false; // 전부 제거되면 다음 첫 그리기에서 1년 줌 재적용.
    } else if (!didInitViewRef.current) {
      // 최초 그리기: 초기 줌을 최근 ~1년으로. fitContent로 전체 범위 잡은 뒤 우측 끝만큼 좁힘.
      ts.fitContent();
      const lr = ts.getVisibleLogicalRange();
      if (lr) ts.setVisibleLogicalRange({ from: Math.max(lr.from, lr.to - DEFAULT_VISIBLE_BARS), to: lr.to });
      didInitViewRef.current = true;
    } else if (prevRange) {
      ts.setVisibleRange(prevRange); // 이후 추가/제거: 사용자의 줌/패닝 보존.
    } else {
      ts.fitContent();
    }
    buildLegend(null);
  }, [drawnList, buildLegend]);

  // Effect C: 우측 가격축 영역 휠 → 가격(세로) 범위 직접 zoom. (candle-chart Effect H와 동일 패턴)
  // 본문 영역은 라이브러리 기본(시간축 zoom) 그대로. 멀티 시리즈는 우측 스케일 공유 → 첫 시리즈 스케일 사용.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const container = chart.chartElement();

    const onWheel = (e: WheelEvent) => {
      const ps = drawnRef.current[0]?.api.priceScale();
      if (!ps) return;
      const rect = container.getBoundingClientRect();
      const axisLeft = rect.right - ps.width();
      if (e.clientX < axisLeft) return; // 차트 본문 → 시간축 zoom 그대로

      e.preventDefault();
      e.stopImmediatePropagation();

      const r = ps.getVisibleRange();
      if (!r) return;
      ps.setAutoScale(false);
      const px = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
      const k = Math.exp(px * 0.002); // <1: zoom in / >1: zoom out
      const mid = (r.from + r.to) / 2;
      ps.setVisibleRange({ from: mid - (mid - r.from) * k, to: mid + (r.to - mid) * k });
    };

    container.addEventListener("wheel", onWheel, { passive: false, capture: true });
    return () => container.removeEventListener("wheel", onWheel, { capture: true });
  }, []);

  // 전체 보기: 시간축 전체 복귀 + 가격축 autoScale 재활성(세로 수동 줌 해제).
  const resetZoom = () => {
    const chart = chartRef.current;
    if (!chart) return;
    drawnRef.current[0]?.api.priceScale().setAutoScale(true);
    chart.timeScale().fitContent();
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        {legend.rows.length === 0 ? (
          <span className="text-muted-foreground">비교할 종목을 선택하세요</span>
        ) : (
          <>
            {legend.date && <span className="font-medium tabular-nums">{legend.date}</span>}
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
      <div className="flex items-center justify-between gap-2">
        {commonStart && drawnList.length > 0 ? (
          <p className="text-xs text-muted-foreground">
            보이는 구간 시작점 0% 기준 정규화 (수정주가) · 휠로 확대/축소, 드래그로 이동
          </p>
        ) : (
          <span />
        )}
        {drawnList.length > 0 && (
          <button
            type="button"
            onClick={resetZoom}
            className="shrink-0 rounded border bg-background px-2 py-0.5 text-xs hover:bg-muted"
          >
            전체 보기
          </button>
        )}
      </div>
      <div ref={ref} className="w-full" style={{ height: CHART_HEIGHT }} />
    </div>
  );
}
