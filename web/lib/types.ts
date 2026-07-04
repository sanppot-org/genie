export interface Ticker {
  id: number;
  ticker: string;
  name: string;
  asset_type: string;
  data_source: string;
  timezone: string | null;
  is_preferred?: boolean;
  common_ticker?: string | null;
}

export interface FundamentalPoint {
  date: string;
  per: number | null;
  pbr: number | null;
  bps: number | null;
  eps: number | null;
  div: number | null;
  dps: number | null;
}

export interface FundamentalSeries {
  ticker: string;
  name: string;
  points: FundamentalPoint[];
}

export interface CandlePoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  trade_value: number | null;
}

export interface CandleSeries {
  ticker: string;
  name: string;
  points: CandlePoint[];
}

export type DividendKind = "SETTLE" | "INTERIM" | "QUARTERLY";

export interface DividendPoint {
  record_date: string;
  kind: DividendKind;
  dps: number;
  fiscal_year: number;
}

export interface DividendSeries {
  ticker: string;
  name: string;
  points: DividendPoint[];
}

export type GenieResponse<T> = { data: T };

export type PeriodType = "ANNUAL" | "QUARTER";

export interface IncomeStatementPoint {
  stac_yymm: string;
  revenue: number | null;
  cost_of_sales: number | null;
  gross_profit: number | null;
  operating_profit: number | null;
  ordinary_profit: number | null;
  net_income: number | null;
  eps: number | null;
  per: number | null;
  dps: number | null;
  div: number | null;
  price: number | null;
  is_estimate: boolean;
}

export interface IncomeStatementSeries {
  ticker: string;
  name: string;
  period_type: PeriodType;
  single_quarter: boolean;
  points: IncomeStatementPoint[];
}

export interface ScreeningScoreBreakdown {
  per: number;
  pbr: number;
  dividend_yield: number;
  quarterly_dividend: number;
  consecutive_increase_years: number;
  regular_buyback: number;
  annual_cancel_ratio: number;
  treasury_holding: number;
}

export interface ScreeningRow {
  ticker: string;
  name: string;
  per: number | null;
  pbr: number | null;
  roe: number | null;
  dividend_yield: number | null;
  quarterly_dividend: boolean;
  consecutive_increase_years: number;
  regular_buyback: boolean;
  annual_cancel_ratio: number | null;
  treasury_ratio: number | null;
  scores: ScreeningScoreBreakdown;
  total_score: number;
}

export interface ScreeningResponse {
  target_date: string | null;
  total: number;
  limit: number;
  offset: number;
  max_score: number;
  rows: ScreeningRow[];
}

export type ScreeningSortBy =
  | "total_score"
  | "per"
  | "pbr"
  | "roe"
  | "dividend_yield"
  | "quarterly_dividend"
  | "consecutive_years"
  | "ticker"
  | "regular_buyback"
  | "annual_cancel_ratio"
  | "treasury_holding";

export type ScreeningSortOrder = "asc" | "desc";

export interface ScreeningFilters {
  per_min?: number;
  per_max?: number;
  pbr_min?: number;
  pbr_max?: number;
  dividend_yield_min?: number;
  quarterly_only?: boolean;
  consecutive_years_min?: number;
  q?: string;
}

export type FilterComparator = "lt" | "lte" | "gt" | "gte" | "eq";
export type FilterOp = "cmp" | "count" | "cagr" | "streak" | "avg";

export interface FilterPredicate {
  cmp: FilterComparator;
  value: number;
}

export interface FilterCondition {
  metric: string;
  op: FilterOp;
  cmp?: FilterComparator;
  value?: number;
  window?: number;
  min_count?: number;
  predicate?: FilterPredicate;
}

export interface FilterScreeningRequest {
  conditions: FilterCondition[];
  sort_by: string;
  order: ScreeningSortOrder; // "asc" | "desc" 재사용
  limit: number;
  offset: number;
}

// 응답 metrics는 참조 지표만 동적으로: cmp→number, count→{count,window}, cagr/streak/avg→{[op]:number|null}
export type FilterMetricDisplay = number | Record<string, number | null> | null;

export interface FilterScreeningRow {
  ticker: string;
  name: string;
  total_score: number | null;
  metrics: Record<string, FilterMetricDisplay>;
}

export interface FilterScreeningResponse {
  total: number;
  limit: number;
  offset: number;
  rows: FilterScreeningRow[];
}

// ── Backtest ─────────────────────────────────────────────────────────────────

export interface StrategyInfo {
  name: string;
  timeframe: string;
  description: string;
  default_params: Record<string, unknown>;
}

export interface BacktestEquityPoint {
  date: string; // YYYY-MM-DD
  return_pct: number; // 초기자본 대비 수익률 (%)
  drawdown_pct: number; // 고점 대비 낙폭 (%, ≤ 0)
}

export interface BacktestRunItem {
  strategy_name: string;
  timeframe: string;
  initial_cash: number;
  final_value: number;
  total_return_pct: number;
  cagr_pct: number | null;
  max_drawdown_pct: number | null;
  sharpe_ratio: number | null;
  total_trades: number;
  win_rate_pct: number | null;
  period_days: number | null;
  start_date: string | null; // 실제 사용된 데이터 첫 봉 날짜 (YYYY-MM-DD)
  end_date: string | null; // 실제 사용된 데이터 마지막 봉 날짜 (YYYY-MM-DD)
  bust: boolean;
  equity_curve: BacktestEquityPoint[] | null; // 일별 자산곡선, 산출 불가 시 null
}

export interface BacktestRunResult {
  results: BacktestRunItem[];
  skipped: string[];
  failed: string[];
  mixed_timeframes: boolean;
  benchmark: BacktestEquityPoint[] | null; // Buy & Hold 벤치마크 (종가 기반)
}

export interface BacktestRunRequest {
  ticker: string;
  strategies: string[];
  start?: string | null;
  end?: string | null;
  initial_cash: number;
  commission: number;
  slippage: number;
  asset: "stock" | "crypto";
  param_overrides?: Record<string, unknown> | null;
}

// ── Correlation analysis ──────────────────────────────────────────────────────

export interface CorrelationRequest {
  tickers: string[];
  start?: string | null;
  end?: string | null;
  asset: "stock";
  method: "pearson" | "spearman";
  return_type: "returns" | "price";
}

export interface CorrelationResponse {
  tickers: string[];
  matrix: (number | null)[][];
  observations: number;
  period_start: string | null;
  period_end: string | null;
  method: string;
  return_type: string;
  dropped: string[];
  warnings: string[];
}

// ── US Ticker / Candle management ────────────────────────────────────────────

export interface UsTickerInfo {
  ticker: string;
  name: string | null;
  asset_type: string;
  exchange: string | null;
  candle_count: number;
  first_date: string | null;
  last_date: string | null;
}

export interface UsRegisterResult {
  registered: number;
  updated: number;
  skipped_unknown: number;
  skipped: string[];
}

export interface UsBackfillResult {
  ticker_count: number;
  attempted: number;
  failed: number;
  tickers_upserted: number;
  rows_upserted: number;
  failed_tickers: string[];
}
