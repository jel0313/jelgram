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
- 画像アップロード(Supabase Storageへ直接アップロード)

### 3.2 AIチャット機能
- 画面常駐のチャットUI
- ユーザーの自由入力に対してAIが応答
- 「この投稿について」ボタンから、特定の投稿をコンテキストに含めて質問可能
- 会話履歴の保持(DBに保存、セッション単位)
- AIキャラクター性(辛口/フレンドリー等)をシステムプロンプトで制御

### 3.3 画像アップロード機能
- Supabase Storageへの直接アップロード(署名付きURL方式)
- フロントエンドでのバリデーション(拡張子・サイズ)
- 将来的な拡張:署名付きURL発行時のファイルサイズ/Content-Type制限によるバックエンド側ガード

## 4. 非機能要件

- 個人開発・検証レベルのスケールを想定(大規模アクセスは非対象)
- **期限なく無料で運用できること**を最優先(AWSのような12ヶ月限定の無料枠は避ける)
- レート制限:AI呼び出し(Gemini API無料枠)の急激な消費を防ぐため、簡易的なレート制限(IPベース等)を検討
- バックエンド(Render無料プラン)は一定時間アクセスがないとスリープする点を許容(個人開発・検証用途のため実用上は問題にしにくい想定)

## 5. 技術スタック

| レイヤー | 技術 | ホスティング | 無料枠の性質 |
|---|---|---|---|
| フロントエンド | Next.js / Tailwind CSS / shadcn/ui | Vercel | 個人利用なら期限なく無料 |
| バックエンド | Python / FastAPI | Render(無料プラン) | 期限なく無料(ただし無操作でスリープ) |
| データベース | PostgreSQL | Supabase | 期限なく無料(容量等に制限あり) |
| 画像ストレージ | Supabase Storage | Supabase(DBと同一サービス) | 期限なく無料(容量制限あり) |
| AI | Google Gemini API | — | 無料枠あり(リクエスト数/トークン数に上限) |
| デプロイ/CI | GitHub連携による自動デプロイ | Vercel / Render | 無料 |

**方針転換の理由**:当初はAWS(EC2/RDS/S3)で統一する案だったが、AWS無料枠は「アカウント作成から12ヶ月間」限定で、以降は課金が発生する。「とにかくずっと無料で使いたい」という要望に合わせ、期限のない無料枠を持つVercel・Render・Supabaseの組み合わせに変更。

## 6. システム構成

```
[GitHub] --push--> 自動デプロイ
     ├─→ [Vercel] Next.js(フロントエンド)
     └─→ [Render] FastAPI(バックエンドAPI, Uvicorn)
                        ↓
                 [Supabase PostgreSQL]
                        ↓
                 [Supabase Storage] ← 画像ファイル

[ブラウザ] --画像を直接アップロード--> [Supabase Storage]
   ↑
   └─ 署名付きURLはFastAPI経由で取得
```

- Vercel、Renderともに GitHub と連携し、push するだけで自動デプロイ
- Next.js(Vercel)から FastAPI(Render)へAPIリクエスト、FastAPIからSupabase(DB/Storage)へアクセスする構成
- サーバー管理(Nginx設定、SSH配線など)が不要になり、AWS EC2構成より運用がシンプル

## 7. データベース設計(案)

### posts(投稿)
| カラム | 型 | 説明 |
|---|---|---|
| id | serial (PK) | 投稿ID |
| user_name | varchar | 投稿者名 |
| content | text | 本文 |
| image_url | varchar (nullable) | Supabase Storage画像URL |
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
| POST | /uploads/presign | Supabase Storage署名付きURL発行 |
| POST | /chat | AIチャット応答取得(message, context, history) |
| GET | /chat/history | セッションの会話履歴取得 |

## 9. 無料枠に関する注意事項

- **Vercel**:個人(Hobby)利用なら期限なく無料。商用利用や大規模アクセスの場合は別途確認が必要
- **Render**:無料プランは期限なく利用可能だが、一定時間アクセスがないとインスタンスがスリープし、次回アクセス時に起動待ち(数十秒程度)が発生する
- **Supabase**:無料プランは期限なく利用可能。DB容量・Storage容量に上限あり(目安:DB 500MB、Storage 1GB程度、プラン内容は変動する可能性があるため利用時に要確認)。一定期間アクセスがないプロジェクトは一時停止される場合がある点にも注意
- **Gemini API**:無料枠にもリクエスト数/トークン数の上限があるため、想定外のアクセス急増時は制限に達する可能性あり

## 10. 未確定・要検討事項

- [ ] リポジトリ構成(モノレポ or フロント/バック分割)
- [ ] ユーザー認証の要否(現状は想定なし、ゲスト利用前提)
- [ ] AIキャラクター(口調・性格)のシステムプロンプト詳細
- [ ] レート制限の具体的な実装方式
- [ ] 独自ドメイン・SSL証明書の設定要否(Vercel/Renderは標準でHTTPS対応)
- [ ] Render無料プランのスリープ挙動が体験上許容できるかの検証
