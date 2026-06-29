"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import type {
  BacktestRunItem,
  BacktestRunRequest,
  BacktestRunResult,
  CorrelationRequest,
  CorrelationResponse,
  GenieResponse,
  StrategyInfo,
  UsBackfillResult,
  UsRegisterResult,
  UsTickerInfo,
} from "@/lib/types";

// ── helpers ──────────────────────────────────────────────────────────────────

function parseSymbols(raw: string): string[] {
  return raw
    .split(",")
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean);
}

/** Convert a date-input value ("YYYY-MM-DD") to backend format ("YYYYMMDD"). */
function toBackendDate(v: string): string | null {
  if (!v) return null;
  return v.replace(/-/g, "");
}

function fmtPct(v: number | null, digits = 2): string {
  if (v === null) return "N/A";
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

function fmtNum(v: number | null, digits = 2): string {
  if (v === null) return "N/A";
  return v.toFixed(digits);
}

function fmtDays(v: number | null): string {
  if (v === null) return "N/A";
  return `${v.toLocaleString("ko-KR")}일`;
}

/** Sort results: non-bust by CAGR desc, bust rows at the bottom. */
function sortResults(rows: BacktestRunItem[]): BacktestRunItem[] {
  const live = rows
    .filter((r) => !r.bust)
    .sort((a, b) => (b.cagr_pct ?? -Infinity) - (a.cagr_pct ?? -Infinity));
  const bust = rows.filter((r) => r.bust);
  return [...live, ...bust];
}

function extractErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    // Try to parse JSON detail from FastAPI
    try {
      const parsed = JSON.parse(err.message) as { detail?: unknown };
      if (typeof parsed.detail === "string" && parsed.detail) return parsed.detail;
      if (Array.isArray(parsed.detail)) {
        // FastAPI 422: detail is [{loc, msg, type}, ...]
        return parsed.detail
          .map((item: unknown) => {
            if (item && typeof item === "object" && "msg" in item) {
              return String((item as { msg: unknown }).msg);
            }
            return JSON.stringify(item);
          })
          .join("; ");
      }
    } catch {
      // not JSON — use raw
    }
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return "알 수 없는 오류";
}

// ── sub-components ────────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-block text-[10px] font-mono tracking-widest uppercase text-green-600">
      {children}
    </span>
  );
}

function Spinner() {
  return (
    <span
      className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
      aria-hidden="true"
    />
  );
}

// ── A. Data Management ───────────────────────────────────────────────────────

