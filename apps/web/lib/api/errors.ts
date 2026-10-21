/** API がエラー(4xx・5xx)を返したときの例外。detail は API の message、code は API の code */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly code?: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

/** レート制限を超えたとき(429) */
export class RateLimitError extends ApiError {
  constructor(detail: string, code?: string) {
    super(429, detail, code);
    this.name = "RateLimitError";
  }
}

/** 画面に出すエラーメッセージを取り出す */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  return "通信に失敗しました。時間をおいてもう一度お試しください";
}
