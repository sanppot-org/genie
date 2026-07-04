"use client";

import {
  ColorType,
  LineSeries,
  LineStyle,
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
import type { BacktestEquityPoint, BacktestRunItem } from "@/lib/types";

const CHART_HEIGHT = 480;
const DD_PANE_HEIGHT = 130;
const BENCHMARK_COLOR = "#9ca3af"; // gray-400
// 한눈에 보기용 최대 포인트 수 — 이보다 길면 버킷으로 뭉뚱그림 (30년 일봉 → 약 2달 단위).
const MAX_POINTS = 160;

const pctFmt = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

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
  ddApi: ISeriesApi<"Line">;
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
  /** Buy & Hold 벤치마크 (없으면 미표시). */
  benchmark: BacktestEquityPoint[] | null;
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
      localization: { priceFormatter: (v: number) => `${v.toFixed(1)}%` },
      timeScale: { timeVisible: false },
    });

    const drawn: DrawnMeta[] = [];
    items.forEach((item, i) => {
      const curve = downsample(item.equity_curve ?? []);
      const color = colorFor(i);
      const equityData = curve.map<LineData>((p) => ({ time: p.date as Time, value: p.return_pct }));
      const ddData = curve.map<LineData>((p) => ({ time: p.date as Time, value: p.drawdown_pct }));

      const equityApi = chart.addSeries(
        LineSeries,
        { color, lineWidth: 2, priceLineVisible: false, lastValueVisible: true },
        0,
      );
      equityApi.setData(equityData);

      const ddApi = chart.addSeries(
        LineSeries,
        { color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false },
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

    // 벤치마크 (Buy & Hold) — 상단 pane에 회색 점선
    if (benchmark && benchmark.length > 0) {
      const api = chart.addSeries(
        LineSeries,
        {
          color: BENCHMARK_COLOR,
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          priceLineVisible: false,
          lastValueVisible: true,
        },
        0,
      );
      api.setData(downsample(benchmark).map<LineData>((p) => ({ time: p.date as Time, value: p.return_pct })));
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
          if (e && "value" in e) ret = e.value as number;
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
        {benchmark && benchmark.length > 0 && (
          <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <span style={{ color: BENCHMARK_COLOR }}>╌╌</span>
            단순보유 {pctFmt(benchmark[benchmark.length - 1].return_pct)}
          </span>
        )}
      </div>
      <p className="text-xs text-muted-foreground">
        위: 초기자본 대비 수익률 · 아래: 고점 대비 낙폭 (MDD 지점 ● 표시) · 휠로 확대/축소
      </p>
      <div ref={ref} className="w-full" style={{ height: CHART_HEIGHT }} />
    </div>
  );
}
