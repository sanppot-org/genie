"use client";

import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  createChart,
  type HistogramData,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type LogicalRange,
  type MouseEventParams,
  type WhitespaceData,
} from "lightweight-charts";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import type { CandlePoint, FundamentalPoint } from "@/lib/types";

// 거래량 막대 색 (캔들 방향 일치, 반투명): 상승=빨강 / 하락=파랑
const VOL_UP = "rgba(210,79,69,0.55)";
const VOL_DOWN = "rgba(18,97,196,0.55)";

// 전체 차트 박스 높이. 내부 pane 분배는 lightweight-charts의 pane 경계 드래그(기본 enabled)로 사용자가 조절.
const CHART_HEIGHT = 720;

// 이동평균선 (한국 HTS 표준 기간·구분색). 종가 기반 SMA, 클라 계산.
const MA = [5, 20, 60, 120] as const;
type MaPeriod = (typeof MA)[number];
const MA_COLOR: Record<MaPeriod, string> = {
  5: "#e91e63",
  20: "#ff9800",
  60: "#4caf50",
  120: "#9c27b0",
};

// 한국식: 상승=빨강 / 하락=파랑 (등락률·종가 강조색)
const UP = "#d24f45";
const DOWN = "#1261c4";

// 상단 고정 레전드(HTS 스타일): hover한 봉(없으면 최신봉)의 OHLC·등락률·거래량 + 켜진 보조지표.
interface LegendData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  changePct: number | null; // 전봉 종가 대비
  volume: number;
  ma: Partial<Record<MaPeriod, number>>; // hover 시점 MA 값 (hover 밖이면 비움)
  per: number | null;
  pbr: number | null;
  div: number | null;
}

/** 단순이동평균 (러닝썸 O(N)). 앞 n-1봉은 생략 → 선이 그 지점부터 시작. */
function sma(points: CandlePoint[], n: number): LineData[] {
  const out: LineData[] = [];
  let sum = 0;
  for (let i = 0; i < points.length; i++) {
    sum += points[i].close;
    if (i >= n) sum -= points[i - n].close;
    if (i >= n - 1) out.push({ time: points[i].date, value: sum / n });
  }
  return out;
}

