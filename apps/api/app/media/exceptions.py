"""画像のエラー。"""

from app.core.exceptions import (
    BadRequestError,
    NotFoundError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)


class MediaNotFoundError(NotFoundError):
    code = "media_not_found"
    message = "画像が見つかりません"


class ImageTooLargeError(PayloadTooLargeError):
    code = "image_too_large"
    message = "画像は 5MB までです"


class UnsupportedImageError(UnsupportedMediaTypeError):
    code = "unsupported_image"
    message = "JPEG・PNG・WebP・GIF の画像だけ使えます"


class BrokenImageError(BadRequestError):
    code = "broken_image"
    message = "画像を読み込めませんでした"


class MediaNotUsableError(BadRequestError):
    code = "media_not_usable"
    message = "使えない画像が含まれています"
