"""画像の定数。"""

# 1枚あたりの上限(要件定義書 3.4)
MAX_IMAGE_BYTES = 5 * 1024 * 1024
# 縦×横の画素数の上限。小さいファイルで巨大な画像を作る攻撃(画像爆弾)を防ぐ
MAX_IMAGE_PIXELS = 40_000_000
# サムネイルの長辺
THUMBNAIL_SIZE = 320

# MIME タイプ → (保存する拡張子, 許可するファイル名の拡張子)
ALLOWED_TYPES: dict[str, tuple[str, frozenset[str]]] = {
    "image/jpeg": ("jpg", frozenset({"jpg", "jpeg"})),
    "image/png": ("png", frozenset({"png"})),
    "image/webp": ("webp", frozenset({"webp"})),
    "image/gif": ("gif", frozenset({"gif"})),
}