// 상단 고정 레전드 오버레이. 종가·등락률만 등락색, 켜진 보조지표만 노출.
function LegendOverlay({
  d,
  maOn,
  perOn,
  pbrOn,
  divOn,
}: {
  d: LegendData;
  maOn: Record<MaPeriod, boolean>;
  perOn: boolean;
  pbrOn: boolean;
  divOn: boolean;
}) {
  const up = d.changePct != null ? d.changePct >= 0 : d.close >= d.open;
  const color = up ? UP : DOWN;
  const won = (v: number) => Math.round(v).toLocaleString("ko-KR");
  return (
    <div className="pointer-events-none absolute left-2 top-2 z-10 flex flex-wrap items-center gap-x-3 gap-y-0.5 rounded bg-white/85 px-2 py-1 text-xs tabular-nums shadow-sm">
      <span className="font-medium">{d.date}</span>
      <span className="text-muted-foreground">시 {won(d.open)}</span>
      <span className="text-muted-foreground">고 {won(d.high)}</span>
      <span className="text-muted-foreground">저 {won(d.low)}</span>
      <span>
        종 <span style={{ color }}>{won(d.close)}</span>
      </span>
      {d.changePct != null && (
        <span style={{ color }}>
          {d.changePct >= 0 ? "+" : ""}
          {d.changePct.toFixed(2)}%
        </span>
      )}
      <span className="text-muted-foreground">거래량 {d.volume.toLocaleString("ko-KR")}</span>
      {MA.map((n) =>
        maOn[n] && d.ma[n] != null ? (
          <span key={n} style={{ color: MA_COLOR[n] }}>
            MA{n} {won(d.ma[n]!)}
          </span>
        ) : null,
      )}
      {perOn && d.per != null && <span style={{ color: "#0ea5e9" }}>PER {d.per.toFixed(2)}</span>}
      {pbrOn && d.pbr != null && <span style={{ color: "#8b5cf6" }}>PBR {d.pbr.toFixed(2)}</span>}
      {divOn && d.div != null && <span style={{ color: "#10b981" }}>DIV {d.div.toFixed(2)}%</span>}
    </div>
  );
}

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
  const pbrRef = useRef<ISeriesApi<"Line"> | null>(null);
  const divRef = useRef<ISeriesApi<"Line"> | null>(null);
  const volRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const maRefs = useRef<(ISeriesApi<"Line"> | null)[]>([]);
  const [maOn, setMaOn] = useState<Record<MaPeriod, boolean>>({
    5: true,
    20: true,
    60: true,
    120: true,
  });
  const [perOn, setPerOn] = useState(false);
  const [pbrOn, setPbrOn] = useState(false);
  const [divOn, setDivOn] = useState(false);
  const [legend, setLegend] = useState<LegendData | null>(null);
  // crosshair 핸들러는 마운트 1회 생성 → 최신 points를 ref로 읽어 인덱싱·등락률 계산.
  const pointsRef = useRef(points);
  const didFitRef = useRef(false);
  // 초기값 true: 첫 데이터+fitContent 완료(Effect B 끝에서 해제) 전까지
  // 마운트·리사이즈·fitContent 정착 중 허위 확장 트리거를 차단.
  const loadingRef = useRef(true);
  const onNeedMoreRef = useRef<(() => void) | undefined>(undefined);
  const hasMoreRef = useRef(false);

  // 구독 핸들러는 마운트 시 1회만 생성되므로 최신 prop을 ref로 읽는다.
  // 렌더 중 ref 쓰기는 금지 → 매 커밋 후 effect에서 동기화.
  useEffect(() => {
    onNeedMoreRef.current = onNeedMore;
    hasMoreRef.current = hasMore ?? false;
    pointsRef.current = points;
  });

  // Effect A: 차트·캔들 시리즈·구독을 마운트당 1회 생성.
  useEffect(() => {
    const el = ref.current;
    if (!el || points.length === 0) return;

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

    // 거래량: 캔들 패인 하단 20% 오버레이 (전용 가격축으로 캔들과 분리)
    volRef.current = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
      priceLineVisible: false,
      lastValueVisible: false,
    });
    volRef.current.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    candleRef.current.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.25 } });

    // 이동평균선: 캔들과 동일 가격축(pane 0). 데이터는 Effect B, 표시여부는 Effect D.
    maRefs.current = MA.map((n) =>
      chart.addSeries(LineSeries, {
        color: MA_COLOR[n],
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      }),
    );

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

    // crosshair 이동 → hover한 봉(차트 밖이면 최신봉)으로 상단 레전드 갱신.
    const onCrosshair = (param: MouseEventParams) => {
      const pts = pointsRef.current;
      if (pts.length === 0) return;
      // param.logical은 hover 중인 봉의 인덱스(데이터 순서 == pts 순서, whitespace 없음).
      const hovering = param.time != null && param.logical != null;
      const idx = hovering ? (param.logical as number) : pts.length - 1;
      if (idx < 0 || idx >= pts.length) return;
      const p = pts[idx];
      const prev = idx > 0 ? pts[idx - 1] : null;
      const changePct = prev && prev.close ? ((p.close - prev.close) / prev.close) * 100 : null;

      // 보조지표는 hover 봉 시점값을 crosshair seriesData에서 읽음(차트 밖이면 비움).
      const sd = param.seriesData;
      const line = (s: ISeriesApi<"Line"> | null): number | null => {
        const d = hovering && s ? sd.get(s) : undefined;
        return d && "value" in d ? (d.value as number) : null;
      };
      const ma: Partial<Record<MaPeriod, number>> = {};
      MA.forEach((n, k) => {
        const v = line(maRefs.current[k]);
        if (v != null) ma[n] = v;
      });
      setLegend({
        date: p.date,
        open: p.open,
        high: p.high,
        low: p.low,
        close: p.close,
        changePct,
        volume: p.volume,
        ma,
        per: line(perRef.current),
        pbr: line(pbrRef.current),
        div: line(divRef.current),
      });
    };
    chart.subscribeCrosshairMove(onCrosshair);

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
      chart.unsubscribeCrosshairMove(onCrosshair);
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      perRef.current = null;
      pbrRef.current = null;
      divRef.current = null;
      volRef.current = null;
      maRefs.current = [];
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
    volRef.current?.setData(
      points.map<HistogramData>((p) => ({
        time: p.date,
        value: p.volume,
        color: p.close >= p.open ? VOL_UP : VOL_DOWN,
      })),
    );
    MA.forEach((n, k) => maRefs.current[k]?.setData(sma(points, n)));
    if (!didFitRef.current) {
      chart.timeScale().fitContent();
      didFitRef.current = true;
    } else if (prev) {
      chart.timeScale().setVisibleRange(prev);
    }
    // hover 전 기본 표시: 최신봉 OHLC·등락률·거래량 (보조지표는 hover 시점에만 채움).
    const last = points[points.length - 1];
    const prevBar = points.length > 1 ? points[points.length - 2] : null;
    setLegend({
      date: last.date,
      open: last.open,
      high: last.high,
      low: last.low,
      close: last.close,
      changePct: prevBar && prevBar.close ? ((last.close - prevBar.close) / prevBar.close) * 100 : null,
      volume: last.volume,
      ma: {},
      per: null,
      pbr: null,
      div: null,
    });
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
    }
    // null은 whitespace로 넣어 갭 유지 (connectNulls=false 동작).
    perRef.current.setData(
      perPoints.map<LineData | WhitespaceData>((p) =>
        p.per == null ? { time: p.date } : { time: p.date, value: p.per },
      ),
    );
  }, [perPoints]);

  // Effect E: PBR 라인(pane 2). perPoints의 pbr 필드 사용 (단일 fundamentals source).
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !perPoints || perPoints.length === 0) return;

    if (!pbrRef.current) {
      pbrRef.current = chart.addSeries(
        LineSeries,
        {
          color: "#8b5cf6",
          lineWidth: 2,
          priceLineVisible: false,
          title: "PBR",
        },
        2,
      );
      // pane stretch는 Effect F가 토글 상태와 함께 일괄 관리.
    }
    pbrRef.current.setData(
      perPoints.map<LineData | WhitespaceData>((p) =>
        p.pbr == null ? { time: p.date } : { time: p.date, value: p.pbr },
      ),
    );
  }, [perPoints]);

  // Effect G: 시가배당율 라인(pane 3). perPoints.div(%) 필드 사용.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !perPoints || perPoints.length === 0) return;

    if (!divRef.current) {
      divRef.current = chart.addSeries(
        LineSeries,
        {
          color: "#10b981",
          lineWidth: 2,
          priceLineVisible: false,
          title: "DIV",
        },
        3,
      );
    }
    divRef.current.setData(
      perPoints.map<LineData | WhitespaceData>((p) =>
        p.div == null ? { time: p.date } : { time: p.date, value: p.div },
      ),
    );
  }, [perPoints]);

  // Effect H: 우측 가격축 영역 휠 → 가격 범위 직접 zoom (v5 API).
  // IPriceScaleApi.setVisibleRange + setAutoScale로 진짜 가격 범위를 좁히거나 넓힌다.
  // 가격축 외 영역은 라이브러리 기본(시간축 zoom) 그대로.
  useEffect(() => {
    const chart = chartRef.current;
    const series = candleRef.current;
    if (!chart || !series) return;

    const container = chart.chartElement();
    const onWheel = (e: WheelEvent) => {
      const priceScale = series.priceScale();
      const rect = container.getBoundingClientRect();
      const axisLeft = rect.right - priceScale.width();
      if (e.clientX < axisLeft) return; // 차트 본문 → 시간축 zoom 그대로

      e.preventDefault();
      e.stopImmediatePropagation();

      const r = priceScale.getVisibleRange();
      if (!r) return;
      priceScale.setAutoScale(false);
      const px = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
      const k = Math.exp(px * 0.002); // <1: zoom in / >1: zoom out
      const mid = (r.from + r.to) / 2;
      priceScale.setVisibleRange({
        from: mid - (mid - r.from) * k,
        to: mid + (r.to - mid) * k,
      });
    };

    container.addEventListener("wheel", onWheel, { passive: false, capture: true });
    return () => container.removeEventListener("wheel", onWheel, { capture: true });
  }, []);

  // Effect D: 이평선 표시여부. 시리즈 1회 생성 후 visible만 토글.
  useEffect(() => {
    MA.forEach((n, k) => maRefs.current[k]?.applyOptions({ visible: maOn[n] }));
  }, [maOn]);

  // Effect F: PER/PBR/DIV 표시여부 + pane stretch 일괄 관리.
  // stretch=0이면 pane 자체가 접혀 빈 공간이 남지 않음.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    perRef.current?.applyOptions({ visible: perOn });
    pbrRef.current?.applyOptions({ visible: pbrOn });
    divRef.current?.applyOptions({ visible: divOn });
    const panes = chart.panes();
    panes[0]?.setStretchFactor(3);
    if (panes.length > 1) panes[1].setStretchFactor(perOn ? 1 : 0);
    if (panes.length > 2) panes[2].setStretchFactor(pbrOn ? 1 : 0);
    if (panes.length > 3) panes[3].setStretchFactor(divOn ? 1 : 0);
  }, [perOn, pbrOn, divOn, perPoints]);

  if (points.length === 0) {
    return <p className="text-sm text-muted-foreground">데이터 없음</p>;
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1">
        {MA.map((n) => (
          <Button
            key={n}
            type="button"
            size="sm"
            variant={maOn[n] ? "default" : "outline"}
            onClick={() => setMaOn((s) => ({ ...s, [n]: !s[n] }))}
          >
            <span style={{ color: MA_COLOR[n] }}>●</span> MA{n}
          </Button>
        ))}
        <Button
          type="button"
          size="sm"
          variant={perOn ? "default" : "outline"}
          onClick={() => setPerOn((v) => !v)}
        >
          <span style={{ color: "#0ea5e9" }}>●</span> PER
        </Button>
        <Button
          type="button"
          size="sm"
          variant={pbrOn ? "default" : "outline"}
          onClick={() => setPbrOn((v) => !v)}
        >
          <span style={{ color: "#8b5cf6" }}>●</span> PBR
        </Button>
        <Button
          type="button"
          size="sm"
          variant={divOn ? "default" : "outline"}
          onClick={() => setDivOn((v) => !v)}
        >
          <span style={{ color: "#10b981" }}>●</span> DIV
        </Button>
      </div>
      <div className="relative w-full">
        {legend && (
          <LegendOverlay d={legend} maOn={maOn} perOn={perOn} pbrOn={pbrOn} divOn={divOn} />
        )}
        <div ref={ref} className="w-full" style={{ height: CHART_HEIGHT }} />
      </div>
    </div>
  );
}
