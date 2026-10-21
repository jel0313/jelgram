# API 一覧(基本設計)

ベース URL:`/api/v1`(16-2)。`/health`・`/metrics` だけは直下。
認証:Supabase Auth の JWT を `Authorization: Bearer <トークン>` で送る(Webhook・ヘルスチェックを除く)。
画面から試す:開発中は `http://localhost:8000/docs`(本番では非公開)。

💡 なぜ `/api/v1`?:互換性のない変更をするとき、`/api/v2` を並べて出し、古い画面を壊さずに移行できる。

---

## 一覧

| 機能 | メソッド | パス | 成功 | 主なエラー | 詳細設計 |
|---|---|---|---|---|---|
| 認証 | POST | /auth/logout | 204 | 401 | [認証](../詳細設計/認証.md) |
| 自分 | GET | /me | 200 | 401・403 | [ユーザー](../詳細設計/ユーザー.md) |
| 自分 | PATCH | /me/profile | 200 | 409・422 | [ユーザー](../詳細設計/ユーザー.md) |
| 自分 | PUT | /me/avatar | 200 | 413・415 | [画像](../詳細設計/画像.md) |
| 自分 | DELETE | /me | 204 | 401 | [ユーザー](../詳細設計/ユーザー.md) |
| 自分 | GET | /me/export | 200 | 401 | [ユーザー](../詳細設計/ユーザー.md) |
| 自分 | GET | /me/follow-requests | 200 | 401 | [ユーザー](../詳細設計/ユーザー.md) |
| 自分 | POST | /me/follow-requests/{follower_id}/approve | 204 | 404 | [ユーザー](../詳細設計/ユーザー.md) |
| 自分 | DELETE | /me/follow-requests/{follower_id} | 204 | 404 | [ユーザー](../詳細設計/ユーザー.md) |
| 自分 | GET | /me/blocks | 200 | 401 | [ユーザー](../詳細設計/ユーザー.md) |
| 自分 | POST・DELETE | /me/push-subscriptions | 204 | 422 | [通知](../詳細設計/通知とOutbox.md) |
| ユーザー | GET | /users/search?q= | 200 | 422 | [ユーザー](../詳細設計/ユーザー.md) |
| ユーザー | GET | /users/{username} | 200 | 404 | [ユーザー](../詳細設計/ユーザー.md) |
| ユーザー | GET | /users/{username}/posts?sort=&limit=&offset= | 200 | 404・422 | [投稿](../詳細設計/投稿.md) |
| ユーザー | GET | /users/{username}/followers ・ /following | 200 | 404 | [ユーザー](../詳細設計/ユーザー.md) |
| ユーザー | POST・DELETE | /users/{username}/follow | 200・204 | 404・429 | [ユーザー](../詳細設計/ユーザー.md) |
| ユーザー | POST・DELETE | /users/{username}/block | 204 | 404 | [ユーザー](../詳細設計/ユーザー.md) |
| 投稿 | GET | /posts?cursor=&limit= | 200 | 400 | [投稿](../詳細設計/投稿.md) |
| 投稿 | GET | /feed?cursor=&limit= | 200 | 400 | [投稿](../詳細設計/投稿.md) |
| 投稿 | GET | /posts/popular | 200 | 401 | [投稿](../詳細設計/投稿.md) |
| 投稿 | GET | /posts/search?q= | 200 | 422 | [投稿](../詳細設計/投稿.md) |
| 投稿 | GET | /hashtags/{tag}/posts | 200 | 400 | [投稿](../詳細設計/投稿.md) |
| 投稿 | GET | /posts/{post_id} | 200 | 404 | [投稿](../詳細設計/投稿.md) |
| 投稿 | POST | /posts(Idempotency-Key) | 201 | 400・422・429 | [投稿](../詳細設計/投稿.md) |
| 投稿 | PUT・PATCH | /posts/{post_id} | 200 | 403・404・409 | [投稿](../詳細設計/投稿.md) |
| 投稿 | DELETE | /posts/{post_id} | 204 | 403・404 | [投稿](../詳細設計/投稿.md) |
| いいね | POST・DELETE | /posts/{post_id}/like | 200 | 404・429 | [投稿](../詳細設計/投稿.md) |
| 通報 | POST | /posts/{post_id}/report | 204 | 404・429 | [管理者](../詳細設計/管理者.md) |
| コメント | GET・POST | /posts/{post_id}/comments | 200・201 | 403・404 | [コメント](../詳細設計/コメント.md) |
| コメント | PATCH・DELETE | /comments/{comment_id} | 200・204 | 403・404 | [コメント](../詳細設計/コメント.md) |
| 画像 | POST | /media(multipart) | 201 | 413・415 | [画像](../詳細設計/画像.md) |
| 画像 | POST | /media/upload-url | 201 | 422 | [画像](../詳細設計/画像.md) |
| 画像 | POST | /media/{media_id}/complete | 200 | 404・413・415 | [画像](../詳細設計/画像.md) |
| 画像 | GET | /media/{media_id} | 200 | 404 | [画像](../詳細設計/画像.md) |
| ストーリー | GET・POST | /stories | 200・201 | 400 | [ストーリーとWebhook](../詳細設計/ストーリーとWebhook.md) |
| ストーリー | DELETE | /stories/{story_id} | 204 | 404 | [ストーリーとWebhook](../詳細設計/ストーリーとWebhook.md) |
| 通知 | GET | /notifications | 200 | 400 | [通知](../詳細設計/通知とOutbox.md) |
| 通知 | GET | /notifications/unread-count | 200 | 401 | [通知](../詳細設計/通知とOutbox.md) |
| 通知 | POST | /notifications/read | 204 | 422 | [通知](../詳細設計/通知とOutbox.md) |
| AI | POST | /chat | 200 | 400・404・429・503 | [AIチャット](../詳細設計/AIチャット.md) |
| AI | POST | /chat/stream(SSE) | 200 | 400・404・429 | [AIチャット](../詳細設計/AIチャット.md) |
| AI | GET | /chat/history?session_id= ・ /chat/sessions ・ /chat/usage | 200 | 422 | [AIチャット](../詳細設計/AIチャット.md) |
| 管理者 | GET | /admin/reports ・ /admin/audit-logs | 200 | 403 | [管理者](../詳細設計/管理者.md) |
| 管理者 | POST | /admin/reports/{id}/resolve | 204 | 403・404・409 | [管理者](../詳細設計/管理者.md) |
| 管理者 | POST | /admin/posts/{id}/hide ・ unhide | 204 | 403・404 | [管理者](../詳細設計/管理者.md) |
| 管理者 | POST | /admin/users/{id}/suspend ・ unsuspend | 204 | 403・404 | [管理者](../詳細設計/管理者.md) |
| Webhook | POST | /webhooks/moderation(HMAC 署名) | 200 | 401・503 | [ストーリーとWebhook](../詳細設計/ストーリーとWebhook.md) |
| 運用 | GET | /health ・ /health/live ・ /metrics | 200 | 503 | [基盤](../詳細設計/基盤.md) |

全エンドポイント共通:401(未認証)・422(入力エラー)・413(本文が大きすぎる)・500(想定外。中身は出さない)

---

## 共通の形

```yaml
# エラー(エラー方針.md)
ErrorResponse:
  code: post_not_found          # 機械が判定する用(英語の固定値)
  message: 投稿が見つかりません   # 画面にそのまま出せる日本語
  details: null                  # 補足(422 は項目ごとのエラー)

# カーソル方式のページ(タイムライン・フィード・通知・コメント)
CursorPage:
  items: [...]
  next_cursor: "eyJ0Ijoi..."     # null なら最後。次は ?cursor= に入れる

# limit / offset 方式のページ(ユーザーの投稿一覧・フォロワー)
OffsetPage:
  items: [...]
  total: 120
  limit: 20
  offset: 40
```

💡 なぜページングが2種類?:タイムラインは新しい投稿が次々に増えるので、offset だと「ずれて重複・抜け」が出る。カーソル(最後に見た日時と id)ならずれない。プロフィールの投稿一覧は「全部で何件・何ページ目」を出したいので offset。

📚 公式:[FastAPI Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)・[Server-Sent Events](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
