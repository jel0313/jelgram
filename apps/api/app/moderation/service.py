"""不適切なコンテンツの判定(12-6)。2段構え。

① すぐ判定(同期):禁止語リストに当たったら、その場で 400 で断る。速い・確実・漏れも多い
② あとで判定(非同期):投稿後にワーカーが AI に判定させ、だめなら非表示 + 通報を作る
   → 文脈を読めるが遅い・コストがかかる。利用者を待たせないよう、投稿後に回す
"""

import unicodedata

# 例として最小限。実運用では DB や設定ファイルで管理し、運用担当が追加できるようにする
_BLOCKED_WORDS = ("死ね", "殺す", "kill yourself")


def normalize(text: str) -> str:
    """全角・半角、大文字・小文字の違いで禁止語をすり抜けられないようにそろえる。"""
    return unicodedata.normalize("NFKC", text).lower()


def find_blocked_words(text: str) -> list[str]:
    """禁止語が含まれていれば、その語を返す。"""
    normalized = normalize(text)
    return [word for word in _BLOCKED_WORDS if normalize(word) in normalized]
