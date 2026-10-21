# APP_STATUS(現状)

- 調査日(フェーズ0):2026-10-22
- 更新日(フェーズ1 完了):2026-10-22 … バックエンドを完成。画面(Next.js)はモックのまま

---

## 1. リクエスト処理の流れ

```
受信(Uvicorn)
 ↓
app/main.py
 ├ ミドルウェア:RequestContext(request_id・ログ・500)→ SecurityHeaders → BodySizeLimit → CORS
 └ ルーター:/api/v1/<機能>
 ↓
<機能>/router.py ……………… URL・メソッド・response_model・ステータス
 ├ <機能>/schemas.py ……… 入力(Create/Update)・出力(Response)の形
 └ 依存関数
     ├ auth/dependencies.py … JWT 検証・失効・凍結 → CurrentUser / require_role / rate_limit
     ├ core/db.py ………………… DB セッション
     └ core/redis.py・media/storage.py・chat/ai_client.py … lifespan で作ったクライアント
 ↓
<機能>/service.py …………… 業務ルール・所有者チェック・commit・Outbox・監査ログ
 ↓
<機能>/repository.py ……… 生 SQL(core/visibility.py の「見てよいか」の条件)
 ↓
PostgreSQL / Redis / Storage / Gemini
 ↓
例外 → core/error_handlers.py → {"code", "message", "details"}

別プロセス:worker/(Celery)… Outbox の中継・画像の加工・AI 判定・プッシュ通知・定期ジョブ
```

---

## 2. 機能一覧

| 機能 | 状態 | 主なファイル | 関連する問題ID |
|---|---|---|---|
| 設定・環境の切り替え | 完成 | core/config.py | 0-2・0-3 |
| ヘルスチェック(DB・Redis) | 完成 | health/router.py | 0-4 |
| 入出力の検証・ステータスコード | 完成 | */schemas.py・*/router.py | 1章 |
| DB(マイグレーション・制約・updated_at) | 完成 | supabase/migrations/ | 2章 |
| 投稿の CRUD・論理削除 | 完成 | posts/ | 3-1〜3-6 |
| いいね・フォロー | 完成 | posts/・users/ | 3-7 |
| タイムライン・フィード・検索・並び順・N+1 | 完成 | posts/repository.py | 4章 |
| 例外とエラーの形 | 完成 | core/exceptions.py・core/error_handlers.py | 5章 |
| JWT 検証・ログアウト(失効) | 完成 | auth/ | 6-3・6-5 |
| 登録・ログイン・リセット・メール確認 | Supabase Auth が担当 | - | 6-1・6-2・6-4・6-6・6-7 |
| 所有者・非公開・ブロック・管理者・IDOR | 完成 | core/visibility.py・admin/ | 7章 |
| CORS・ヘッダー・レート制限・本文の上限・秘密の管理 | 完成 | core/middleware.py・core/rate_limit.py | 8章 |
| 画像(検証・UUID 名・署名付き URL・加工・アイコン) | 完成 | media/・worker/handlers.py | 9章 |
| トランザクション・楽観/悲観ロック・冪等性 | 完成 | posts/service.py・core/idempotency.py | 10章 |
| 通知・メール・ジョブキュー・ストーリー・Webhook・プッシュ | 完成 | notifications/・worker/・stories/・webhooks/ | 11章 |
| AI(層の分離・履歴・SSE・使用量・インジェクション対策・判定・障害時) | 完成 | chat/・moderation/ | 12-1〜12-7 |
| AI:画像からキャプション提案 | 未着手(任意) | - | 12-8 |
| キャッシュ・無効化・Redis のレート制限 | 完成 | users/service.py・posts/service.py | 13章 |
| テスト(UT・IT・ST・カバレッジ・CI) | 完成 | tests/・.github/workflows/ | 14章 |
| 構造化ログ・request_id・監査ログ・マスク | 完成 | core/logging.py・core/audit.py | 15章 |
| URL 設計・/api/v1・OpenAPI | 完成 | main.py | 16章 |
| Dockerfile・compose・CI・lifespan | 完成 | apps/api/Dockerfile・docker-compose.yml | 17章 |
| 応用(WebSocket・既読・おすすめ・OAuth) | 対象外(希望時のみ) | - | 18章 |
| 設計書・不具合管理・ruff・mypy・pre-commit | 完成 | docs/・pyproject.toml | 19章 |
| レイヤー分離・差し替え・Outbox | 完成 | 全体・core/outbox.py | 20章 |
| UTC・退会・エクスポート・シード・データ移行・バックアップ・全文検索 | 完成 | users/・scripts/seed.py・運用手順書 | 21章 |
| メトリクス・Sentry・トレース・プール・シャットダウン・脆弱性・訓練 | 完成 | core/metrics.py・main.py・運用手順書 | 22章 |
| 画面と API の接続 | 未着手 | apps/web/lib/api/ | 対象外(フロント) |

