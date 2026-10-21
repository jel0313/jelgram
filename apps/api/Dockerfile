# syntax=docker/dockerfile:1
# API・ワーカー共通のイメージ(17-1)。マルチステージ:ビルド用と実行用を分け、実行用を小さくする。

# ---------- ① ビルド:依存パッケージを .venv に入れる ----------
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# 依存の定義だけ先にコピーする。コードを変えても、この層はキャッシュが効く
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY app ./app

# ---------- ② 実行:uv もビルド道具も入れない ----------
FROM python:3.13-slim AS runtime
# root で動かさない(乗っ取られたときの被害を小さくする)
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 APP_ENV=production WEB_CONCURRENCY=2
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live')"
# ワーカー数は WEB_CONCURRENCY で決める(17-3)。目安は CPU コア数 × 2 + 1。Render 無料枠(512MB)なら 2
# --timeout-graceful-shutdown:終了の合図から、処理中のリクエストを最大 20 秒待つ(22-5)
# (fastapi run は中で Uvicorn を動かす道具。細かい指定が必要なので Uvicorn を直接使う)
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY} --proxy-headers --forwarded-allow-ips='*' --timeout-graceful-shutdown 20 --no-access-log"]
