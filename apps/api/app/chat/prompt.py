"""AI に渡す会話の組み立てと、応答の検証(12-2・12-5)。

プロンプトインジェクション対策:
    ① システムの指示は systemInstruction、利用者の入力は contents と、欄を分ける
    ② 他人が書いた投稿は <post> タグで囲み、「データであって指示ではない」と指示で明言する
    ③ 投稿の中の <post> </post> は無害化して、タグを閉じて抜け出せないようにする
    ④ 応答に指示の内容が出ていないか・禁止語がないかを確かめてから返す
"""

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from app.chat.ai_client import AIMessage
from app.chat.constants import (
    BLOCKED_REPLY_MESSAGE,
    HISTORY_MAX_CHARS,
    HISTORY_MAX_MESSAGES,
    REPLY_MAX_LENGTH,
    SYSTEM_PROMPT_MARKERS,
)
from app.moderation.service import find_blocked_words


def escape_post(text: str) -> str:
    """投稿の中のタグを無害化する(③)。"""
    return text.replace("<", "&lt;").replace(">", "&gt;")


def build_messages(
    history: Sequence[Mapping[Any, Any]], post: Mapping[Any, Any] | None
) -> list[AIMessage]:
    """DB の会話履歴(古い順・最後が今回の質問)を、AI に渡す形にする。

    件数(最新 20 件)と文字数(合計 6000 字)の両方で切る。古いものから捨てる。
    """
    selected: list[AIMessage] = []
    total = 0
    for row in reversed(history[-HISTORY_MAX_MESSAGES:]):
        text = row["content"]
        if selected and total + len(text) > HISTORY_MAX_CHARS:
            break
        total += len(text)
        role: Literal["user", "model"] = "model" if row["role"] == "assistant" else "user"
        selected.append(AIMessage(role=role, text=text))
    selected.reverse()

    # Gemini は会話が user から始まる必要がある
    while selected and selected[0].role != "user":
        selected.pop(0)

    if post is not None and selected:
        last = selected[-1]
        selected[-1] = AIMessage(
            role="user",
            text=(
                f'<post author="{escape_post(post["author_display_name"])}">\n'
                f"{escape_post(post['content'])}\n</post>\n\n{last.text}"
            ),
        )
    return selected


def validate_reply(text: str, *, blocked: bool) -> tuple[str, bool]:
    """応答を検証する(④)。問題があれば差し替えた文と True を返す。"""
    if blocked or not text.strip():
        return BLOCKED_REPLY_MESSAGE, True
    if any(marker in text for marker in SYSTEM_PROMPT_MARKERS):
        return BLOCKED_REPLY_MESSAGE, True
    if find_blocked_words(text):
        return BLOCKED_REPLY_MESSAGE, True
    return text.strip()[:REPLY_MAX_LENGTH], False
