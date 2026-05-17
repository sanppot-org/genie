"use client";

import { useSyncExternalStore } from "react";

import type { Ticker } from "@/lib/types";

const KEY = "genie:recentTickers";
const MAX = 8;
// 서버/하이드레이션 스냅샷 (안정 참조). 프리렌더 HTML과 일치 → 미스매치 방지.
const EMPTY: Ticker[] = [];

const listeners = new Set<() => void>();

function readInitial(): Ticker[] {
  if (typeof window === "undefined") return EMPTY;
  try {
    const v = JSON.parse(window.localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(v) ? (v as Ticker[]) : EMPTY;
  } catch {
    return EMPTY;
  }
}

// 모듈 캐시: getSnapshot이 안정 참조를 반환해야 무한 렌더 방지(변경 시에만 교체).
let cache: Ticker[] = readInitial();

function persist(): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(cache));
  } catch {
    /* localStorage 비가용(시크릿 모드 등) — 무시, 메모리만 유지 */
  }
}

function emit(): void {
  for (const l of listeners) l();
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

function getSnapshot(): Ticker[] {
  return cache;
}

function getServerSnapshot(): Ticker[] {
  return EMPTY;
}

/** 최근 선택 종목을 localStorage에 최신순·dedupe·최대 8개로 보관.
 *
 * `useSyncExternalStore` + 서버 스냅샷(EMPTY)으로 하이드레이션 미스매치를
 * 방지한다(하이드레이션은 EMPTY로 일치 → 커밋 후 클라 값으로 재렌더).
 */
export function useRecentTickers() {
  const recent = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const add = (t: Ticker): void => {
    cache = [t, ...cache.filter((p) => p.ticker !== t.ticker)].slice(0, MAX);
    persist();
    emit();
  };

  const remove = (ticker: string): void => {
    cache = cache.filter((p) => p.ticker !== ticker);
    persist();
    emit();
  };

  return { recent, add, remove };
}
