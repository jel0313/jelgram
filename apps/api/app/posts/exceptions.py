"""投稿・いいねの例外。

HTTPException を継承しているので、service で raise するとそのままエラーの応答になる。
"""

from fastapi import HTTPException


class PostNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=404, detail="投稿が見つかりません")


class InvalidImageUrlError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=422, detail="画像の URL が不正です")
