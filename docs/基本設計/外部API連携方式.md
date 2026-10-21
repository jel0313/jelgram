# 外部サービス連携方式(基本設計)

すべて無料の範囲で使う。テストでは外部サービスを呼ばない(偽物に差し替える)。

| サービス | 用途 | 呼び方 | 無料枠の注意 | テスト |
|---|---|---|---|---|
| Supabase PostgreSQL | DB | SQLAlchemy + psycopg(生 SQL) | DB 500MB・7日使わないと一時停止 | ローカルの Supabase |
| Supabase Storage | 画像 | httpx2(REST)・秘密鍵はサーバーだけ | 1GB | FakeStorage |
| Supabase Auth | ログイン・JWT | 公開鍵(JWKS)で検証 | MAU 5万 | テスト用の鍵で署名 |
| Gemini API | AI チャット・投稿の判定 | httpx2(REST)・キーはヘッダー | 15回/分・500回/日(4.2 の上限で守る) | FakeAI |
| Redis | キャッシュ・レート制限・ジョブ | redis-py | ローカルは Docker。本番は Render Key Value(無料 25MB)を提案 | fakeredis / 本物(IT) |
| SMTP | メール | smtplib(BackgroundTasks) | ローカルは Mailpit | 差し替え |
| Web Push | プッシュ通知 | pywebpush(VAPID) | 無料 | FakePush |
| Sentry | エラー監視 | sentry-sdk(DSN があるときだけ) | 無料プラン 5千件/月 | 無効 |

## 落ちたときの動き(12-7・22章)

```
AI(Gemini)
  接続できない・5xx・時間切れ → 0.5秒・1秒…と待ってリトライ(最大2回)→ だめなら 503
  429(無料枠の上限)        → リトライしない → 429(キャラクターの口調)
Storage
  一覧の画像 URL が作れない → URL を null にして、投稿の一覧は返す
  アップロードできない      → 503
Redis
  落ちている → キャッシュなし・レート制限なしで動く(fail-open)。ログに警告
               AI チャットの回数制限は DB で数えるので止まらない
```

💡 なぜ Redis が落ちても止めない?:キャッシュとレート制限は「あると良い」機能。そのために API 全体が止まるほうが被害が大きい。逆に、無料枠を守る AI の回数制限は止めたくないので、DB で数えている。

## 時間がかかる処理の逃がし方(11章)

| 処理 | 方法 | 理由 |
|---|---|---|
| メール送信 | BackgroundTasks(応答の後に同じプロセスで) | 軽い・失敗しても困らない |
| 画像の加工・AI 判定・プッシュ通知・Auth のユーザー削除 | Outbox → Celery ワーカー | 重い・失敗したらやり直したい・DB と確実にそろえたい |
| ストーリーの期限切れ・古いデータの掃除 | Celery beat(定期実行) | 時刻で動く |

📚 公式:[Gemini API](https://ai.google.dev/api/generate-content)・[Supabase Storage](https://supabase.com/docs/guides/storage)・[Celery](https://docs.celeryq.dev/en/stable/getting-started/introduction.html)
