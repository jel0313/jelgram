# UT 仕様:画像・AI チャット・Webhook・ワーカー(第9・11・12章)

テストコード:`tests/unit/test_media.py`・`tests/unit/test_chat.py`・`tests/unit/test_misc.py`・`tests/unit/test_services.py`
方針:Storage・Gemini は偽物(FakeStorage・httpx2.MockTransport)。AI API は絶対に呼ばない。

## 画像(9-3〜9-8)

| No | 観点 | 前提条件 | 入力 | 期待結果 | 実施結果 | 判定 | 実施日 |
|---|---|---|---|---|---|---|---|
| 1 | マジックバイトの判定 | なし | PNG・JPEG・GIF・WebP・PDF | 各形式・PDF は None | 一致 | OK | 2026-10-22 |
| 2 | 正しい画像 | なし | a.PNG(40×30) | png・40・30 | 一致 | OK | 2026-10-22 |
| 3 | サイズ(境界値) | なし | 5MB + 1 バイト | 413 | 413 | OK | 2026-10-22 |
| 4 | 空ファイル | なし | 0 バイト | 400 | 400 | OK | 2026-10-22 |
| 5 | 画像に見せかけた PDF | なし | a.png・image/png・中身 PDF | 415 | 415 | OK | 2026-10-22 |
| 6 | MIME・拡張子の不一致 | なし | PNG を image/jpeg・a.jpg | 415 | 415 | OK | 2026-10-22 |
| 7 | SVG | なし | <svg onload=…> | 415 | 415 | OK | 2026-10-22 |
| 8 | 途中で切れた画像 | なし | PNG の先頭 60 バイト | 400 | 400 | OK | 2026-10-22 |
| 9 | 画像爆弾 | なし | 8000×6000 | 413 か 400 | 拒否 | OK | 2026-10-22 |
| 10 | EXIF の削除とサムネイル | EXIF にメーカー名 | 800×600 JPEG | メーカー名なし・WebP・長辺 320 | 一致 | OK | 2026-10-22 |
| 11 | GIF は本体を変えない | なし | GIF | 同じバイト列 | 一致 | OK | 2026-10-22 |
| 12 | 保存名は UUID | なし | ../../etc/passwd.png | <owner>/<uuid>.png・.. なし | 一致 | OK | 2026-10-22 |
| 13 | DB 失敗でファイルを消す(異常系) | insert が例外 | upload | Storage が空・rollback | 一致 | OK | 2026-10-22 |
| 14 | 見えない画像 | 権限なし | GET | 404 | 404 | OK | 2026-10-22 |
| 15 | Storage 障害でも一覧は返す | Storage 停止 | sign_media | url=None | None | OK | 2026-10-22 |
| 16 | Storage クライアントの送信内容 | MockTransport | upload | URL・apikey・Content-Type | 一致 | OK | 2026-10-22 |
| 17 | 署名付き URL は1回の通信 | MockTransport | 2 パス | 1 回・失敗したパスは除く | 一致 | OK | 2026-10-22 |
| 18 | 空のパスは通信しない | なし | [] | 呼ばれない | 呼ばれない | OK | 2026-10-22 |
| 19 | Storage の 500 | MockTransport | download | StorageError(503) | 例外 | OK | 2026-10-22 |
| 20 | 直接アップロードの完了 | 正しい画像 / 偽物 / 他人 / 未アップロード | complete | 幅を記録 / 削除・failed・415 / 404 / 404 | 一致 | OK | 2026-10-22 |

## AI チャット(12章)

