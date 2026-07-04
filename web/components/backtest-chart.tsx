"use client";

import {
  BaselineSeries,
  ColorType,
  LineSeries,
  LineStyle,
  PriceScaleMode,
  createChart,
  createSeriesMarkers,
  type ISeriesApi,
  type LineData,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import { useEffect, useRef, useState } from "react";

import { colorFor } from "@/lib/compare-colors";
import type { BacktestBenchmark, BacktestEquityPoint, BacktestRunItem } from "@/lib/types";

const CHART_HEIGHT = 480;
const DD_PANE_HEIGHT = 130;
const BENCHMARK_COLOR = "#9ca3af"; // gray-400
// 한눈에 보기용 최대 포인트 수 — 이보다 길면 버킷으로 뭉뚱그림 (30년 일봉 → 약 2달 단위).
const MAX_POINTS = 160;

const pctFmt = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

// 상단 pane은 로그 스케일 — 로그축은 양수만 허용하므로 수익률(%)을 배수(1 + r/100)로 변환해 그린다.
// 축·레전드 표시는 %로 되돌린다. 단순보유와 전략의 수익률 격차가 커도 전략 선이 눌리지 않는다.
const toMultiple = (retPct: number) => 1 + retPct / 100;
const toPct = (multiple: number) => (multiple - 1) * 100;
const equityAxisFmt = (v: number) => `${toPct(v) >= 0 ? "+" : ""}${toPct(v).toFixed(0)}%`;
const ddAxisFmt = (v: number) => `${v.toFixed(0)}%`;

/** "#rrggbb" → "rgba(r, g, b, a)" — 낙폭 영역 채우기용 반투명 색. */
function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/** 시계열을 버킷 단위로 집계해 한눈에 보이게 단순화.
 *  equity는 버킷 마지막 값, drawdown은 버킷 내 최저값 — MDD 깊이가 뭉개지지 않게 보존. */
function downsample(curve: BacktestEquityPoint[]): BacktestEquityPoint[] {
  if (curve.length <= MAX_POINTS) return curve;
  const bucket = Math.ceil(curve.length / MAX_POINTS);
  const out: BacktestEquityPoint[] = [];
  for (let i = 0; i < curve.length; i += bucket) {
    const slice = curve.slice(i, i + bucket);
    const last = slice[slice.length - 1];
    let minDd = slice[0].drawdown_pct;
    for (const p of slice) minDd = Math.min(minDd, p.drawdown_pct);
    out.push({ date: last.date, return_pct: last.return_pct, drawdown_pct: minDd });
  }
  return out;
}

interface DrawnMeta {
  name: string;
  color: string;
  equityApi: ISeriesApi<"Line">;
  ddApi: ISeriesApi<"Baseline">;
  lastReturn: number;
  lastDd: number;
}

interface LegendRow {
  name: string;
  color: string;
  ret: number;
  dd: number;
}

interface Props {
  /** 차트에 그릴 전략 결과 (bust 제외, equity_curve 보유). 색은 배열 순서 기준. */
  items: BacktestRunItem[];
  /** Buy & Hold 벤치마크 (없으면 미표시). 곡선 + 요약 지표. */
  benchmark: BacktestBenchmark | null;
}

/** 백테스트 자산곡선 2-pane 차트 — 위: 수익률(%) + 벤치마크, 아래: 낙폭(%) + MDD 마커. */
export function BacktestChart({ items, benchmark }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const drawnRef = useRef<DrawnMeta[]>([]);
  const [legend, setLegend] = useState<{ date: string | null; rows: LegendRow[] }>({
    date: null,
    rows: [],
  });

  // 결과가 바뀔 때마다 차트를 재생성 — 백테스트 실행 단위로만 변하므로 단순 재생성이 안전.
  useEffect(() => {
    const el = ref.current;
    if (!el || items.length === 0) return;

    const chart = createChart(el, {
      width: el.clientWidth,
      height: CHART_HEIGHT,
      layout: {
        background: { type: ColorType.Solid, color: "white" },
        textColor: "#333",
        panes: { separatorColor: "#e5e5e5", enableResize: false },
      },
      grid: {
        horzLines: { color: "#eee" },
        vertLines: { color: "#eee" },
      },
      rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } },
      timeScale: { timeVisible: false },
    });

    const drawn: DrawnMeta[] = [];
    items.forEach((item, i) => {
      const curve = downsample(item.equity_curve ?? []);
      const color = colorFor(i);
      const equityData = curve.map<LineData>((p) => ({ time: p.date as Time, value: toMultiple(p.return_pct) }));
      const ddData = curve.map<LineData>((p) => ({ time: p.date as Time, value: p.drawdown_pct }));

      const equityApi = chart.addSeries(
        LineSeries,
        {
          color,
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: true,
          priceFormat: { type: "custom", formatter: equityAxisFmt, minMove: 0.01 },
        },
        0,
      );
      equityApi.setData(equityData);
      equityApi.priceScale().applyOptions({ mode: PriceScaleMode.Logarithmic });

      // 낙폭은 0 기준선 아래를 채우는 underwater 영역 — 깊이·기간이 면적으로 보인다.
      const ddApi = chart.addSeries(
        BaselineSeries,
        {
          baseValue: { type: "price", price: 0 },
          // 그라데이션을 기준값(0)·실제 데이터 범위에 앵커 — false(기본)면 패널 전체 높이 기준이라
          // 0선 위 여백까지 채우기 색이 번져 보인다.
          relativeGradient: true,
          bottomLineColor: color,
          bottomFillColor1: hexToRgba(color, 0.06), // 0 부근은 옅게
          bottomFillColor2: hexToRgba(color, 0.28), // 깊은 낙폭일수록 진하게
          topLineColor: color,
          topFillColor1: "transparent",
          topFillColor2: "transparent",
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          priceFormat: { type: "custom", formatter: ddAxisFmt, minMove: 0.01 },
        },
        1,
      );
      ddApi.setData(ddData);

      // MDD 최저점 마커
      const worst = curve.reduce((a, b) => (b.drawdown_pct < a.drawdown_pct ? b : a), curve[0]);
      if (worst && worst.drawdown_pct < 0) {
        const marker: SeriesMarker<Time> = {
          time: worst.date as Time,
          position: "belowBar",
          color,
          shape: "circle",
          size: 1,
          text: `MDD ${worst.drawdown_pct.toFixed(1)}%`,
        };
        createSeriesMarkers(ddApi, [marker]);
      }

      drawn.push({
        name: item.strategy_name,
        color,
        equityApi,
        ddApi,
        lastReturn: curve.length > 0 ? curve[curve.length - 1].return_pct : 0,
        lastDd: worst ? worst.drawdown_pct : 0,
      });
    });

    // 벤치마크 (Buy & Hold) — 상단(수익률)·하단(낙폭) pane 모두 회색 점선
    if (benchmark && benchmark.curve.length > 0) {
      const bench = downsample(benchmark.curve);
      const api = chart.addSeries(
        LineSeries,
        {
          color: BENCHMARK_COLOR,
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          priceLineVisible: false,
          lastValueVisible: true,
          priceFormat: { type: "custom", formatter: equityAxisFmt, minMove: 0.01 },
        },
        0,
      );
      api.setData(bench.map<LineData>((p) => ({ time: p.date as Time, value: toMultiple(p.return_pct) })));

      const ddApi = chart.addSeries(
        LineSeries,
        {
          color: BENCHMARK_COLOR,
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          priceLineVisible: false,
          lastValueVisible: false,
          priceFormat: { type: "custom", formatter: ddAxisFmt, minMove: 0.01 },
        },
        1,
      );
      ddApi.setData(bench.map<LineData>((p) => ({ time: p.date as Time, value: p.drawdown_pct })));
    }

    chart.panes()[1]?.setHeight(DD_PANE_HEIGHT);
    chart.timeScale().fitContent();
    drawnRef.current = drawn;

    // 레전드 — hover 시 십자선 값, 아니면 마지막 값(수익률) + MDD.
    const buildLegend = (param: MouseEventParams | null) => {
      const hovering = param != null && param.time != null;
      const rows: LegendRow[] = drawnRef.current.map((m) => {
        let ret = m.lastReturn;
        let dd = m.lastDd;
        if (hovering) {
          const e = param.seriesData.get(m.equityApi);
          if (e && "value" in e) ret = toPct(e.value as number); // 시리즈 값은 배수 → %로 환산
          const d = param.seriesData.get(m.ddApi);
          if (d && "value" in d) dd = d.value as number;
        }
        return { name: m.name, color: m.color, ret, dd };
      });
      setLegend({ date: hovering ? (param.time as string) : null, rows });
    };
    buildLegend(null);

    const onCrosshair = (param: MouseEventParams) => buildLegend(param);
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
      drawnRef.current = [];
    };
  }, [items, benchmark]);

  if (items.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        {legend.date && <span className="font-medium tabular-nums">{legend.date}</span>}
        {legend.rows.map((r) => (
          <span key={r.name} className="inline-flex items-center gap-1.5 tabular-nums">
            <span style={{ color: r.color }}>●</span>
            <span>{r.name}</span>
            <span style={{ color: r.color }} className="font-medium">
              {pctFmt(r.ret)}
            </span>
            <span className="text-xs text-muted-foreground">
              ({legend.date ? "낙폭" : "MDD"} {r.dd.toFixed(1)}%)
            </span>
          </span>
        ))}
        {benchmark && benchmark.curve.length > 0 && (
          <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <span style={{ color: BENCHMARK_COLOR }}>╌╌</span>
            단순보유 {pctFmt(benchmark.total_return_pct)}
            {benchmark.max_drawdown_pct !== null && (
              <span>(MDD {benchmark.max_drawdown_pct.toFixed(1)}%)</span>
            )}
          </span>
        )}
      </div>
      <p className="text-xs text-muted-foreground">
        위: 초기자본 대비 수익률 (로그 스케일) · 아래: 고점 대비 낙폭 (MDD 지점 ● 표시) · 휠로 확대/축소
      </p>
      <div ref={ref} className="w-full" style={{ height: CHART_HEIGHT }} />
    </div>
  );
}
