// API(FastAPI)を呼ぶ共通の関数(WBS 5.2)。
// ログイン中のトークンを Authorization ヘッダーに付け、エラーは ApiError にして投げる。

import { getAccessToken } from "@/lib/auth";

import { ApiError, RateLimitError } from "./errors";

type Options = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  /** JSON にして送る本文 */
  body?: unknown;
};

/** API の URL(例:http://localhost:8000) */
function apiBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!url) throw new Error("NEXT_PUBLIC_API_BASE_URL を .env.local に設定してください");
  return url.replace(/\/$/, "");
}

/** API を呼んで、応答の JSON を返す */
export async function apiFetch<T>(path: string, { method = "GET", body }: Options = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = await getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    // サーバーが起動していない・ネットワークが切れているなど
    throw new ApiError(0, "サーバーに接続できませんでした。時間をおいてもう一度お試しください");
  }

  if (!response.ok) {
    const detail = await readDetail(response);
    if (response.status === 429) throw new RateLimitError(detail);
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** エラーの応答から、FastAPI の {"detail": "..."} を取り出す */
async function readDetail(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") return data.detail;
  } catch {
    // JSON でない応答
  }
  return `エラーが発生しました(${response.status})`;
}
