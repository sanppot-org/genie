"use client";

import {
  ColorType,
  HistogramSeries,
  LineSeries,
  LineStyle,
  createChart,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type LineData,
  type MouseEventParams,
  type WhitespaceData,
} from "lightweight-charts";
import { useEffect, useRef, useState } from "react";

import type { CandleSeries, FundamentalSeries } from "@/lib/types";

const COLOR_DIV = "#14b8a6"; // teal-500 — 시가배당률 (좌축)
const COLOR_PRICE = "#475569"; // slate-600 — 우선주 주가 (우축)
const COLOR_COMMON_PRICE = "#0ea5e9"; // sky-500 — 보통주 주가 (우축, pane 0)
const COLOR_EPS = "#f59e0b"; // amber-500 — 보통주 EPS (pane 1)
const COLOR_DPS = "#10b981"; // emerald-500 — 우선주 DPS (pane 1)
const COLOR_DISC = "#8b5cf6"; // violet-500 — 괴리율 (pane 2)

const CHART_HEIGHT = 720;

const DEFAULT_YEARS = 3;

interface PreferredChartProps {
  fundamentals: FundamentalSeries;
  candles: CandleSeries;
  commonCandles?: CandleSeries | null;
  commonFundamentals?: FundamentalSeries | null;
}

// 상단 hover 레전드 (차트 밖이면 최신값).
interface LegendData {
  date: string;
  div: number | null; // 시가배당률 %
  price: number | null; // 우선주 주가 원
  commonPrice: number | null; // 보통주 주가 원
  eps: number | null; // 보통주 EPS 원
  dps: number | null; // 우선주 DPS 원
  disc: number | null; // 괴리율 %
}

function LegendOverlay({
  d,
  hasCommonPrice,
  hasEps,
  hasDps,
  hasDisc,
}: {
  d: LegendData;
  hasCommonPrice: boolean;
  hasEps: boolean;
  hasDps: boolean;
  hasDisc: boolean;
}) {
  const won = (v: number) => Math.round(v).toLocaleString("ko-KR");
  return (
    <div className="pointer-events-none absolute left-2 top-2 z-10 flex flex-wrap items-center gap-x-3 gap-y-0.5 rounded bg-white/85 px-2 py-1 text-xs tabular-nums shadow-sm">
      <span className="font-medium">{d.date}</span>
      <span style={{ color: COLOR_DIV }}>배당 {d.div != null ? `${d.div.toFixed(2)}%` : "-"}</span>
      <span style={{ color: COLOR_PRICE }}>우선주 주가 {d.price != null ? `${won(d.price)}원` : "-"}</span>
      {hasCommonPrice && (
        <span style={{ color: COLOR_COMMON_PRICE }}>보통주 주가 {d.commonPrice != null ? `${won(d.commonPrice)}원` : "-"}</span>
      )}
      {hasEps && (
        <span style={{ color: COLOR_EPS }}>EPS {d.eps != null ? `${won(d.eps)}원` : "-"}</span>
      )}
      {hasDps && (
        <span style={{ color: COLOR_DPS }}>DPS(주당배당금) {d.dps != null ? `${won(d.dps)}원` : "-"}</span>
      )}
      {hasDisc && (
        <span style={{ color: COLOR_DISC }}>괴리율 {d.disc != null ? `${d.disc.toFixed(2)}%` : "-"}</span>
      )}
    </div>
  );
}

// 월조인 괴리율: (보통주close - 우선주close) / 보통주close * 100.
// 월말 거래일 불일치 방지를 위해 YYYY-MM 키로 조인, 결과 time은 우선주 실제 date 유지.
function calcDiscount(pref: CandleSeries, common: CandleSeries): LineData[] {
  const comClose = new Map(common.points.map((p) => [p.date.slice(0, 7), p.close]));
  const out: LineData[] = [];
  for (const p of pref.points) {
    const com = comClose.get(p.date.slice(0, 7));
    if (com == null || com === 0) continue;
    out.push({ time: p.date, value: ((com - p.close) / com) * 100 });
  }
  out.sort((a, b) => (a.time as string).localeCompare(b.time as string));
  return out;
}

