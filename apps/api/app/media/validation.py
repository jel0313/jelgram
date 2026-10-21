"""画像の検証(9-3)。4つを全部チェックする。

    ① サイズ        5MB 以下か
    ② 拡張子        ファイル名の拡張子が許可されたものか
    ③ MIME タイプ   クライアントが申告した Content-Type が許可されたものか
    ④ マジックバイト ファイルの先頭の数バイト(中身の本当の形式)が、②③と一致するか

②③はクライアントがいくらでも偽れる。④で中身を確かめ、最後に Pillow で実際に開けるかも見る。
"""

import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

from app.media.constants import ALLOWED_TYPES, MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS
from app.media.exceptions import BrokenImageError, ImageTooLargeError, UnsupportedImageError


@dataclass(frozen=True)
class ValidatedImage:
    content_type: str
    extension: str  # 保存するときの拡張子
    width: int
    height: int


def detect_content_type(head: bytes) -> str | None:
    """ファイルの先頭のバイト列から、本当の形式を判定する。"""
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def file_extension(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def validate_image(
    data: bytes, *, filename: str | None, declared_type: str | None
) -> ValidatedImage:
    """画像として使えるかを確かめる。だめなら例外。"""
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageTooLargeError
    if not data:
        raise BrokenImageError("ファイルが空です")

    actual_type = detect_content_type(data[:16])
    if actual_type is None or actual_type not in ALLOWED_TYPES:
        raise UnsupportedImageError
    extension, allowed_extensions = ALLOWED_TYPES[actual_type]

    # 申告された形式・拡張子が、中身と食い違っていたら拒否する
    if declared_type is not None and declared_type.split(";")[0].strip() != actual_type:
        raise UnsupportedImageError("ファイルの形式と中身が一致しません")
    if filename is not None and file_extension(filename) not in allowed_extensions:
        raise UnsupportedImageError("拡張子と中身が一致しません")

    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            if width * height > MAX_IMAGE_PIXELS:
                raise ImageTooLargeError("画像の縦横の大きさが大きすぎます")
            image.verify()  # 壊れたファイルを見つける(中身を最後まで読む)
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as e:
        raise BrokenImageError from e

    return ValidatedImage(content_type=actual_type, extension=extension, width=width, height=height)
