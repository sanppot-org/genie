"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api";
import type {
  GenieResponse,
  ScreeningFilters,
  ScreeningResponse,
  ScreeningSortBy,
  ScreeningSortOrder,
} from "@/lib/types";

export function useScreening(
  date: string | undefined,
  limit: number,
  offset: number,
  sortBy: ScreeningSortBy,
  order: ScreeningSortOrder,
  filters: ScreeningFilters,
) {
  return useQuery({
    queryKey: ["screening", date ?? "latest", limit, offset, sortBy, order, filters],
    queryFn: () =>
      apiGet<GenieResponse<ScreeningResponse>>("/api/screening/kr-stock", {
        date,
        limit,
        offset,
        sort_by: sortBy,
        order,
        ...filters,
      }).then((r) => r.data),
    placeholderData: keepPreviousData,
  });
}
