"""Prometheus のメトリクス(22-1)。`GET /metrics` で Prometheus が定期的に取りに来る。"""

from prometheus_client import Counter, Histogram

REQUESTS = Counter(
    "http_requests_total",
    "HTTP リクエスト数",
    ["method", "route", "status"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP リクエストの処理時間",
    ["method", "route"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
AI_REQUESTS = Counter("ai_requests_total", "AI API の呼び出し回数", ["outcome"])
AI_TOKENS = Counter("ai_tokens_total", "AI API のトークン使用量", ["kind"])


def observe_request(method: str, route: str, status: int, duration: float) -> None:
    """1回のリクエストを記録する。

    ラベルには実際のパス(/posts/123)ではなくテンプレート(/posts/{post_id})を使う。
    実際のパスだと種類が無限に増え、Prometheus のメモリを食いつぶすため。
    """
    REQUESTS.labels(method, route, str(status)).inc()
    REQUEST_DURATION.labels(method, route).observe(duration)