| No | 観点 | 前提条件 | 入力 | 期待結果 | 実施結果 | 判定 | 実施日 |
|---|---|---|---|---|---|---|---|
| 21 | ロールの変換 | なし | user・assistant | user・model | 一致 | OK | 2026-10-22 |
| 22 | 履歴の件数(境界値) | 30 件 | build | 最新 20 件 | 一致 | OK | 2026-10-22 |
| 23 | 履歴の文字数 | 5000+2000+最新 | build | 最新だけ(model から始めない) | 一致 | OK | 2026-10-22 |
| 24 | 投稿を囲む・無害化 | 投稿に </post> | build | <post author=…>・&lt;/post&gt; | 一致 | OK | 2026-10-22 |
| 25 | 応答の検証(同値分割) | なし | 空・ブロック・指示の漏えい・禁止語 | 定型文に差し替え | 一致 | OK | 2026-10-22 |
| 26 | 応答の長さ | なし | 5000 字 | 2000 字 | 2000 | OK | 2026-10-22 |
| 27 | 応答の解析 | なし | parts 2つ・usage | 連結・トークン数 | 一致 | OK | 2026-10-22 |
| 28 | 思考の部分は除く | thought=True | parse | 答えだけ | 一致 | OK | 2026-10-22 |
| 29 | ブロックの判定 | blockReason / finishReason=SAFETY | parse | blocked=True | True | OK | 2026-10-22 |
| 30 | 送信内容 | MockTransport | generate | systemInstruction と contents が別・キーはヘッダー | 一致 | OK | 2026-10-22 |
| 31 | 503 → 成功 | 1回目 503 | generate | リトライで成功 | 成功 | OK | 2026-10-22 |
| 32 | リトライの上限 | ずっと 500 | generate | 3回で AIUnavailableError | 一致 | OK | 2026-10-22 |
| 33 | 時間切れ | ReadTimeout | generate | AIUnavailableError | 例外 | OK | 2026-10-22 |
| 34 | 429・400 はリトライしない | 429 / 400 | generate | 1回で AIRateLimitedError / AIUnavailableError | 一致 | OK | 2026-10-22 |
| 35 | ストリーミングの解析 | SSE 2 件 | stream | 差分 2 つ・最後に合計とトークン数 | 一致 | OK | 2026-10-22 |
| 36 | 日の区切り(境界値) | JST 23:59・PDT 23:00 | start_of_day | 前日 15:00 UTC・前日 7:00 UTC | 一致 | OK | 2026-10-22 |
| 37 | 4 種類の上限(境界値) | 上限 - 1 / 上限 | check | 通る / 429・Retry-After > 0 | 一致 | OK | 2026-10-22 |
| 38 | SSE のイベント | FakeAI | reply_stream | delta・delta・done、トークン数を保存 | 一致 | OK | 2026-10-22 |
| 39 | SSE のエラー | AI 停止 | reply_stream | error(ai_unavailable) | 一致 | OK | 2026-10-22 |
| 40 | 準備:投稿つき | 見える投稿 | prepare | ロック・保存・commit・<post> | 一致 | OK | 2026-10-22 |
| 41 | 準備:ない投稿・禁止語 | なし | prepare | 404・400、保存しない | 一致 | OK | 2026-10-22 |

## Webhook・ワーカー(11章・12-6・20-4)

| No | 観点 | 前提条件 | 入力 | 期待結果 | 実施結果 | 判定 | 実施日 |
|---|---|---|---|---|---|---|---|
| 42 | 正しい署名 | なし | 本文・署名 | 通る | 通る | OK | 2026-10-22 |
| 43 | 改ざん | なし | 本文を変える | 401 | 401 | OK | 2026-10-22 |
| 44 | 時刻のずれ(境界値) | now=1000+ | 301秒・-301秒・300秒・数字でない | 401・401・OK・401 | 一致 | OK | 2026-10-22 |
| 45 | 禁止語の正規化 | なし | 全角・大文字 | 当たる | 当たる | OK | 2026-10-22 |
| 46 | AI 判定の JSON 解析 | なし | JSON・```json・文章・壊れた JSON | 辞書・辞書・{}・{} | 一致 | OK | 2026-10-22 |
| 47 | 画像の加工 | pending | handle_media_process | サムネイル・ready | 一致 | OK | 2026-10-22 |
| 48 | 加工済みは何もしない(冪等) | ready | handle_media_process | 何もしない | 一致 | OK | 2026-10-22 |
| 49 | プッシュ・無効な宛先の削除 | 宛先 2・うち1つ無効 | handle_notification_created | 1件送信・無効を削除 | 一致 | OK | 2026-10-22 |
| 50 | AI 判定で非表示 | flagged | handle_post_moderate | 非表示・投稿のタグは無害化して渡す | 一致 | OK | 2026-10-22 |
| 51 | 未知のイベント | なし | "nope" | ValueError | 例外 | OK | 2026-10-22 |
