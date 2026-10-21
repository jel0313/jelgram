# 詳細設計:通知・Outbox・ワーカー(第11・20章)

対象:`app/notifications/`・`app/core/outbox.py`・`app/worker/`

## 通知を作る(11-2)

```
いいね・コメント・フォロー の service から notifications.notify()
  自分への通知 → 作らない
  ブロック関係 → 作らない
  insert notifications + Outbox(notification.created)← 呼び出し元と同じトランザクション
```

## Outbox パターン(20-4)

```
API:本体の変更 + outbox_events への insert を1回の commit で確定
ワーカー(5秒ごと):
  select … from outbox_events where processed_at is null and attempts < 10
  order by id limit 50 for update skip locked      ← 他のワーカーが処理中の行は飛ばす
  1件ずつ セーブポイントの中で:
     処理 → processed_at = now
     失敗 → セーブポイントだけ戻す → attempts + 1・last_error(次回また取る)
  最後に commit
```

| イベント | 処理(worker/handlers.py) | 冪等にする工夫 |
|---|---|---|
| media.process | EXIF 削除・サムネイル | status が pending のときだけ |
| media.delete | Storage から削除 | ないファイルの削除はエラーにならない |
| post.moderate | AI が判定 → 不適切なら非表示 + 通報 | 非表示済み・削除済みなら何もしない |
| notification.created | Web Push を送る。404・410 の宛先は削除 | 二重に届いても害が小さい |
| user.purge | Supabase Auth の管理 API でユーザー削除 | 404 も成功扱い |

💡 なぜ各処理で commit しない?:処理済みの印(processed_at)と処理の結果を、同じ commit で確定させるため。各処理が勝手に commit すると、「処理は終わったのに印が付かない(また実行される)」が起きる。

## 定期ジョブ(Celery beat)

| ジョブ | 間隔 | 内容 |
|---|---|---|
| relay_outbox | 5 秒 | 上の Outbox の中継 |
| expire_stories | 毎時 5 分 | 期限切れのストーリーと画像を削除(11-5) |
| cleanup | 毎日 | 冪等性キー(1日)・処理済み Outbox(7日)・Webhook の記録(30日) |

## 既読・未読数・プッシュの登録

```sql
-- 既読:自分宛てだけ(他人の通知 id を送られても変わらない)
update notifications set read_at = :now
where recipient_id = :user_id and read_at is null
  and (cast(:ids as bigint[]) is null or id = any(cast(:ids as bigint[])))

-- プッシュの宛先:同じ端末を別の人が登録したら付け替える
insert … on conflict (endpoint) do update set user_id = excluded.user_id …
```

## 非同期の使い分け(11-1)

| | 使う場面 | この アプリ |
|---|---|---|
| def | DB・ファイル・同期のライブラリを使う(FastAPI がスレッドで動かす) | ほぼ全部のエンドポイント |
| async def | await できる部品だけで書ける | raw_body(Webhook の本文を読む) |

async def の中で同期の DB を呼ぶと、その間ほかの全リクエストが止まる。

📚 公式:[Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)・[Concurrency and async](https://fastapi.tiangolo.com/async/)・[Celery Periodic Tasks](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html)
