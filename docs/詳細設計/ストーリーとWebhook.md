# 詳細設計:ストーリー・Webhook(第11章)

## ストーリー(11-5)

```
投稿:自分の未使用の画像 → stories(expires_at = 作成 + 24時間)
一覧:期限内 かつ 見てよい かつ(自分 or フォロー中)
削除:自分のものだけ → 画像の行を削除 → Outbox(media.delete)
期限切れ:ワーカーの expire_stories(毎時)
  delete from media m using stories s where s.media_id = m.id and s.expires_at <= :now returning path
  → Outbox(media.delete)。stories の行は media の削除で cascade
```
一覧は `expires_at > now()` で絞るので、ジョブが遅れても期限切れは見えない。

## Webhook の受信(11-6)

外部のモデレーションサービスが「この投稿は不適切」と知らせてくる想定。

```
POST /webhooks/moderation
  X-Webhook-Timestamp: 1792605776
  X-Webhook-Signature: hex(HMAC-SHA256(共有鍵, "<タイムスタンプ>.<本文>"))

① WEBHOOK_SECRET が未設定 → 503
② タイムスタンプが ±300 秒の外 → 401(再送攻撃の対策)
③ 署名を hmac.compare_digest で比較 → 違えば 401(改ざん・なりすまし対策)
④ 本文を検証(event_id・type・post_id・reason)→ 400
⑤ insert webhook_events (provider, event_id) on conflict do nothing
     入らなかった → {"status": "duplicate"}(200 を返して、相手の再送を止める)
⑥ 投稿を非表示 + 通報 + 監査ログ → {"status": "processed"}
```

💡 なぜ生の本文で署名を確かめる?:JSON として読み直すと、空白やキーの順番が変わり、送信側と同じバイト列にならない。
💡 なぜ compare_digest?:`==` は最初に違う文字で止まるので、時間の差から署名を1文字ずつ推測される(タイミング攻撃)。

📚 公式:[hmac](https://docs.python.org/3/library/hmac.html)
