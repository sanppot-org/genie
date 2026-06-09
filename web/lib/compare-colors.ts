// 종목 비교 구분색 팔레트(최대 10). 한국식 적/청 대비를 피해 상호 식별 우선.
// compare-chart(차트 선)와 compare 페이지(칩)에서 공유 — lightweight-charts 비의존.
export const PALETTE = [
  "#2563eb", // blue
  "#dc2626", // red
  "#16a34a", // green
  "#d97706", // amber
  "#7c3aed", // violet
  "#0891b2", // cyan
  "#db2777", // pink
  "#65a30d", // lime
  "#475569", // slate
  "#ea580c", // orange
] as const;

export function colorFor(idx: number): string {
  return PALETTE[idx % PALETTE.length];
}
