# jelgram

タイムラインに「辛口だけど愛のある」AI が常駐する、ミニ SNS。
投稿を見ながら、画面のチャットで AI に質問したりツッコんでもらったりできる。

- 詳しい仕様:[要件定義書](docs/要件定義書.md)
- 進捗:[WBS](docs/WBS_進捗管理表.md)

---

## 目次

1. [構成](#1-構成)
2. [初めてのセットアップ](#2-初めてのセットアップ)
3. [毎日の立ち上げ方](#3-毎日の立ち上げ方)
4. [よく使うコマンド](#4-よく使うコマンド)
5. [環境変数](#5-環境変数)
6. [開発の進め方](#6-開発の進め方)
7. [DB のスキーマ変更](#7-db-のスキーマ変更)
8. [コミット前のチェック](#8-コミット前のチェック)
9. [守ること(秘密情報)](#9-守ること秘密情報)
10. [困ったときは](#10-困ったときは)
11. [資料一覧](#11-資料一覧)

---

## 1. 構成

### 技術スタック

| レイヤー       | 技術                               | ホスティング     |
| -------------- | ---------------------------------- | ---------------- |
| フロントエンド | Next.js / Tailwind CSS / shadcn/ui | Vercel           |
| バックエンド   | Python 3.13 / FastAPI              | Render(無料)   |
| DB・画像・認証 | Supabase(PostgreSQL・Storage・Auth) | Supabase         |
| AI             | Gemini API(`gemini-3.5-flash-lite`) | —                |

ツール:Node.js 24(fnm)・pnpm・uv・pytest・Ruff・Vitest

### システムの流れ

```
ブラウザ(Next.js / localhost:3000)
   ├→ Supabase Auth ……… Google ログイン → JWT を受け取る
   ├→ FastAPI(localhost:8000)… JWT 付きで API を呼ぶ
   │     ├→ Supabase PostgreSQL
   │     └→ Gemini API
   └→ Supabase Storage …… 画像を直接アップロード(署名付き URL は FastAPI から取得)
```

### フォルダ構成

```
jelgram/
├── apps/
│   ├── api/                FastAPI(バックエンド)
│   │   ├── app/            アプリ本体(main.py・config.py・routers/)
│   │   ├── tests/          pytest のテスト
│   │   ├── pyproject.toml  依存パッケージ・pytest・Ruff の設定
│   │   └── .env.example    環境変数のひな形
│   └── web/                Next.js(フロントエンド。5.1 で作成予定)
│       └── .env.example    環境変数のひな形
├── supabase/migrations/    DB スキーマの SQL
├── docs/                   要件定義書・WBS・詳細設計書など
└── .node-version           Node.js のバージョン(24)
```

---

## 2. 初めてのセットアップ

新しい PC で始めるとき、またはリポジトリを clone し直したときに1回だけ行う。
アカウント作成や Supabase・Google の管理画面での設定など、**詳しい手順は [開発環境構築手順](docs/開発環境構築手順.md)** にある。ここではローカルで必要な作業だけをまとめる。

### 2.1 ツールを入れる

```
brew install uv fnm pnpm
fnm install --lts
```

`~/.zshrc` の **末尾** に次を追加して、ターミナルを開き直す。

```
eval "$(fnm env --use-on-cd --version-file-strategy=recursive --shell zsh)"
```

✅ 確認:`node -v` が `v24.x`、`pnpm -v` と `uv --version` でバージョンが表示される

### 2.2 リポジトリを取得する

```
git clone https://github.com/jel0313/jelgram.git
cd jelgram
```

### 2.3 環境変数ファイルを作る

```
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env.local
```

値の入れ方は [5. 環境変数](#5-環境変数) を参照。値は開発用 Supabase・Google AI Studio の管理画面、またはパスワードマネージャーから取る。

### 2.4 パッケージを入れる

```
cd apps/api
uv sync
```

- Python 3.13 と仮想環境(`apps/api/.venv`)も自動で用意される。`source .venv/bin/activate` は不要
- フロントエンドは 5.1 で作成後、`cd apps/web && pnpm install` を行う

### 2.5 VS Code の設定

- 拡張機能:Python、Ruff、ESLint、Tailwind CSS IntelliSense
- `Cmd + Shift + P` →「Python: Select Interpreter」→ `apps/api/.venv` を選ぶ(import の赤い波線が消える)

✅ 確認:[3. 毎日の立ち上げ方](#3-毎日の立ち上げ方) の手順で API が起動し、テストがすべて成功する

---

## 3. 毎日の立ち上げ方

### 3.1 バックエンド(FastAPI)

```
cd apps/api
uv run fastapi dev app/main.py
```

| URL                                                            | 内容                                        |
| -------------------------------------------------------------- | ------------------------------------------- |
| [http://localhost:8000/health](http://localhost:8000/health)   | 動作確認。`{"status":"ok"}` が出れば OK     |
| [http://localhost:8000/docs](http://localhost:8000/docs)       | API ドキュメント。ここから API を試せる     |

- ファイルを保存すると自動で再起動する
- 止めるときは `Ctrl + C`

### 3.2 フロントエンド(Next.js)※ 5.1 で作成後

**別のターミナル** で起動する(バックエンドと同時に動かす)。

```
cd apps/web
pnpm dev
```

→ [http://localhost:3000](http://localhost:3000) を開く

### 3.3 始める前のチェック

- **開発用 Supabase が一時停止していないか**:しばらく使っていないと止まる。[Supabase のダッシュボード](https://supabase.com/dashboard) で `jelgram-dev` を開き、Paused なら **Restore** を押す(数分かかる)
- **最新の状態か**:`git pull`
- **依存パッケージが増えていないか**:`pyproject.toml` や `uv.lock` が変わっていたら `uv sync`

---

## 4. よく使うコマンド

### バックエンド(`apps/api` で実行)

| やりたいこと                     | コマンド                         |
| -------------------------------- | -------------------------------- |
| 起動                             | `uv run fastapi dev app/main.py` |
| テストを全部実行                 | `uv run pytest`                  |
| テストを詳しく表示               | `uv run pytest -v`               |
| 1ファイルだけテスト              | `uv run pytest tests/test_health.py` |
| コードの書き方を整える           | `uv run ruff format .`           |
| 問題のある書き方をチェック       | `uv run ruff check .`            |
| 自動で直せるものは直す           | `uv run ruff check . --fix`      |
| パッケージを追加                 | `uv add <パッケージ名>`          |
| 開発用パッケージを追加           | `uv add --dev <パッケージ名>`    |
| `uv.lock` どおりに入れ直す       | `uv sync`                        |

- Python のコマンドは必ず `uv run` を付ける(`.venv` の Python が使われる)

### フロントエンド(`apps/web` で実行)※ 5.1 で作成後

| やりたいこと     | コマンド             |
| ---------------- | -------------------- |
| 起動             | `pnpm dev`           |
| テスト           | `pnpm test`          |
| パッケージを追加 | `pnpm add <名前>`    |

実際のスクリプト名は 5.1 で決まり次第、ここを更新する。

---

## 5. 環境変数

値そのものは **リポジトリに書かない**。項目名は `.env.example` を見る。

### バックエンド:`apps/api/.env`

| 項目                     | 取得場所・内容                                                                  |
| ------------------------ | ------------------------------------------------------------------------------- |
| `SUPABASE_URL`           | Supabase → Project Settings → Data API                                          |
| `SUPABASE_SECRET_KEY`    | Supabase → Project Settings → API Keys(`sb_secret_...`)。**秘密**             |
| `DATABASE_URL`           | Supabase → 画面上部の Connect → **Session pooler**。`[YOUR-PASSWORD]` を `[ ]` ごと DB パスワードに置き換える。**秘密** |
| `SUPABASE_STORAGE_BUCKET`| `post-images`(初期値のまま)                                                  |
| `GEMINI_API_KEY`         | [Google AI Studio](https://aistudio.google.com/apikey)(`jelgram-dev` プロジェクト)。**秘密** |
| `GEMINI_MODEL`           | `gemini-3.5-flash-lite`(初期値のまま)                                        |
| `RATE_LIMIT_*`           | レート制限の上限(初期値のまま。要件定義書 4.2)                              |
| `CORS_ALLOW_ORIGINS`     | `http://localhost:3000`(複数ある場合はカンマ区切り)                          |

- 必須項目が空だと、API の起動時にエラーになる(エラーに項目名が出る)
- テストは `.env` を使わず、ダミー値で動く

### フロントエンド:`apps/web/.env.local`

| 項目                                   | 取得場所・内容                                             |
| -------------------------------------- | ---------------------------------------------------------- |
| `NEXT_PUBLIC_SUPABASE_URL`             | バックエンドの `SUPABASE_URL` と同じ                        |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Supabase → Project Settings → API Keys(`sb_publishable_...`) |
| `NEXT_PUBLIC_API_BASE_URL`             | `http://localhost:8000`                                    |

- `NEXT_PUBLIC_` で始まる値はブラウザに公開される。**秘密の値(secret key など)は絶対に入れない**

---

## 6. 開発の進め方

機能ごとに、次の4工程を1周ずつ回す(要件定義書 7.4)。

```
詳細設計 → 製造 → テスト → 打鍵 → コミット
```

| 工程     | やること                                                        | 成果物                                              |
| -------- | --------------------------------------------------------------- | --------------------------------------------------- |
| 詳細設計 | 作るもの・API 仕様・テストケース・打鍵項目を決める              | `docs/詳細設計_手順/<ID>_<機能名>/詳細設計書.md`・`マニュアル.md` |
| 製造     | マニュアルの STEP に沿ってコードを書く                          | ソースコード                                        |
| テスト   | 自動テストを書いて、すべて成功させる                            | テストコード                                        |
| 打鍵     | 実際に動かして確認する(画面がない間は `/docs` から API を呼ぶ) | マニュアルの打鍵結果欄                              |

- 工程が終わるたびに [WBS](docs/WBS_進捗管理表.md) の記号を更新する(🔄 作業中 → ✅ 完了)。全工程が終わったら完了日を記入する
- 作っている途中で設計を変えたら、詳細設計書も合わせて直す
- 新しい API は `apps/api/app/routers/` にファイルを足し、`app/main.py` に `include_router` で登録する
- API の応答は必ず Pydantic モデルで定義する(フロントエンドの型を自動生成するため)

---

## 7. DB のスキーマ変更

テーブルの追加・変更は、必ず SQL ファイルで管理する。

1. `supabase/migrations/` に日時付きのファイルを追加する(例:`20261001000000_add_xxx.sql`)
2. Supabase の **SQL Editor** → **New query** に中身を貼り付けて **Run**
3. 開発用(`jelgram-dev`)で確認してから、本番用にも同じ手順で実行する

- 管理画面(Table Editor)で直接テーブルを変更しない。SQL ファイルと実際の DB がずれてしまう
- すでに実行した SQL ファイルは書き換えず、変更は新しいファイルで追加する

---

## 8. コミット前のチェック

テストの自動実行(CI)は3次開発で入れる予定。それまでは **手元で必ず確認してからコミット** する。

```
cd apps/api
uv run ruff format .
uv run ruff check .
uv run pytest
```

3つとも問題なければ、ルートに戻って確認する。

```
cd ../..
git status
```

- `apps/api/.env`・`apps/web/.env.local` が一覧に **出ていない** こと(出ていたら絶対にコミットしない)
- `.venv/`・`node_modules/` が一覧に出ていないこと

```
git add <ファイル>
git commit -m "4.2 認証(JWT検証)を実装"
git push
```

- コミットメッセージは日本語で、先頭に WBS の ID を付ける

---

## 9. 守ること(秘密情報)

| してはいけないこと                                          | 理由                                                          |
| ----------------------------------------------------------- | ------------------------------------------------------------- |
| `.env`・`.env.local` をコミットする                         | キーが GitHub に公開され、悪用される                          |
| secret key・DB パスワード・Gemini キーをコードや docs に書く | 同上                                                          |
| secret key を `NEXT_PUBLIC_` の変数に入れる                 | ブラウザに配られ、誰でも見られる                              |
| キーをチャットやメモ用ファイルに貼る                        | 漏れる経路が増える。キーはパスワードマネージャーで保管する    |

- `docs/設定/` は個人メモ用で `.gitignore` 済み。それでも秘密の値は書かない
- 万一漏れたら、すぐに管理画面でキーを再発行する(DB パスワードは Project Settings → Database → Reset database password)

---

## 10. 困ったときは

| 症状                                                     | 対処                                                                                     |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `ModuleNotFoundError: No module named 'app'`             | `apps/api` 以外で実行している。`cd apps/api` してから実行する                            |
| `fastapi: command not found`                             | `uv run` を付け忘れている                                                                |
| 起動時に `ValidationError`・`Field required`             | `.env` に必須項目がない。エラーに出ている項目名を確認する                                |
| 起動時に `String should have at least 1 character`       | `.env` の必須項目の値が空                                                                |
| `Address already in use`                                 | 別のターミナルでサーバーが動いたまま。そちらを `Ctrl + C` で止める                       |
| DB につながらない                                        | 開発用 Supabase が一時停止していないか確認する([3.3](#33-始める前のチェック))         |
| `node -v` が 24 系にならない                             | `~/.zshrc` の fnm の設定が末尾にあるか確認し、ターミナルを開き直す                       |
| `VIRTUAL_ENV=... does not match` という警告              | 別の仮想環境が有効なだけで、動作に問題はない。気になる場合は `deactivate`                 |
| VS Code で import に赤い波線                             | Python のインタープリターを `apps/api/.venv` に切り替える                                |
| ブラウザで API の結果が CORS エラーになる                | `CORS_ALLOW_ORIGINS` に画面の URL(`http://localhost:3000`)が入っているか確認する        |

機能ごとのトラブルは、各機能のマニュアル末尾の「困ったときは」を見る。

---

## 11. 資料一覧

| 資料                                                          | 内容                                          |
| ------------------------------------------------------------- | --------------------------------------------- |
| [要件定義書](docs/要件定義書.md)                               | 何を作るか・技術選定・DB/API 設計・ロードマップ |
| [WBS](docs/WBS_進捗管理表.md)                                  | 作業一覧と進捗                                |
| [開発環境構築手順](docs/開発環境構築手順.md)                   | アカウント・Supabase・Google の設定手順       |
| [詳細設計_手順/](docs/詳細設計_手順/)                          | 機能ごとの詳細設計書とマニュアル              |
| [supabase/migrations/](supabase/migrations/)                   | DB スキーマの SQL                             |
