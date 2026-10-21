// API(FastAPI)を呼ぶ共通の関数(WBS 5.2)。
// ログイン中のトークンを Authorization ヘッダーに付け、エラーは ApiError にして投げる。

import { getAccessToken } from "@/lib/auth";

import { ApiError, RateLimitError } from "./errors";

type Options = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
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
    const { message, code } = await readError(response);
    if (response.status === 429) throw new RateLimitError(message, code);
    throw new ApiError(response.status, message, code);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** エラーの応答 {"code": "...", "message": "...", "details": ...} から、表示する文と code を取り出す */
async function readError(response: Response): Promise<{ message: string; code?: string }> {
  try {
    const data = await response.json();
    if (typeof data?.message === "string") {
      return { message: data.message, code: typeof data.code === "string" ? data.code : undefined };
    }
  } catch {
    // JSON でない応答
  }
  return { message: `エラーが発生しました(${response.status})` };
}
