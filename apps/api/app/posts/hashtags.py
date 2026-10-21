"""本文からハッシュタグを取り出す。"""

import re

from app.posts.constants import HASHTAG_MAX_LENGTH, MAX_HASHTAGS_PER_POST

# 「#」の後ろの文字・数字・_(日本語も含む)。全角の「#」も受け付ける
_HASHTAG_PATTERN = re.compile(r"[#＃]([\w]+)")


def extract_hashtags(content: str) -> list[str]:
    """本文の #タグ を、重複なし・出てきた順・小文字で返す。"""
    tags: list[str] = []
    for match in _HASHTAG_PATTERN.finditer(content):
        tag = match.group(1).lower()
        if len(tag) <= HASHTAG_MAX_LENGTH and tag not in tags:
            tags.append(tag)
        if len(tags) >= MAX_HASHTAGS_PER_POST:
            break
    return tags


def normalize_hashtag(tag: str) -> str:
    """検索で受け取ったタグを、保存時と同じ形にする(先頭の # を外して小文字)。"""
    return tag.lstrip("#＃").lower()