---

## 3. 問題点(フェーズ0 で見つけたもの → 対応)

| # | 重要度 | 内容 | 対応 |
|---|---|---|---|
| 1 | 高 | テストがクラウドの DB に直接つながる | ローカルの Supabase で IT。UT は DB 不要 |
| 2 | 高 | 開発用 Supabase に接続できない | 一時的なものだった(2026-10-22 に接続を確認)。新しいマイグレーション5本も適用済み |
| 3 | 高 | 画像バケットが公開 | 非公開の `media` バケット + 署名付き URL + 認可 |
| 4 | 中 | セキュリティヘッダー・本文の上限・レート制限がない | ミドルウェアと依存関数で対応 |
| 5 | 中 | 秘密情報が str | SecretStr・ログのマスク |
| 6 | 中 | import 時に DB エンジンを作る・lifespan なし | get_engine(遅延作成)・lifespan で作成と片付け |
| 7 | 中 | エラーの形がばらばら | AppError + 例外ハンドラー |
| 8 | 中 | CORS が PATCH・PUT を許可していない | 許可した |
| 9 | 中 | GET /posts にページングがない | カーソル方式 |
| 10 | 低 | mypy・CI・Dockerfile・構造化ログがない | すべて追加 |
| 11 | 低 | README が古い | 更新 |

### 残っている課題(フェーズ2 の改善問題の候補)

| 内容 | 詳細 |
|---|---|
| 認証のたびに DB を読む | ST の結果。短時間のキャッシュで減らせる |
| 本番のワーカー | Render の無料枠では常時起動できない(運用手順書 1章に代案) |
| 画面がまだダミー | `apps/web/lib/api/` を `/api/v1` の API に置き換える。エラーの形が `{"code","message"}` になったので、`readDetail` も `message` を読むように変える |

---

## 4. 使用ライブラリ

| ライブラリ | バージョン | 何のために使うか |
|---|---|---|
| fastapi[standard] | 0.158.1 | Web API の本体(ルーティング・検証・/docs・SSE・OpenTelemetry) |
| pydantic / pydantic-settings | 2.14.1 / 2.16.1 | 入出力の検証・.env の読み込み |
| sqlalchemy + psycopg | 2.1.6 / 3.3.6 | DB 接続・コネクションプール・生 SQL の実行 |
| pyjwt[crypto] | 2.15.1 | Supabase の JWT(ES256)の検証 |
| httpx2 | 2.16.0 | 外部 API(Gemini・Storage)の呼び出し・TestClient |
| redis | 6.4.0 | キャッシュ・レート制限・トークンの失効リスト |
| celery[redis] | 5.6.3 | ジョブキュー・定期ジョブ |
| pillow | 13.0.0 | 画像の検証・EXIF 削除・サムネイル |
| prometheus-client | 0.26.0 | メトリクス(/metrics) |
| sentry-sdk | 2.72.0 | エラー監視(DSN があるときだけ) |
| pywebpush | 2.5.0 | Web Push |
| pytest・pytest-cov | 9.1.1 / 7.1.0 | テスト・カバレッジ(C0/C1) |
| fakeredis | 2.40.0 | UT で Redis の代わり |
| locust | 2.46.7 | 負荷テスト |
| ruff・mypy・pre-commit | 0.17.1 / 2.4.0 / 4.7.0 | 静的解析・整形・型チェック・コミット前の自動チェック |

---

## 5. 不要ファイルの削除(フェーズ0。cleanup ブランチ)

| 削除したファイル | 理由 |
|---|---|
| `docs/詳細設計_手順/4.1_APIひな形/`・`4.2_認証/`(詳細設計書・マニュアル) | 旧形式。`docs/詳細設計/`・`docs/テスト仕様/` に作り直した |
| `docs/API仕様/5.4_投稿一覧の表示.md`・シーケンス図 | 旧形式。`docs/基本設計/API一覧.md`・`docs/詳細設計/投稿.md` に統合 |
| `apps/api/tests/test_*.py`(5 ファイル) | `tests/unit/`・`tests/integration/` に作り直した |

削除しなかったもの(Git 管理外。秘密情報を含む可能性があるため):`apps/api/.env`・`apps/web/.env.local`・`docs/設定/`
