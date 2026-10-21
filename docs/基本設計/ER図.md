# ER 図(基本設計)

テーブルの定義は `supabase/migrations/` の SQL だけが持つ(ORM のモデルは作らない。生 SQL 方針)。

```
auth.users(Supabase Auth)
   │ 1:1(新規登録のトリガーで自動作成)
   ▼
profiles ──────────────┬──────────────────────┬─────────────────┐
 id・username(一意)   │ 1:多                 │ 多:多(自己参照) │ 1:多
 display_name・bio      ▼                      ▼                 ▼
 is_private・role      posts                  follows           media
 status・avatar_media_id  id・content         follower_id        id・path(一意)
                          like_count            followee_id        status
                          comment_count         status             thumbnail_path
                          version               (pending/accepted)
                          deleted_at・hidden_at
                          │                      blocks
                          ├─ 1:多 → comments    blocker_id・blocked_id
                          ├─ 多:多 → likes(user_id・post_id の複合主キー)
                          ├─ 多:多 → post_hashtags ─→ hashtags(name 一意)
                          ├─ 1:多(最大10・並び順)→ post_media ─→ media
                          └─ 1:多 → reports(通報)

profiles ─ 1:多 → chat_messages(session_id ごとの会話・トークン数)
profiles ─ 1:多 → notifications(recipient_id・actor_id)
profiles ─ 1:多 → stories ─→ media(24時間で期限切れ)
profiles ─ 1:多 → push_subscriptions(Web Push の宛先)
profiles ─ 1:多 → idempotency_keys(user_id・key の複合主キー)

運用:outbox_events(ワーカーへの依頼)・audit_logs(監査ログ)・webhook_events(重複受信の防止)
```

## 制約で守っていること

| ルール | どこで守るか |
|---|---|
| いいねは1人1投稿1回 | likes の主キー (user_id, post_id) |
| ユーザー名の重複禁止 | profiles_username_key(一意インデックス) |
| ユーザー名の形式 | check `^[a-z0-9_]{3,30}$` + API の検証 |
| 自分をフォロー・ブロックしない | check (follower_id <> followee_id) |
| 同じ人が同じ投稿を2回通報しない | reports の unique (reporter_id, post_id) |
| 画像は1つの投稿にだけ使う | post_media.media_id の unique |
| カウンタが負にならない | check (like_count >= 0) |
| 本文の長さ | check(DB)+ Pydantic(API)の二重 |
| updated_at の自動更新 | トリガー set_updated_at() |

💡 なぜ API と DB の両方でチェック?:API のチェックは分かりやすいエラーを返すため。DB の制約は、バグや同時実行で API のチェックをすり抜けても、壊れたデータを入れないための最後の砦。

## 主なインデックス(4-7)

| インデックス | 使う場面 |
|---|---|
| posts (created_at desc, id desc) where 削除・非表示でない | タイムライン |
| posts (user_id, created_at desc, id desc) | ユーザーの投稿一覧 |
| follows (followee_id, status) | フォロワー一覧・フィード |
| post_hashtags (hashtag_id, post_id desc) | ハッシュタグ検索 |
| posts.content の GIN(pg_trgm) | 本文の部分一致検索(日本語) |
| notifications (recipient_id, created_at desc, id desc) | 通知一覧 |
| chat_messages (user_id, created_at) | AI のレート制限の集計 |
| outbox_events (id) where 未処理 | ワーカーの取り出し |

実行計画の確認方法(開発用 DB で):

```sql
explain analyze
select p.id from posts p
where p.deleted_at is null and p.hidden_at is null
order by p.created_at desc, p.id desc limit 21;
-- → Index Scan using posts_timeline_idx …(Seq Scan + Sort になっていなければ OK)
```

📚 公式:[pg_trgm](https://www.postgresql.org/docs/current/pgtrgm.html)・[EXPLAIN](https://www.postgresql.org/docs/current/using-explain.html)
