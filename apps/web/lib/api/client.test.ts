import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getAccessToken } from "@/lib/auth";

import { apiFetch } from "./client";
import { ApiError, RateLimitError } from "./errors";

vi.mock("@/lib/auth", () => ({ getAccessToken: vi.fn() }));

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
  vi.stubGlobal("fetch", fetchMock);
  vi.mocked(getAccessToken).mockResolvedValue("token-123");
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

const jsonResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("apiFetch", () => {
  it("ログイン中ならトークンを Authorization に付けて、JSON を返す", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { id: "u1" }));

    const result = await apiFetch<{ id: string }>("/me");

    expect(result).toEqual({ id: "u1" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/me");
    expect(init.method).toBe("GET");
    expect(init.headers.Authorization).toBe("Bearer token-123");
  });

  it("未ログインなら Authorization を付けない", async () => {
    vi.mocked(getAccessToken).mockResolvedValue(null);
    fetchMock.mockResolvedValue(jsonResponse(200, {}));

    await apiFetch("/health");

    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined();
  });

  it("本文は JSON にして送る", async () => {
    fetchMock.mockResolvedValue(jsonResponse(201, { id: 1 }));

    await apiFetch("/posts", { method: "POST", body: { content: "こんにちは" } });

    const init = fetchMock.mock.calls[0][1];
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ content: "こんにちは" }));
  });

  it("エラーの応答は、detail を持つ ApiError になる", async () => {
    fetchMock.mockResolvedValue(jsonResponse(404, { detail: "投稿が見つかりません" }));

    await expect(apiFetch("/posts/1")).rejects.toEqual(new ApiError(404, "投稿が見つかりません"));
  });

  it("429 は RateLimitError になる", async () => {
    fetchMock.mockResolvedValue(jsonResponse(429, { detail: "話しすぎ" }));

    await expect(apiFetch("/chat", { method: "POST", body: {} })).rejects.toBeInstanceOf(RateLimitError);
  });

  it("detail がない・JSON でないエラーでも、ステータス付きのメッセージになる", async () => {
    fetchMock.mockResolvedValue(new Response("Internal Server Error", { status: 500 }));

    await expect(apiFetch("/posts")).rejects.toMatchObject({ status: 500, detail: "エラーが発生しました(500)" });
  });

  it("サーバーにつながらないときは status 0 の ApiError になる", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(apiFetch("/posts")).rejects.toMatchObject({ status: 0 });
  });

  it("204(本文なし)なら undefined を返す", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await expect(apiFetch("/posts/1", { method: "DELETE" })).resolves.toBeUndefined();
  });
});
