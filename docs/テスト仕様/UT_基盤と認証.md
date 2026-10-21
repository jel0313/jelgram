# UT 仕様:基盤・認証(第0・5・6・8・15章)

テストコード:`tests/unit/test_core.py`・`tests/unit/test_auth.py`・`tests/unit/test_senders.py`
実行:`cd apps/api && uv run pytest tests/unit/test_core.py tests/unit/test_auth.py`
方針:DB・Redis・JWKS は偽物(fakeredis・FakeJWKSClient・repository の差し替え)

## 設定(0-2・0-3)

| No | 観点 | 前提条件 | 入力 | 期待結果 | 実施結果 | 判定 | 実施日 |
|---|---|---|---|---|---|---|---|
| 1 | 秘密情報が repr に出ない | なし | database_url にパスワード | repr に含まれない | 含まれない | OK | 2026-10-22 |
| 2 | CORS のカンマ区切り(同値分割) | なし | "a" / " a , b ," / "" | [a] / [a, b] / [] | 一致 | OK | 2026-10-22 |
| 3 | 本番で localhost の CORS(異常系) | app_env=production | localhost を含む | 起動時に ValidationError | エラー | OK | 2026-10-22 |
| 4 | 本番で METRICS_TOKEN なし(異常系) | app_env=production | 未設定 | ValidationError | エラー | OK | 2026-10-22 |
| 5 | 本番は /docs を出さない | app_env=production | - | docs_enabled = False | False | OK | 2026-10-22 |
| 6 | 必須項目が空(異常系) | なし | supabase_url="" | ValidationError | エラー | OK | 2026-10-22 |
| 7 | 空欄の任意の秘密 | なし | sentry_dsn="" | None 扱い | None | OK | 2026-10-22 |

## ログのマスク(15-1・15-5)

| No | 観点 | 前提条件 | 入力 | 期待結果 | 実施結果 | 判定 | 実施日 |
|---|---|---|---|---|---|---|---|
| 8 | 文中の秘密を伏せる | なし | Bearer・JWT・sb_secret・AIza・メール | どれも出力に残らない | 残らない | OK | 2026-10-22 |
| 9 | キー名で伏せる(入れ子も) | なし | {password, nested.api_key} | *** | *** | OK | 2026-10-22 |
| 10 | JSON に request_id と追加項目 | request_id をセット | extra={status, token} | request_id・status あり、token は *** | 一致 | OK | 2026-10-22 |

## ミドルウェア・例外ハンドラー(5章・8-2・8-7・15-2)

| No | 観点 | 前提条件 | 入力 | 期待結果 | 実施結果 | 判定 | 実施日 |
|---|---|---|---|---|---|---|---|
| 11 | request_id の発行 | なし | ヘッダーなし | 32 桁の ID がヘッダーとログに | 一致 | OK | 2026-10-22 |
| 12 | 正しい request_id は引き継ぐ | なし | X-Request-ID: abc-123 | そのまま返る | 一致 | OK | 2026-10-22 |
| 13 | 不正な request_id(異常系) | なし | タブを含む | 新しい ID に置き換え | 置き換え | OK | 2026-10-22 |
| 14 | セキュリティヘッダー | hsts=True | GET | nosniff・DENY・no-referrer・CSP・HSTS | すべてあり | OK | 2026-10-22 |
| 15 | 本文の上限(境界値) | 上限 100 バイト | Content-Length 101 | 413 | 413 | OK | 2026-10-22 |
| 16 | Content-Length なしでも止める | 上限 100 バイト | chunked で 200 バイト | 413 | 413 | OK | 2026-10-22 |
| 17 | パスごとの上限 | /big は 1000 | 500 バイト | 200 | 200 | OK | 2026-10-22 |
| 18 | 想定外の例外で中身を出さない | 例外を投げる URL | GET | 500・internal_error・request_id だけ | 一致 | OK | 2026-10-22 |
| 19 | AppError の形 | NotFoundError | GET | {code, message, details} | 一致 | OK | 2026-10-22 |
| 20 | 429 に Retry-After | RateLimitError(30) | GET | Retry-After: 30 | 30 | OK | 2026-10-22 |
| 21 | 422 に入力値を含めない | なし | password="hunter2", age="abc" | field=body.age・hunter2 が出ない | 一致 | OK | 2026-10-22 |
| 22 | 存在しない URL・メソッド違い | なし | GET /nothing・DELETE /ok | 404 http_404・405 | 一致 | OK | 2026-10-22 |

