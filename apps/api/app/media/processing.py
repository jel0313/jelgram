"""画像の加工(9-8)。ワーカーがバックグラウンドで実行する。

- EXIF(撮影場所の緯度経度などが入ることがある)を消す
- 向き(EXIF の Orientation)を実際の画素に反映してから消す(消すと横倒しになるのを防ぐ)
- 一覧用のサムネイル(長辺 320px・WebP)を作る
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageOps

from app.media.constants import THUMBNAIL_SIZE

_PIL_FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP", "image/gif": "GIF"}


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes  # EXIF を消した本体
    thumbnail: bytes  # WebP のサムネイル
    width: int
    height: int


def process_image(data: bytes, content_type: str) -> ProcessedImage:
    with Image.open(io.BytesIO(data)) as original:
        if content_type == "image/gif":
            # GIF には EXIF がなく、作り直すとアニメーションが崩れるので本体はそのまま
            cleaned = data
            frame = original.convert("RGBA")
        else:
            frame = ImageOps.exif_transpose(original)  # 向きを画素に反映
            cleaned = _save_without_metadata(frame, _PIL_FORMATS[content_type])
        width, height = frame.size
        thumbnail = frame.copy()
        thumbnail.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))
        buffer = io.BytesIO()
        thumbnail.save(buffer, format="WEBP", quality=80)
    return ProcessedImage(data=cleaned, thumbnail=buffer.getvalue(), width=width, height=height)


def _save_without_metadata(image: Image.Image, pil_format: str) -> bytes:
    """メタデータ(EXIF など)を付けずに保存し直す。"""
    buffer = io.BytesIO()
    if pil_format == "JPEG":
        image.convert("RGB").save(buffer, format="JPEG", quality=90, exif=b"")
    else:
        image.save(buffer, format=pil_format, exif=b"")
    return buffer.getvalue()
