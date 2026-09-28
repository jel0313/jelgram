"""認証(JWT 検証)の定数。"""

# 許可する署名方式。トークン側の alg は信じない
JWT_ALGORITHMS = ["ES256"]
# ログイン済みユーザー向けのトークンだけを通す
JWT_AUDIENCE = "authenticated"
