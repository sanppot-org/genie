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

export type GenieResponse<T> = { data: T };
