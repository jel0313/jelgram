# ST 仕様:総合テスト(第14章 14-8・第8章 8-8・第22章)

すべてローカルの環境で行う(クラウドの無料枠を使わない)。

## 1. 負荷テスト(locust)

```
uv run python -m scripts.seed --users 50 --posts 20     # 50人・1000投稿
RATE_LIMIT_POSTS_PER_MINUTE=1000 RATE_LIMIT_LIKES_PER_MINUTE=1000 \
  uv run uvicorn app.main:app --port 8010 --workers 2
uv run locust -f tests/load/locustfile.py --host http://127.0.0.1:8010 --headless -u 30 -r 10 -t 40s
```

| No | 観点 | 前提条件 | 入力 | 期待結果 | 実施結果 | 判定 | 実施日 |
|---|---|---|---|---|---|---|---|
| 1 | 失敗しない | 上の準備 | 30 人・40 秒(タイムライン・フィード・検索・プロフィール・いいね・投稿) | 失敗率 0% | 866 件・失敗 0 | OK | 2026-10-22 |
| 2 | 応答時間(中央値) | 同上 | 同上 | 100ms 以下 | 18ms | OK | 2026-10-22 |
| 3 | 応答時間(95%) | 同上 | 同上 | 300ms 以下 | 37ms | OK | 2026-10-22 |
| 4 | 応答時間(99%) | 同上 | 同上 | 1 秒以下 | 430ms | OK | 2026-10-22 |

### 見つかったボトルネック(改善問題の候補)

| 現象 | 原因 | 改善案 |
|---|---|---|
| 起動直後だけ 400〜500ms | ワーカーごとに初回の公開鍵(JWKS)取得と DB 接続の作成 | lifespan で JWKS を先に取る・プールを温める |
| 全リクエストで DB を 1 回余分に読む | get_current_user がアカウントの状態を毎回 DB から読む | Redis に短時間(30 秒など)キャッシュ |
| フォロワー数の集計 | プロフィールのたびに count(*) | キャッシュ済み(5分)。さらに増えたらカウンタ列 |

## 2. セキュリティ診断(OWASP API Security Top 10 2023。8-8)

| No | 項目 | 対策 | 確認 | 判定 |
|---|---|---|---|---|
| 5 | API1 オブジェクト単位の認可(IDOR) | SQL に必ず閲覧者の条件・所有者チェック | IT 16〜27 | OK |
| 6 | API2 認証の不備 | ES256 だけ許可・aud/iss/exp 必須・失効リスト | UT 28〜35 | OK |
| 7 | API3 プロパティ単位の認可 | 入力は extra=forbid(user_id などを受けない)・出力は response_model(メールは本人だけ) | UT 5・IT 1 | OK |
| 8 | API4 リソースの無制限な消費 | レート制限・本文 1MB・画像 5MB・画素数・limit の上限・statement_timeout | UT 15〜17・23・IT 15 | OK |
| 9 | API5 機能単位の認可 | require_role("admin") | IT 24 | OK |
| 10 | API6 業務フローの悪用 | 冪等性キー・いいねの一意制約・通報の一意制約 | IT 3・6 | OK |
| 11 | API7 SSRF | 利用者が指定した URL にサーバーからアクセスしない(画像は Storage の自分のパスだけ) | コードレビュー | OK |
| 12 | API8 設定の不備 | セキュリティヘッダー・CORS の許可リスト・本番は /docs 非公開・500 で中身を出さない | UT 14・18・3〜5 | OK |
| 13 | API9 API の管理 | /api/v1・OpenAPI に全エンドポイント | API一覧.md | OK |
| 14 | API10 外部 API の安全でない利用 | AI の応答を検証してから保存・Webhook は署名と時刻を確認 | UT 25・42〜44 | OK |
| 15 | 依存パッケージの脆弱性(22-6) | `uvx pip-audit` | No known vulnerabilities found | OK |

## 3. 障害時の挙動

| No | 観点 | 起こし方 | 期待結果 | 実施結果 | 判定 | 実施日 |
|---|---|---|---|---|---|---|
| 16 | Redis 停止 | `docker compose stop redis` | /health は 503。投稿・閲覧は動く(キャッシュ・レート制限なし)。ログに警告 | IT 49・UT 25 | OK | 2026-10-22 |
| 17 | AI 停止・キー無効 | GEMINI_API_KEY を不正に | 503(キャラの口調)。チャット以外は影響なし | 503・ほかの API は 200 | OK | 2026-10-22 |
| 18 | Storage 停止 | FakeStorage.fail | 一覧は画像 URL が null で返る。アップロードは 503 | UT 15 | OK | 2026-10-22 |
| 19 | ワーカー停止 | ワーカーを起動しない | API は動く。Outbox にたまり、再開後に処理される | IT 42 | OK | 2026-10-22 |
| 20 | DB 停止・復旧 | `docker stop supabase_db_jelgram` → start | 停止中:/health 503・API 500(request_id だけ)/ 復旧後:自動で 200(pool_pre_ping) | 期待どおり | OK | 2026-10-22 |

障害対応訓練の手順とポストモーテムのひな形は [運用手順書](../運用手順書.md) 4 章。
