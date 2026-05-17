// 운영 빌드에서는 NEXT_PUBLIC_API_BASE_URL=""로 두고 nginx가 same-origin proxy.
// dev에서는 .env.local의 "http://localhost:8000"를 사용.
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

type QueryValue = string | number | boolean | null | undefined;

function buildUrl(path: string, params?: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null) continue;
      search.set(k, String(v));
    }
  }
  const qs = search.toString();
  const query = qs ? `?${qs}` : "";

  if (!BASE_URL) {
    // same-origin 상대 경로 — nginx가 /api/*를 백엔드로 proxy
    return `${path}${query}`;
  }
  const url = new URL(path, BASE_URL);
  if (qs) url.search = qs;
  return url.toString();
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function apiGet<T>(path: string, params?: Record<string, QueryValue>): Promise<T> {
  const res = await fetch(buildUrl(path, params), { cache: "no-store" });
  return handle<T>(res);
}

export async function apiPost<T>(path: string, body?: unknown, params?: Record<string, QueryValue>): Promise<T> {
  const res = await fetch(buildUrl(path, params), {
    method: "POST",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  return handle<T>(res);
}
