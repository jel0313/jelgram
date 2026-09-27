# 要件定義書:AI常駐型SNS(Grok風チャットアシスタント)

## 1. 概要

Instagram/X(旧Twitter)のようなSNS上に、Grokのような「常駐AIチャット」を組み込んだミニマムアプリ。
タイムライン上の投稿について、AIに質問したり解説してもらったりできる体験を提供する。

## 2. コンセプト

- 疑似タイムライン(投稿一覧)を表示
- 画面に常駐するAIチャットに、投稿について質問したり雑談したりできる
- AIキャラクターは「辛口だけど愛のある」トーン(Grok的立ち位置)

## 3. 機能要件

### 3.1 タイムライン機能
- 投稿一覧の表示(ユーザー名、本文、画像、いいね数、投稿日時)
- 投稿の新規作成(テキスト+画像)
- 画像アップロード(S3へ直接アップロード)

### 3.2 AIチャット機能
- 画面常駐のチャットUI
- ユーザーの自由入力に対してAIが応答
- 「この投稿について」ボタンから、特定の投稿をコンテキストに含めて質問可能
- 会話履歴の保持(DBに保存、セッション単位)
- AIキャラクター性(辛口/フレンドリー等)をシステムプロンプトで制御

### 3.3 画像アップロード機能
- S3への直接アップロード(Presigned URL方式、パターンB)
- フロントエンドでのバリデーション(拡張子・サイズ)
- 将来的な拡張:S3 Presigned URL発行時のConditions指定(content-length-range、Content-Type制限)によるバックエンド側ガード

## 4. 非機能要件

- 個人開発・検証レベルのスケールを想定(大規模アクセスは非対象)
- 無料枠内での運用を最優先(AWS無料枠・GitHub無料枠)
- レート制限:AI呼び出し(Gemini API無料枠)の急激な消費を防ぐため、簡易的なレート制限(IPベース等)を検討

## 5. 技術スタック

| レイヤー | 技術 |
|---|---|
| フロントエンド | Next.js / Tailwind CSS / shadcn/ui |
| バックエンド | Python / FastAPI |
| データベース | PostgreSQL(AWS RDS) |
| 画像ストレージ | AWS S3(Presigned URL方式) |
| AI | Google Gemini API(無料枠) |
| インフラ | AWS(EC2, RDS, S3) |
| デプロイ/CI | GitHub Actions(無料枠) |

## 6. システム構成

```
[GitHub] --push--> [GitHub Actions] --deploy--> [EC2 (t2/t3.micro)]
                                                    ├─ Next.js (PM2, port 3000)
                                                    ├─ FastAPI (Uvicorn, port 8000)
                                                    └─ Nginx (リバースプロキシ, port 80/443)
                                                          ↓
                                                   [RDS PostgreSQL (db.t3.micro)]

[ブラウザ] --画像を直接アップロード--> [S3]
   ↑
   └─ Presigned URLはFastAPI経由で取得
```

- EC2 1台にNext.js・FastAPI・Nginxを同居(無料枠のインスタンス時間を節約)
- Nginxで `/api/*` をFastAPIへ、それ以外をNext.jsへ振り分け
- Next.jsのビルドはGitHub Actions上で実施し、成果物のみEC2へ転送(EC2のメモリ不足対策)

## 7. データベース設計(案)

### posts(投稿)
| カラム | 型 | 説明 |
|---|---|---|
| id | serial (PK) | 投稿ID |
| user_name | varchar | 投稿者名 |
| content | text | 本文 |
| image_url | varchar (nullable) | S3画像URL |
| likes | integer | いいね数 |
| created_at | timestamp | 投稿日時 |

### chat_messages(会話履歴)
| カラム | 型 | 説明 |
|---|---|---|
| id | serial (PK) | メッセージID |
| session_id | varchar | セッション識別子 |
| role | varchar | user / assistant |
| content | text | メッセージ内容 |
| post_id | integer (nullable, FK) | 紐づく投稿(任意) |
| created_at | timestamp | 送信日時 |

## 8. API設計(案)

| メソッド | パス | 説明 |
|---|---|---|
| GET | /posts | 投稿一覧取得 |
| POST | /posts | 投稿新規作成 |
| POST | /uploads/presign | S3 Presigned URL発行 |
| POST | /chat | AIチャット応答取得(message, context, history) |
| GET | /chat/history | セッションの会話履歴取得 |

## 9. AWS無料枠に関する注意事項

- EC2 / RDSの無料枠は**アカウント作成から12ヶ月間**が対象。以降は課金が発生するため、継続運用する場合は移行・縮小の計画が必要
- S3無料枠:5GBストレージ、PUT/POST/LIST 2,000件/月、GET 20,000件/月(12ヶ月間)
- Gemini API無料枠にもリクエスト数/トークン数の上限があるため、想定外のアクセス急増時は制限に達する可能性あり

## 10. 未確定・要検討事項

- [ ] リポジトリ構成(モノレポ or フロント/バック分割)
- [ ] ユーザー認証の要否(現状は想定なし、ゲスト利用前提)
- [ ] AIキャラクター(口調・性格)のシステムプロンプト詳細
- [ ] レート制限の具体的な実装方式
- [ ] 独自ドメイン・SSL証明書(Let's Encrypt)の設定要否
- [ ] 本番運用時のAWS無料枠終了後の移行方針
