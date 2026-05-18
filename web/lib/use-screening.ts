"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api";
import type { GenieResponse, ScreeningResponse } from "@/lib/types";

export function useScreening(date: string | undefined, limit: number, offset: number) {
  return useQuery({
    queryKey: ["screening", date ?? "latest", limit, offset],
    queryFn: () =>
      apiGet<GenieResponse<ScreeningResponse>>("/api/screening/kr-stock", {
        date,
        limit,
        offset,
      }).then((r) => r.data),
    placeholderData: keepPreviousData,
  });
}