function DataSection({ onTickerClick }: { onTickerClick: (ticker: string) => void }) {
  const queryClient = useQueryClient();
  const [symbolsRaw, setSymbolsRaw] = useState("");

  const tickersQuery = useQuery({
    queryKey: ["us-tickers"],
    queryFn: () =>
      apiGet<GenieResponse<UsTickerInfo[]>>("/api/us-tickers").then((r) => r.data),
  });

  const registerMutation = useMutation({
    mutationFn: (symbols: string[]) =>
      apiPost<GenieResponse<UsRegisterResult>>("/api/us-tickers/register", { symbols }).then(
        (r) => r.data,
      ),
    onSuccess: () => {
      setSymbolsRaw("");
      void queryClient.invalidateQueries({ queryKey: ["us-tickers"] });
    },
  });

  const backfillMutation = useMutation({
    mutationFn: (symbols: string[]) =>
      apiPost<GenieResponse<UsBackfillResult>>("/api/us-candles/backfill", { symbols }).then(
        (r) => r.data,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["us-tickers"] });
    },
  });

  const symbols = parseSymbols(symbolsRaw);
  const canSubmit = symbols.length > 0;

  function handleRegister() {
    if (!canSubmit) return;
    registerMutation.reset();
    registerMutation.mutate(symbols);
  }

  function handleBackfill() {
    if (!canSubmit) return;
    backfillMutation.reset();
    backfillMutation.mutate(symbols);
  }

  const regData = registerMutation.data;
  const bfData = backfillMutation.data;

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-3">
        <SectionLabel>데이터 관리</SectionLabel>
        <div className="h-px flex-1 bg-border" />
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-48 max-w-sm space-y-1">
          <label className="text-xs text-muted-foreground" htmlFor="symbols-input">
            심볼 (콤마 구분)
          </label>
          <Input
            id="symbols-input"
            value={symbolsRaw}
            onChange={(e) => setSymbolsRaw(e.target.value)}
            placeholder="TQQQ, SOXL, NVDA"
            className="font-mono text-sm"
          />
        </div>

        <Button
          variant="outline"
          size="sm"
          disabled={!canSubmit || registerMutation.isPending}
          onClick={handleRegister}
          className="gap-2"
        >
          {registerMutation.isPending && <Spinner />}
          등록
        </Button>

        <Button
          variant="outline"
          size="sm"
          disabled={!canSubmit || backfillMutation.isPending}
          onClick={handleBackfill}
          className="gap-2"
        >
          {backfillMutation.isPending && <Spinner />}
          데이터 백필
        </Button>

        {symbols.length > 0 && (
          <span className="text-xs text-muted-foreground">
            심볼 {symbols.length}개 × 약 0.5초 예상
          </span>
        )}
      </div>

      {/* Register result */}
      {registerMutation.isError && (
        <p className="text-sm text-destructive">
          등록 실패: {extractErrorMessage(registerMutation.error)}
        </p>
      )}
      {regData && (
        <div className="rounded-md border border-border bg-muted/20 px-4 py-3 text-sm font-mono">
          <span className="text-muted-foreground">등록 결과 — </span>
          <span>
            신규{" "}
            <strong className="text-green-600">{regData.registered}</strong>
            {" · "}업데이트 <strong>{regData.updated}</strong>
            {" · "}미확인{" "}
            <strong className={regData.skipped_unknown > 0 ? "text-red-600" : ""}>
              {regData.skipped_unknown}
            </strong>
          </span>
          {regData.skipped.length > 0 && (
            <p className="mt-1 text-xs text-muted-foreground">
              건너뜀: {regData.skipped.join(", ")}
            </p>
          )}
        </div>
      )}

      {/* Backfill result */}
      {backfillMutation.isPending && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner />
          백필 진행 중… 심볼이 많으면 1분 이상 걸릴 수 있습니다.
        </div>
      )}
      {backfillMutation.isError && (
        <p className="text-sm text-destructive">
          백필 실패: {extractErrorMessage(backfillMutation.error)}
        </p>
      )}
      {bfData && (
        <div className="rounded-md border border-border bg-muted/20 px-4 py-3 text-sm font-mono">
          <span className="text-muted-foreground">백필 결과 — </span>
          <span>
            행 삽입{" "}
            <strong className="text-green-600">{bfData.rows_upserted.toLocaleString("ko-KR")}</strong>
            {" · "}종목 {bfData.tickers_upserted}
            {" · "}실패{" "}
            <strong className={bfData.failed > 0 ? "text-red-600" : ""}>
              {bfData.failed}
            </strong>
          </span>
          {bfData.failed_tickers.length > 0 && (
            <p className="mt-1 text-xs text-destructive">
              실패 종목: {bfData.failed_tickers.join(", ")}
            </p>
          )}
        </div>
      )}

      {/* Registered US tickers list */}
      <UsTickerTable tickers={tickersQuery} onTickerClick={onTickerClick} />
    </section>
  );
}

// ── US Ticker Table ───────────────────────────────────────────────────────────

