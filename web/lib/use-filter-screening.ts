"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { apiPost } from "@/lib/api";
import type {
  FilterCondition,
  FilterScreeningResponse,
  GenieResponse,
  ScreeningSortOrder,
} from "@/lib/types";

export function useFilterScreening(
  conditions: FilterCondition[],
  sortBy: string,
  order: ScreeningSortOrder,
  limit: number,
  offset: number,
) {
  return useQuery({
    // conditions는 객체 배열 → JSON 직렬화로 안정적 키 생성.
    queryKey: ["filter-screening", JSON.stringify(conditions), sortBy, order, limit, offset],
    queryFn: () =>
      apiPost<GenieResponse<FilterScreeningResponse>>("/api/screening/filter", {
        conditions,
        sort_by: sortBy,
        order,
        limit,
        offset,
      }).then((r) => r.data),
    enabled: conditions.length > 0, // 적용된 조건이 있을 때만 조회
    placeholderData: keepPreviousData,
  });
}
