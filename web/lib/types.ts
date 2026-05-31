export interface Ticker {
  id: number;
  ticker: string;
  name: string;
  asset_type: string;
  data_source: string;
  timezone: string | null;
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
