"""AI API(Gemini)の呼び出し(12-1)。

サービス層からは AIClient(Protocol)としてだけ使う。
本物は GeminiClient、テストでは同じメソッドを持つ偽物に差し替える(AI API は必ずモックする)。

    service ──→ AIClient.generate() / stream()
                    └ GeminiClient … タイムアウト・リトライ・エラーの変換
"""

import json
import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Annotated, Literal, Protocol

import httpx2
from fastapi import Depends, Request

from app.chat.constants import MAX_OUTPUT_TOKENS
from app.chat.exceptions import AIRateLimitedError, AIUnavailableError
from app.core import metrics

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AIMessage:
    role: Literal["user", "model"]
    text: str


@dataclass
class AIResult:
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    blocked: bool = False  # AI 側の安全フィルターで止められた


@dataclass
class AIStreamChunk:
    """ストリーミングの1かたまり。最後のかたまりだけ usage が入る。"""

    text: str = ""
    result: AIResult | None = field(default=None)


class AIClient(Protocol):
    def generate(self, system: str, messages: list[AIMessage]) -> AIResult: ...

    def stream(self, system: str, messages: list[AIMessage]) -> Iterator[AIStreamChunk]: ...


# リトライしてよいエラー(一時的なもの)。429(上限)はリトライしても無駄なのでしない
_RETRYABLE_STATUS = {500, 502, 503, 504}


class GeminiClient:
    """Gemini API の REST を呼ぶクライアント。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float,
        max_retries: int,
    ) -> None:
        self.model = model
        self.max_retries = max_retries
        self.http = httpx2.Client(
            base_url=base_url,
            # API キーは URL(?key=)ではなくヘッダーで送る。URL はログに残りやすいため(8-6)
            headers={"x-goog-api-key": api_key},
            timeout=httpx2.Timeout(timeout, connect=5),
        )

    def close(self) -> None:
        self.http.close()

    def _body(self, system: str, messages: list[AIMessage]) -> dict[str, object]:
        # システムの指示と利用者の入力は、別の欄で渡す(12-5。混ぜると利用者が指示を上書きしやすい)
        return {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": m.role, "parts": [{"text": m.text}]} for m in messages],
            "generationConfig": {"maxOutputTokens": MAX_OUTPUT_TOKENS, "temperature": 0.8},
        }

    def _send(self, path: str, body: dict[str, object], *, stream: bool) -> httpx2.Response:
        """リトライつきで送る。指数バックオフ:0.5 秒 → 1 秒 → 2 秒 …"""
        for attempt in range(self.max_retries + 1):
            try:
                request = self.http.build_request("POST", path, json=body)
                response = self.http.send(request, stream=stream)
            except httpx2.TransportError as e:  # 接続できない・時間切れ
                logger.warning("AI API に接続できません", extra={"attempt": attempt})
                if attempt == self.max_retries:
                    metrics.AI_REQUESTS.labels("unavailable").inc()
                    raise AIUnavailableError from e
            else:
                if response.status_code == 429:
                    response.close()
                    metrics.AI_REQUESTS.labels("rate_limited").inc()
                    raise AIRateLimitedError
                if response.status_code not in _RETRYABLE_STATUS:
                    if response.status_code >= 400:
                        response.read()
                        response.close()
                        logger.error(
                            "AI API がエラーを返しました",
                            extra={"status": response.status_code, "body": response.text[:500]},
                        )
                        metrics.AI_REQUESTS.labels("error").inc()
                        raise AIUnavailableError
                    return response
                response.close()
                logger.warning(
                    "AI API が一時的なエラー",
                    extra={"status": response.status_code, "attempt": attempt},
                )
                if attempt == self.max_retries:
                    metrics.AI_REQUESTS.labels("unavailable").inc()
                    raise AIUnavailableError
            time.sleep(0.5 * 2**attempt)
        raise AIUnavailableError  # ここには来ない

    def generate(self, system: str, messages: list[AIMessage]) -> AIResult:
        response = self._send(
            f"/models/{self.model}:generateContent", self._body(system, messages), stream=False
        )
        result = parse_response(response.json())
        _record_usage(result)
        return result

    def stream(self, system: str, messages: list[AIMessage]) -> Iterator[AIStreamChunk]:
        """Server-Sent Events で少しずつ受け取る(12-3)。"""
        response = self._send(
            f"/models/{self.model}:streamGenerateContent?alt=sse",
            self._body(system, messages),
            stream=True,
        )
        texts: list[str] = []
        last: dict[str, object] = {}
        try:
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = json.loads(line[5:].strip())
                chunk = parse_response(data)
                last = data
                if chunk.text:
                    texts.append(chunk.text)
                    yield AIStreamChunk(text=chunk.text)
        except httpx2.TransportError as e:
            raise AIUnavailableError from e
        finally:
            response.close()
        final = parse_response(last) if last else AIResult(text="")
        result = AIResult(
            text="".join(texts),
            prompt_tokens=final.prompt_tokens,
            completion_tokens=final.completion_tokens,
            blocked=final.blocked,
        )
        _record_usage(result)
        yield AIStreamChunk(result=result)


def parse_response(data: dict) -> AIResult:  # type: ignore[type-arg]
    """Gemini の応答から、本文・トークン数・ブロックされたかを取り出す。"""
    usage = data.get("usageMetadata") or {}
    prompt_feedback = data.get("promptFeedback") or {}
    candidates = data.get("candidates") or []
    blocked = bool(prompt_feedback.get("blockReason"))
    text = ""
    if candidates:
        candidate = candidates[0]
        if candidate.get("finishReason") in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"):
            blocked = True
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
    return AIResult(
        text=text,
        prompt_tokens=usage.get("promptTokenCount"),
        completion_tokens=usage.get("candidatesTokenCount"),
        blocked=blocked,
    )


def _record_usage(result: AIResult) -> None:
    metrics.AI_REQUESTS.labels("blocked" if result.blocked else "ok").inc()
    if result.prompt_tokens:
        metrics.AI_TOKENS.labels("prompt").inc(result.prompt_tokens)
    if result.completion_tokens:
        metrics.AI_TOKENS.labels("completion").inc(result.completion_tokens)


def get_ai_client(request: Request) -> AIClient:
    """lifespan で作った AI クライアントを返す。"""
    client: AIClient = request.app.state.ai_client
    return client


AIClientDep = Annotated[AIClient, Depends(get_ai_client)]