## レート制限・カーソル(8-3・13-3・4-2)

| No | 観点 | 前提条件 | 入力 | 期待結果 | 実施結果 | 判定 | 実施日 |
|---|---|---|---|---|---|---|---|
| 23 | 上限まで通り、超えたら拒否(境界値) | 上限 3 | 4 回 | 通・通・通・否、retry_after 1〜60 | 一致 | OK | 2026-10-22 |
| 24 | ユーザーごとに別に数える | 上限 1 | u1・u2 | 両方通る | 通る | OK | 2026-10-22 |
| 25 | Redis が落ちている(異常系) | pipeline が例外 | 1 回 | 通す(fail-open) | 通す | OK | 2026-10-22 |
| 26 | カーソルの往復 | なし | (日時, 42) | 元に戻る | 一致 | OK | 2026-10-22 |
| 27 | 壊れたカーソル(異常系) | なし | "" / "!!!" / 項目不足 | 400 | 400 | OK | 2026-10-22 |

## 認証(6-3・6-5・7-5)

| No | 観点 | 前提条件 | 入力 | 期待結果 | 実施結果 | 判定 | 実施日 |
|---|---|---|---|---|---|---|---|
| 28 | 正しいトークン | active な user | ES256 の JWT | 200・id・role | 一致 | OK | 2026-10-22 |
| 29 | トークンなし | なし | ヘッダーなし | 401・WWW-Authenticate | 一致 | OK | 2026-10-22 |
| 30 | 無効なトークン(異常系) | なし | 期限切れ・aud 違い・iss 違い・sub が UUID でない・形式違い | 401 invalid_token | 401 | OK | 2026-10-22 |
| 31 | alg のすり替え(異常系) | なし | HS256 で署名 | 401 | 401 | OK | 2026-10-22 |
| 32 | ログアウト済み | 失効リストにある | 同じ session_id | 401 | 401 | OK | 2026-10-22 |
| 33 | 凍結 | status=suspended | 正しい JWT | 403 account_suspended | 403 | OK | 2026-10-22 |
| 34 | 退会・存在しない | deleted / なし | 正しい JWT | 401 | 401 | OK | 2026-10-22 |
| 35 | 認証サーバーに接続できない | JWKS が接続エラー | 正しい JWT | 503 | 503 | OK | 2026-10-22 |
| 36 | 管理者 API(認可) | role=user / admin | GET /admin | 403 / 200 | 一致 | OK | 2026-10-22 |
| 37 | レート制限の依存関数 | 上限 N | N+1 回 | N 回目まで 200、次は 429 | 一致 | OK | 2026-10-22 |
| 38 | ログアウト:期限まで失効 | 期限 10 分後 | logout | TTL 590〜600 秒 | 一致 | OK | 2026-10-22 |
| 39 | 期限切れ・session_id なし | - | logout | 記録しない | 記録なし | OK | 2026-10-22 |
| 40 | 認証の差し替え(14-7) | dependency_overrides | GET /me | 差し替えたユーザー | 一致 | OK | 2026-10-22 |

## メール・Web Push(11-3・11-7)

| No | 観点 | 前提条件 | 入力 | 期待結果 | 実施結果 | 判定 | 実施日 |
|---|---|---|---|---|---|---|---|
| 41 | メール送信 | SMTP 設定あり | 宛先・件名 | SMTP に渡る | 一致 | OK | 2026-10-22 |
| 42 | SMTP 未設定 | smtp_host=None | - | 送らない | 送らない | OK | 2026-10-22 |
| 43 | 送信失敗(異常系) | 接続エラー | - | 例外にせずログ | ログのみ | OK | 2026-10-22 |
| 44 | Web Push の送信 | VAPID 設定 | 宛先 | webpush に endpoint・claims | 一致 | OK | 2026-10-22 |
| 45 | 解除された宛先 | 404・410 | - | False(呼び出し元が削除) | False | OK | 2026-10-22 |
| 46 | 一時的なエラー | 500 | - | 例外(Outbox が再試行) | 例外 | OK | 2026-10-22 |