// 날짜 문자열(YYYY-MM-DD)에서 N년 전 날짜를 문자열 산술로 계산 (Date 객체 타임존 문제 회피).
// 2월 29일처럼 존재하지 않는 날짜는 28일로 방어.
function yearsBefore(lastDate: string, years: number): string {
  const [y, m, d] = lastDate.split("-").map(Number);
  const newYear = y - years;
  // 2월 29일 → 평년이면 28일로 방어
  const isLeap = (yr: number) => (yr % 4 === 0 && yr % 100 !== 0) || yr % 400 === 0;
  const day = m === 2 && d === 29 && !isLeap(newYear) ? 28 : d;
  return `${newYear}-${String(m).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

// pts 기준 N년 구간의 from 날짜를 반환. 데이터가 3년 미만이면 null(→ fitContent).
function rangeFromYears(pts: { date: string }[], years: number): { from: string; to: string } | null {
  if (pts.length === 0) return null;
  const last = pts[pts.length - 1].date;
  const first = pts[0].date;
  const from = yearsBefore(last, years);
  if (from <= first) return null; // 데이터 전체가 N년 이내 → fitContent
  return { from, to: last };
}

export function PreferredChart({
  fundamentals,
  candles,
  commonCandles,
  commonFundamentals,
}: PreferredChartProps) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const divRef = useRef<ISeriesApi<"Line"> | null>(null);
  const priceRef = useRef<ISeriesApi<"Line"> | null>(null);
  const commonPriceRef = useRef<ISeriesApi<"Line"> | null>(null);
  const epsRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const dpsRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const discRef = useRef<ISeriesApi<"Line"> | null>(null);
  const divAvgLineRef = useRef<IPriceLine | null>(null);
  const discAvgLineRef = useRef<IPriceLine | null>(null);
  const didRangeRef = useRef(false);

  const [legend, setLegend] = useState<LegendData | null>(null);

  const hasCommonPrice = Boolean(commonCandles && commonCandles.points.length > 0);
  const hasEps = Boolean(commonFundamentals && commonFundamentals.points.length > 0);
  const hasDps = fundamentals.points.some((p) => p.dps != null && p.dps !== 0);
  const hasDisc = Boolean(commonCandles && commonCandles.points.length > 0);
  const hasDividend = fundamentals.points.some((p) => p.div != null && p.div !== 0);

  // 구독 핸들러는 마운트 1회 생성 → 최신 props/시리즈를 ref로 읽는다.
  const propsRef = useRef({ fundamentals, candles });
  useEffect(() => {
    propsRef.current = { fundamentals, candles };
  });

  // Effect A: 차트·기본 시리즈(div, price)·구독을 마운트당 1회 생성.
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
      leftPriceScale: { visible: true },
      rightPriceScale: { visible: true },
      timeScale: { timeVisible: false },
    });
    chartRef.current = chart;

    // 시가배당률 — 좌축 (%)
    divRef.current = chart.addSeries(LineSeries, {
      color: COLOR_DIV,
      lineWidth: 2,
      priceScaleId: "left",
      priceLineVisible: false,
      title: "시가배당률",
    });
    // 주가 — 우축 (원)
    priceRef.current = chart.addSeries(LineSeries, {
      color: COLOR_PRICE,
      lineWidth: 2,
      priceLineVisible: false,
      title: "주가",
    });

    // pane1 히스토그램: 생성 순서 고정 → EPS 먼저, DPS 나중 → DPS가 항상 위(앞)에 렌더.
    epsRef.current = chart.addSeries(
      HistogramSeries,
      { color: COLOR_EPS, priceLineVisible: false, lastValueVisible: false },
      1,
    );
    dpsRef.current = chart.addSeries(
      HistogramSeries,
      { color: COLOR_DPS, priceLineVisible: false, lastValueVisible: false },
      1,
    );

    const onCrosshair = (param: MouseEventParams) => {
      const { fundamentals: f, candles: c } = propsRef.current;
      const read = (s: ISeriesApi<"Line"> | ISeriesApi<"Histogram"> | null): number | null => {
        if (!param.time || !s) return null;
        const d = param.seriesData.get(s);
        return d && "value" in d ? (d.value as number) : null;
      };
      const hovering = param.time != null;
      if (hovering) {
        setLegend({
          date: String(param.time),
          div: read(divRef.current),
          price: read(priceRef.current),
          commonPrice: read(commonPriceRef.current),
          eps: read(epsRef.current),
          dps: read(dpsRef.current),
          disc: read(discRef.current),
        });
        return;
      }
      // 차트 밖 → 최신값.
      const lastF = f.points[f.points.length - 1] ?? null;
      const lastC = c.points[c.points.length - 1] ?? null;
      setLegend({
        date: lastC?.date ?? lastF?.date ?? "",
        div: lastF?.div ?? null,
        price: lastC?.close ?? null,
        commonPrice: null,
        eps: null,
        dps: lastF?.dps ?? null,
        disc: null,
      });
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
      divRef.current = null;
      priceRef.current = null;
      commonPriceRef.current = null;
      epsRef.current = null;
      dpsRef.current = null;
      discRef.current = null;
      divAvgLineRef.current = null;
      discAvgLineRef.current = null;
      didRangeRef.current = false;
    };
    // 마운트당 1회. page.tsx에서 key={ticker}로 종목 변경 시 재마운트.
  }, []);

  // Effect C: 보통주 EPS 히스토그램(pane 1) 데이터 갱신.
  // 시리즈는 Effect A에서 미리 생성됨 → setData만.
  useEffect(() => {
    if (!epsRef.current) return;

    if (!commonFundamentals || commonFundamentals.points.length === 0) {
      epsRef.current.setData([]);
      return;
    }

    // 0/null은 whitespace.
    epsRef.current.setData(
      commonFundamentals.points.map((p) =>
        p.eps == null || p.eps === 0 ? { time: p.date } : { time: p.date, value: p.eps },
      ),
    );
  }, [commonFundamentals]);

  // Effect B: div·price 데이터 갱신 + 최초 1회 기본 3Y 구간 + 배당 평균선.
  // DPS 히스토그램(pane 1): EPS(Effect C)보다 나중에 선언 → DPS 시리즈가 EPS 위(앞)에 렌더.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !divRef.current || !priceRef.current) return;

    // 시가배당률: null은 whitespace로 갭 유지.
    divRef.current.setData(
      fundamentals.points.map<LineData | WhitespaceData>((p) =>
        p.div == null ? { time: p.date } : { time: p.date, value: p.div },
      ),
    );
    // 주가
    priceRef.current.setData(
      candles.points.map<LineData>((p) => ({ time: p.date, value: p.close })),
    );

    // 배당 평균선 (null·0 제외 평균) — 1회 생성 후 재생성.
    if (divAvgLineRef.current) {
      divRef.current.removePriceLine(divAvgLineRef.current);
      divAvgLineRef.current = null;
    }
    const divVals = fundamentals.points
      .map((p) => p.div)
      .filter((v): v is number => v != null && v !== 0);
    if (divVals.length > 0) {
      const avg = divVals.reduce((a, b) => a + b, 0) / divVals.length;
      divAvgLineRef.current = divRef.current.createPriceLine({
        price: avg,
        color: COLOR_DIV,
        lineStyle: LineStyle.Dashed,
        lineWidth: 1,
        axisLabelVisible: true,
        title: "평균",
      });
    }

    // 최초 1회: 기본 3Y (데이터 3년 미만이면 fitContent).
    if (!didRangeRef.current && candles.points.length > 0) {
      didRangeRef.current = true;
      const range = rangeFromYears(candles.points, DEFAULT_YEARS);
      if (!range) {
        chart.timeScale().fitContent();
      } else {
        chart.timeScale().setVisibleRange(range);
      }
    }

    // hover 전 기본 레전드 = 최신값.
    const lastF = fundamentals.points[fundamentals.points.length - 1] ?? null;
    const lastC = candles.points[candles.points.length - 1] ?? null;
    setLegend({
      date: lastC?.date ?? lastF?.date ?? "",
      div: lastF?.div ?? null,
      price: lastC?.close ?? null,
      commonPrice: null,
      eps: null,
      dps: lastF?.dps ?? null,
      disc: null,
    });

    // DPS 히스토그램: 시리즈는 Effect A에서 미리 생성됨 → setData만.
    if (dpsRef.current) {
      dpsRef.current.setData(
        fundamentals.points.map((p) =>
          p.dps == null || p.dps === 0 ? { time: p.date } : { time: p.date, value: p.dps },
        ),
      );
    }
  }, [fundamentals, candles]);

  // Effect F: pane1 stretch 일원화 — EPS·DPS 데이터 유무에 따라 한 곳에서만 결정.
  // Effect C/B의 경쟁적 stretch 호출을 제거하고 여기서만 처리.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const hasEpsData = Boolean(
      commonFundamentals && commonFundamentals.points.some((p) => p.eps != null && p.eps !== 0),
    );
    const hasDpsData = fundamentals.points.some((p) => p.dps != null && p.dps !== 0);
    const panes = chart.panes();
    panes[0]?.setStretchFactor(3);
    if (panes.length > 1) panes[1].setStretchFactor(hasEpsData || hasDpsData ? 2 : 0);
  }, [fundamentals, commonFundamentals]);

  // Effect E: 보통주 주가 라인(pane 0, 우측 축). commonCandles 도착 시 지연 생성.
  // 우선주 주가와 동일 priceScaleId("right") 사용 → 같은 원 축에서 가격 격차 시각화.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    if (!commonCandles || commonCandles.points.length === 0) {
      if (commonPriceRef.current) {
        chart.removeSeries(commonPriceRef.current);
        commonPriceRef.current = null;
      }
      return;
    }

    if (!commonPriceRef.current) {
      commonPriceRef.current = chart.addSeries(
        LineSeries,
        {
          color: COLOR_COMMON_PRICE,
          lineWidth: 2,
          priceLineVisible: false,
          title: "보통주",
        },
        0,
      );
    }
    commonPriceRef.current.setData(
      commonCandles.points.map<LineData | WhitespaceData>((p) =>
        p.close == null ? { time: p.date } : { time: p.date, value: p.close },
      ),
    );
  }, [commonCandles]);

  // Effect D: 괴리율 라인(pane 2) + 평균선. commonCandles 도착 시 지연 생성.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    // commonCandles가 없거나 조인 결과가 0건이면 stale 시리즈 정리.
    const data =
      commonCandles && commonCandles.points.length > 0
        ? calcDiscount(candles, commonCandles)
        : [];

    if (data.length === 0) {
      if (discRef.current) {
        if (discAvgLineRef.current) {
          discRef.current.removePriceLine(discAvgLineRef.current);
          discAvgLineRef.current = null;
        }
        chart.removeSeries(discRef.current);
        discRef.current = null;
      }
      // pane stretch 갱신 (괴리율 없음)
      const panes = chart.panes();
      panes[0]?.setStretchFactor(3);
      if (panes.length > 2) panes[2].setStretchFactor(0);
      return;
    }

    if (!discRef.current) {
      discRef.current = chart.addSeries(
        LineSeries,
        {
          color: COLOR_DISC,
          lineWidth: 2,
          priceLineVisible: false,
          title: "괴리율",
        },
        2,
      );
    }
    discRef.current.setData(data);

    if (discAvgLineRef.current) {
      discRef.current.removePriceLine(discAvgLineRef.current);
      discAvgLineRef.current = null;
    }
    const avg = data.reduce((s, d: LineData) => s + d.value, 0) / data.length;
    discAvgLineRef.current = discRef.current.createPriceLine({
      price: avg,
      color: COLOR_DISC,
      lineStyle: LineStyle.Dashed,
      lineWidth: 1,
      axisLabelVisible: true,
      title: "평균",
    });

    // pane stretch 갱신 (괴리율 있음)
    const panes = chart.panes();
    panes[0]?.setStretchFactor(3);
    if (panes.length > 2) panes[2].setStretchFactor(2);
  }, [candles, commonCandles]);

  if (candles.points.length === 0) {
    return <p className="text-sm text-muted-foreground">데이터 없음</p>;
  }

  return (
    <div className="space-y-2">
      {!hasDividend && <span className="text-xs text-muted-foreground">배당 이력 없음</span>}
      <div className="relative w-full">
        {legend && <LegendOverlay d={legend} hasCommonPrice={hasCommonPrice} hasEps={hasEps} hasDps={hasDps} hasDisc={hasDisc} />}
        <div ref={ref} className="w-full" style={{ height: CHART_HEIGHT }} />
      </div>
    </div>
  );
}
