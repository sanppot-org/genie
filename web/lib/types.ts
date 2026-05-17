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

export type GenieResponse<T> = { data: T };