function UsTickerTable({
  tickers,
  onTickerClick,
}: {
  tickers: ReturnType<typeof useQuery<UsTickerInfo[]>>;
  onTickerClick: (ticker: string) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <p className="text-xs text-muted-foreground">등록된 US 티커</p>
        {tickers.isFetching && !tickers.isLoading && <Spinner />}
      </div>

      {tickers.isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner />
          티커 목록 불러오는 중…
        </div>
      )}

      {tickers.isError && (
        <p className="text-sm text-destructive">
          티커 조회 실패: {extractErrorMessage(tickers.error)}
        </p>
      )}

      {tickers.data && tickers.data.length === 0 && (
        <p className="text-sm text-muted-foreground">
          등록된 US 티커가 없습니다. 위에서 심볼을 등록하세요.
        </p>
      )}

      {tickers.data && tickers.data.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-border">
          <div className="max-h-[360px] overflow-y-auto">
            <table className="w-full border-collapse text-xs">
              <thead className="sticky top-0 z-10">
                <tr className="border-b border-border bg-muted/90 backdrop-blur-sm">
                  {[
                    ["티커", "text-left"],
                    ["이름", "text-left"],
                    ["유형", "text-left"],
                    ["거래소", "text-left"],
                    ["데이터 기간", "text-left"],
                    ["봉수", "text-right"],
                  ].map(([label, align]) => (
                    <th
                      key={label}
                      className={`px-3 py-2 font-medium text-muted-foreground ${align}`}
                    >
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tickers.data.map((t) => {
                  const hasData = t.candle_count > 0;
                  return (
                    <tr
                      key={t.ticker}
                      onClick={() => onTickerClick(t.ticker)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onTickerClick(t.ticker);
                        }
                      }}
                      tabIndex={0}
                      role="button"
                      aria-label={`${t.ticker} 백테스트 티커로 선택`}
                      className="cursor-pointer border-b border-border last:border-0 hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset transition-colors"
                      title={`클릭하면 백테스트 티커에 입력됩니다${!hasData ? " (데이터 없음 — 백필 필요)" : ""}`}
                    >
                      <td className="px-3 py-2 font-mono font-semibold">{t.ticker}</td>
                      <td className="px-3 py-2 text-muted-foreground max-w-48 truncate">
                        {t.name ?? "—"}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-mono font-medium ${
                            t.asset_type === "US_ETF"
                              ? "bg-blue-50 text-blue-600"
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {t.asset_type}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-mono text-muted-foreground">
                        {t.exchange ?? "—"}
                      </td>
                      <td className="px-3 py-2 font-mono text-muted-foreground">
                        {hasData && t.first_date && t.last_date
                          ? `${t.first_date} ~ ${t.last_date}`
                          : <span className="text-amber-600">데이터 없음</span>}
                      </td>
                      <td className="px-3 py-2 text-right font-mono tabular-nums">
                        {hasData ? (
                          t.candle_count.toLocaleString("ko-KR")
                        ) : (
                          <span className="text-amber-600 opacity-60">0</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── B. Backtest ───────────────────────────────────────────────────────────────

const DEFAULT_INITIAL_CASH = 10_000_000;
const DEFAULT_COMMISSION = 0.001;
const DEFAULT_SLIPPAGE = 0.001;

function BacktestSection({
  ticker,
  setTicker,
}: {
  ticker: string;
  setTicker: (v: string) => void;
}) {
  const [asset, setAsset] = useState<"stock" | "crypto">("stock");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [initialCash, setInitialCash] = useState(String(DEFAULT_INITIAL_CASH));
  const [commission, setCommission] = useState(String(DEFAULT_COMMISSION));
  const [slippage, setSlippage] = useState(String(DEFAULT_SLIPPAGE));
  const [selectedStrategies, setSelectedStrategies] = useState<Set<string>>(new Set());

  // Load available strategies
  const strategiesQuery = useQuery({
    queryKey: ["backtest-strategies"],
    queryFn: () =>
      apiGet<GenieResponse<StrategyInfo[]>>("/api/backtest/strategies").then((r) => r.data),
  });

  const backtestMutation = useMutation({
    mutationFn: (req: BacktestRunRequest) =>
      apiPost<GenieResponse<BacktestRunResult>>("/api/backtest/run", req).then((r) => r.data),
  });

  function toggleStrategy(name: string) {
    setSelectedStrategies((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  function handleRun() {
    const cash = parseFloat(initialCash);
    const comm = parseFloat(commission);
    const slip = parseFloat(slippage);
    if (!ticker.trim() || selectedStrategies.size === 0) return;
    if (!isFinite(cash) || cash <= 0 || !isFinite(comm) || !isFinite(slip)) return;

    backtestMutation.reset();
    const req: BacktestRunRequest = {
      ticker: ticker.trim().toUpperCase(),
      strategies: Array.from(selectedStrategies),
      start: toBackendDate(start),
      end: toBackendDate(end),
      initial_cash: cash,
      commission: comm,
      slippage: slip,
      asset,
    };
    backtestMutation.mutate(req);
  }

  const result = backtestMutation.isPending ? null : backtestMutation.data;
  const sortedResults = result ? sortResults(result.results) : [];

  const canRun =
    ticker.trim().length > 0 &&
    selectedStrategies.size > 0 &&
    isFinite(parseFloat(initialCash)) &&
    parseFloat(initialCash) > 0 &&
    isFinite(parseFloat(commission)) &&
    isFinite(parseFloat(slippage)) &&
    !backtestMutation.isPending;

  return (
    <section className="space-y-5">
      <div className="flex items-center gap-3">
        <SectionLabel>백테스트</SectionLabel>
        <div className="h-px flex-1 bg-border" />
      </div>

      {/* ── Form ── */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 lg:grid-cols-6">
        <div className="space-y-1 lg:col-span-1">
          <label className="text-xs text-muted-foreground" htmlFor="bt-ticker">
            티커
          </label>
          <Input
            id="bt-ticker"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="005930"
            className="font-mono text-sm"
          />
        </div>

        <div className="space-y-1">
          <span className="text-xs text-muted-foreground">자산 유형</span>
          <div
            role="group"
            aria-label="자산 유형"
            className="flex h-9 gap-1 rounded-md border border-input p-0.5"
          >
            {(["stock", "crypto"] as const).map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => setAsset(opt)}
                aria-label={opt === "stock" ? "주식" : "코인"}
                aria-pressed={asset === opt}
                className={`flex-1 rounded text-xs font-medium transition-colors ${
                  asset === opt
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {opt === "stock" ? "주식" : "코인"}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-1">
          <label className="text-xs text-muted-foreground" htmlFor="bt-start">
            시작일
          </label>
          <Input
            id="bt-start"
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className="text-sm"
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs text-muted-foreground" htmlFor="bt-end">
            종료일
          </label>
          <Input
            id="bt-end"
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            className="text-sm"
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs text-muted-foreground" htmlFor="bt-cash">
            초기자본 (원)
          </label>
          <Input
            id="bt-cash"
            type="number"
            value={initialCash}
            onChange={(e) => setInitialCash(e.target.value)}
            className="font-mono text-sm"
            min="1"
            step="1000000"
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs text-muted-foreground" htmlFor="bt-comm">
            수수료 · 슬리피지
          </label>
          <div className="flex gap-1">
            <Input
              id="bt-comm"
              type="number"
              value={commission}
              onChange={(e) => setCommission(e.target.value)}
              className="font-mono text-sm"
              step="0.0001"
              min="0"
              placeholder="수수료"
              aria-label="수수료"
            />
            <Input
              type="number"
              value={slippage}
              onChange={(e) => setSlippage(e.target.value)}
              className="font-mono text-sm"
              step="0.0001"
              min="0"
              placeholder="슬리피지"
              aria-label="슬리피지"
            />
          </div>
        </div>
      </div>

      {/* ── Strategy checkboxes ── */}
      <div className="space-y-2">
        <p className="text-xs text-muted-foreground">전략 선택</p>
        {strategiesQuery.isLoading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner />
            전략 목록 불러오는 중…
          </div>
        )}
        {strategiesQuery.isError && (
          <p className="text-sm text-destructive">
            전략 조회 실패: {extractErrorMessage(strategiesQuery.error)}
          </p>
        )}
        {strategiesQuery.data && (
          <div className="flex flex-wrap gap-2">
            {strategiesQuery.data.map((s) => {
              const checked = selectedStrategies.has(s.name);
              return (
                <label
                  key={s.name}
                  className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors ${
                    checked
                      ? "border-foreground bg-foreground text-background"
                      : "border-border bg-background hover:border-foreground/40"
                  }`}
                >
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={checked}
                    onChange={() => toggleStrategy(s.name)}
                  />
                  <span className="font-mono text-xs">{s.timeframe}</span>
                  <span>{s.name}</span>
                  {s.description && (
                    <span
                      className={`text-xs ${checked ? "text-background/70" : "text-muted-foreground"}`}
                    >
                      {s.description}
                    </span>
                  )}
                </label>
              );
            })}
          </div>
        )}
        {strategiesQuery.data && strategiesQuery.data.length === 0 && (
          <p className="text-sm text-muted-foreground">등록된 전략이 없습니다.</p>
        )}
      </div>

      {/* ── Run button ── */}
      <div className="flex items-center gap-3">
        <Button
          disabled={!canRun}
          onClick={handleRun}
          className="gap-2"
        >
          {backtestMutation.isPending && <Spinner />}
          {backtestMutation.isPending ? "실행 중…" : "백테스트 실행"}
        </Button>
        {backtestMutation.isPending && (
          <span className="text-xs text-muted-foreground">
            전략 수에 따라 수십 초 걸릴 수 있습니다
          </span>
        )}
        {backtestMutation.isError && (
          <span className="text-sm text-destructive">
            {extractErrorMessage(backtestMutation.error)}
          </span>
        )}
      </div>

      {/* ── Results ── */}
      {result && (
        <ResultsPanel
          result={result}
          rows={sortedResults}
          initialCash={parseFloat(initialCash)}
          commission={parseFloat(commission)}
          ticker={ticker.trim().toUpperCase()}
        />
      )}
    </section>
  );
}

// ── Results panel ─────────────────────────────────────────────────────────────

function ResultsPanel({
  result,
  rows,
  initialCash,
  commission,
  ticker,
}: {
  result: BacktestRunResult;
  rows: BacktestRunItem[];
  initialCash: number;
  commission: number;
  ticker: string;
}) {
  return (
    <div className="space-y-3">
      {/* Warnings */}
      {result.mixed_timeframes && (
        <div className="inline-flex items-center gap-2 rounded-md border border-amber-500 bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-600">
          <span aria-hidden="true">⚠</span>
          타임프레임 혼합 — 전략 간 직접 비교 시 주의 필요
        </div>
      )}

      {result.skipped.length > 0 && (
        <p className="text-xs text-muted-foreground">
          데이터 없어 제외:{" "}
          <span className="font-mono">{result.skipped.join(", ")}</span>
        </p>
      )}
      {result.failed.length > 0 && (
        <p className="text-xs text-destructive">
          실행 실패:{" "}
          <span className="font-mono">{result.failed.join(", ")}</span>
        </p>
      )}

      {/* Condition summary */}
      <div className="text-xs text-muted-foreground font-mono">
        {ticker} · 초기자본{" "}
        {initialCash.toLocaleString("ko-KR")}원 · 수수료 {(commission * 100).toFixed(2)}%
      </div>

      {/* Table */}
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">결과가 없습니다.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                {[
                  ["전략", "text-left"],
                  ["TF", "text-left"],
                  ["수익률", "text-right"],
                  ["CAGR", "text-right"],
                  ["MDD", "text-right"],
                  ["Sharpe", "text-right"],
                  ["승률", "text-right"],
                  ["거래수", "text-right"],
                  ["기간", "text-right"],
                ].map(([label, align]) => (
                  <th
                    key={label}
                    className={`px-3 py-2 font-medium text-muted-foreground ${align}`}
                  >
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <ResultRow key={row.strategy_name} row={row} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ResultRow({ row }: { row: BacktestRunItem }) {
  if (row.bust) {
    return (
      <tr
        className="border-b border-border last:border-0 opacity-50"
        aria-label={`${row.strategy_name} — 청산/비정상`}
      >
        <td className="px-3 py-2 font-medium text-red-600">
          <span className="line-through">{row.strategy_name}</span>
        </td>
        <td className="px-3 py-2 font-mono text-muted-foreground">{row.timeframe}</td>
        <td colSpan={7} className="px-3 py-2 text-center font-mono text-xs text-red-600">
          청산 / 비정상 종료
        </td>
      </tr>
    );
  }

  const returnCls = row.total_return_pct >= 0 ? "text-green-600" : "text-red-600";
  const cagrCls =
    row.cagr_pct === null ? "" : row.cagr_pct >= 0 ? "text-green-600" : "text-red-600";
  const mddCls =
    row.max_drawdown_pct !== null && row.max_drawdown_pct < -20 ? "text-red-600" : "";

  return (
    <tr className="border-b border-border last:border-0 hover:bg-muted/30">
      <td className="px-3 py-2 font-medium">{row.strategy_name}</td>
      <td className="px-3 py-2 font-mono text-muted-foreground">{row.timeframe}</td>
      <td className={`px-3 py-2 text-right font-mono tabular-nums font-semibold ${returnCls}`}>
        {fmtPct(row.total_return_pct)}
      </td>
      <td className={`px-3 py-2 text-right font-mono tabular-nums font-semibold ${cagrCls}`}>
        {fmtPct(row.cagr_pct)}
      </td>
      <td className={`px-3 py-2 text-right font-mono tabular-nums ${mddCls}`}>
        {fmtPct(row.max_drawdown_pct)}
      </td>
      <td className="px-3 py-2 text-right font-mono tabular-nums">
        {fmtNum(row.sharpe_ratio, 3)}
      </td>
      <td className="px-3 py-2 text-right font-mono tabular-nums">
        {fmtPct(row.win_rate_pct, 1)}
      </td>
      <td className="px-3 py-2 text-right font-mono tabular-nums">{row.total_trades}</td>
      <td className="px-3 py-2 text-right font-mono tabular-nums text-muted-foreground">
        {fmtDays(row.period_days)}
      </td>
    </tr>
  );
}

// ── C. Correlation analysis ────────────────────────────────────────────────────

/** Diverging cell color: +상관 빨강, -상관 파랑, 강도는 |값|. null은 무색. */
function corrCellStyle(v: number | null): React.CSSProperties {
  if (v === null) return {};
  const alpha = Math.min(Math.abs(v), 1) * 0.85;
  const rgb = v >= 0 ? "220, 38, 38" : "37, 99, 235";
  return {
    backgroundColor: `rgba(${rgb}, ${alpha})`,
    color: alpha > 0.5 ? "#fff" : undefined,
  };
}

function CorrelationSection() {
  const [tickersRaw, setTickersRaw] = useState("");
  const [method, setMethod] = useState<"pearson" | "spearman">("pearson");
  const [returnType, setReturnType] = useState<"returns" | "price">("returns");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const corrMutation = useMutation({
    mutationFn: (req: CorrelationRequest) =>
      apiPost<GenieResponse<CorrelationResponse>>("/api/correlation/run", req).then((r) => r.data),
  });

  const parsedTickers = parseSymbols(tickersRaw);
  const canRun = parsedTickers.length >= 2 && !corrMutation.isPending;

  function handleRun() {
    if (!canRun) return;
    corrMutation.reset();
    corrMutation.mutate({
      tickers: parsedTickers,
      start: toBackendDate(start),
      end: toBackendDate(end),
      asset: "stock",
      method,
      return_type: returnType,
    });
  }

  const result = corrMutation.isPending ? null : corrMutation.data;

  return (
    <section className="space-y-5">
      <div className="flex items-center gap-3">
        <SectionLabel>상관관계</SectionLabel>
        <div className="h-px flex-1 bg-border" />
      </div>

      {/* ── Form ── */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 lg:grid-cols-6">
        <div className="space-y-1 sm:col-span-3 lg:col-span-2">
          <label className="text-xs text-muted-foreground" htmlFor="corr-tickers">
            티커 (쉼표 구분, 2~20개)
          </label>
          <Input
            id="corr-tickers"
            value={tickersRaw}
            onChange={(e) => setTickersRaw(e.target.value)}
            placeholder="005930, 000660, 035720"
            className="font-mono text-sm"
          />
        </div>

        <div className="space-y-1">
          <span className="text-xs text-muted-foreground">상관 기준</span>
          <div
            role="group"
            aria-label="상관 기준"
            className="flex h-9 gap-1 rounded-md border border-input p-0.5"
          >
            {(["returns", "price"] as const).map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => setReturnType(opt)}
                aria-pressed={returnType === opt}
                className={`flex-1 rounded text-xs font-medium transition-colors ${
                  returnType === opt
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {opt === "returns" ? "수익률" : "가격"}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-1">
          <span className="text-xs text-muted-foreground">방법</span>
          <div
            role="group"
            aria-label="상관 방법"
            className="flex h-9 gap-1 rounded-md border border-input p-0.5"
          >
            {(["pearson", "spearman"] as const).map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => setMethod(opt)}
                aria-pressed={method === opt}
                className={`flex-1 rounded text-xs font-medium capitalize transition-colors ${
                  method === opt
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-1">
          <label className="text-xs text-muted-foreground" htmlFor="corr-start">
            시작일
          </label>
          <Input id="corr-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} className="text-sm" />
        </div>

        <div className="space-y-1">
          <label className="text-xs text-muted-foreground" htmlFor="corr-end">
            종료일
          </label>
          <Input id="corr-end" type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="text-sm" />
        </div>
      </div>

      <Button variant="outline" size="sm" disabled={!canRun} onClick={handleRun} className="gap-2">
        {corrMutation.isPending && <Spinner />}
        상관 분석
      </Button>

      {corrMutation.isError && (
        <p className="text-sm text-destructive">에러: {extractErrorMessage(corrMutation.error)}</p>
      )}

      {result && <CorrelationResult result={result} />}
    </section>
  );
}

function CorrelationResult({ result }: { result: CorrelationResponse }) {
  if (result.tickers.length < 2) {
    return (
      <div className="space-y-2 text-sm text-muted-foreground">
        <p>상관계산에 필요한 유효 티커가 부족합니다.</p>
        {result.dropped.length > 0 && <p>제외됨: {result.dropped.join(", ")}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>관측 {result.observations.toLocaleString("ko-KR")}개</span>
        {result.period_start && result.period_end && (
          <span>
            {result.period_start} ~ {result.period_end}
          </span>
        )}
        <span>{result.return_type === "returns" ? "수익률" : "가격"} · {result.method}</span>
      </div>

      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="px-3 py-2 text-left font-medium text-muted-foreground" />
              {result.tickers.map((t) => (
                <th key={t} className="px-3 py-2 text-center font-mono font-medium text-muted-foreground">
                  {t}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.tickers.map((rowTicker, i) => (
              <tr key={rowTicker} className="border-b border-border last:border-0">
                <td className="px-3 py-2 font-mono font-medium text-muted-foreground">{rowTicker}</td>
                {result.matrix[i].map((v, j) => (
                  <td
                    key={`${rowTicker}-${result.tickers[j]}`}
                    className="px-3 py-2 text-center font-mono tabular-nums"
                    style={corrCellStyle(v)}
                  >
                    {v === null ? "—" : v.toFixed(2)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {result.dropped.length > 0 && (
        <p className="text-xs text-muted-foreground">제외된 티커: {result.dropped.join(", ")}</p>
      )}
      {result.warnings.length > 0 && (
        <ul className="space-y-0.5 text-xs text-amber-600">
          {result.warnings.map((w) => (
            <li key={w}>⚠ {w}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function LabPage() {
  const [backtestTicker, setBacktestTicker] = useState("");

  return (
    <main className="mx-auto w-full max-w-6xl space-y-10 p-6">
      <header className="space-y-1 border-b border-border pb-5">
        <h1 className="text-2xl font-semibold tracking-tight">Lab</h1>
        <p className="text-sm text-muted-foreground">
          전략 백테스트 실행 · 상관관계 분석 · 미국 주식 데이터 관리
        </p>
      </header>

      <DataSection onTickerClick={setBacktestTicker} />

      <div className="h-px bg-border" />

      <BacktestSection ticker={backtestTicker} setTicker={setBacktestTicker} />

      <div className="h-px bg-border" />

      <CorrelationSection />
    </main>
  );
}
