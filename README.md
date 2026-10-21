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

ツール:Node.js 24(fnm)・pnpm・uv・pytest・Ruff・mypy・Vitest・Docker(ローカルの Supabase・Redis)・Supabase CLI

### システムの流れ

```
ブラウザ(Next.js / localhost:3000)
   ├→ Supabase Auth ……… Google ログイン → JWT を受け取る
   └→ FastAPI(localhost:8000/api/v1)… JWT 付きで API を呼ぶ
         ├→ Supabase PostgreSQL ……… 生 SQL
         ├→ Supabase Storage …………… 画像(非公開バケット・署名付き URL)
         ├→ Redis ………………………… キャッシュ・レート制限・ジョブキュー
         └→ Gemini API

Celery ワーカー(別プロセス)… Outbox のイベント(画像の加工・AI 判定・プッシュ通知)・定期ジョブ
```

### フォルダ構成

```
jelgram/
├── apps/
│   ├── api/                FastAPI(バックエンド)
│   │   ├── app/            アプリ本体(機能別のフォルダ。docs/バックエンド構成.md)
│   │   ├── tests/          unit(UT)・integration(IT)・load(負荷テスト)
│   │   ├── scripts/        シードデータ
│   │   └── Dockerfile
│   └── web/                Next.js(フロントエンド。画面はモック)
├── supabase/               config.toml(ローカル環境)・migrations/(DB スキーマの SQL)
├── docs/                   要件定義書・基本設計・詳細設計・テスト仕様・運用手順書など
├── infra/                  Prometheus の設定
├── docker-compose.yml      Redis・API・ワーカー・監視
└── .github/                CI(workflows)・Dependabot・家庭教師モードの指示書
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
mkdir -p ~/dev && cd ~/dev
git clone https://github.com/jel0313/jelgram.git
cd jelgram
```

> ⚠️ **デスクトップ・書類フォルダには置かない**:この2つは iCloud と同期されていて、iCloud がファイルの中身をクラウドに移すことがある。`.venv` や `node_modules` の中身が消えると、Python や Node がファイルの読み込み待ちで固まる。`~/dev` のような iCloud の外に置く。

### 2.3 環境変数ファイルを作る

```
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env.local
```

値の入れ方は [5. 環境変数](#5-環境変数) を参照。値は開発用 Supabase・Google AI Studio の管理画面、またはパスワードマネージャーから取る。

### 2.4 パッケージを入れる

```
brew install supabase/tap/supabase   # Supabase CLI(ローカルの DB・Auth・Storage)
cd apps/api
uv sync
```

- Python 3.13 と仮想環境(`apps/api/.venv`)も自動で用意される。`source .venv/bin/activate` は不要
- Docker Desktop を起動しておく(ローカルの Supabase と Redis が使う)
- フロントエンドは `cd apps/web && pnpm install`

### 2.5 VS Code の設定

- 拡張機能:Python、Ruff、ESLint、Tailwind CSS IntelliSense
- `Cmd + Shift + P` →「Python: Select Interpreter」→ `apps/api/.venv` を選ぶ(import の赤い波線が消える)

✅ 確認:[3. 毎日の立ち上げ方](#3-毎日の立ち上げ方) の手順で API が起動し、テストがすべて成功する

---

## 3. 毎日の立ち上げ方

### 3.1 ローカルの Supabase と Redis

```
supabase start -x studio,imgproxy,edge-runtime,logflare,vector,realtime,postgres-meta,supavisor
docker compose up -d redis
```

- 初回はイメージの取得に数分かかる。マイグレーション(`supabase/migrations/`)も自動で適用される
- 接続情報(URL・キー)は `supabase status` で見られる。`apps/api/.env` にはこの値を入れる(クラウドの開発用 Supabase を使う場合はそちらの値)
- 止めるとき:`supabase stop`・`docker compose stop`

### 3.2 バックエンド(FastAPI)

```
cd apps/api
uv run fastapi dev app/main.py
```

| URL                                                            | 内容                                        |
| -------------------------------------------------------------- | ------------------------------------------- |
| [http://localhost:8000/health](http://localhost:8000/health)   | DB・Redis の接続確認                        |
| [http://localhost:8000/docs](http://localhost:8000/docs)       | API ドキュメント。ここから API を試せる     |
| [http://127.0.0.1:54324](http://127.0.0.1:54324)               | Mailpit(ローカルで送ったメールの受信箱)   |

- API は `/api/v1` の下にある(例:`/api/v1/posts`)
- ファイルを保存すると自動で再起動する。止めるときは `Ctrl + C`

### 3.3 ワーカー(画像の加工・通知・定期ジョブ)

別のターミナルで2つ起動する。

```
cd apps/api
uv run celery -A app.worker.celery_app worker --loglevel=INFO
uv run celery -A app.worker.celery_app beat --loglevel=INFO
```

### 3.4 フロントエンド(Next.js)

```
cd apps/web
pnpm dev
```

→ [http://localhost:3000](http://localhost:3000) を開く

---

## 4. よく使うコマンド

### バックエンド(`apps/api` で実行)

| やりたいこと                     | コマンド                         |
| -------------------------------- | -------------------------------- |
| 起動                             | `uv run fastapi dev app/main.py` |
| テストを全部実行(UT + IT)      | `uv run pytest`                  |
| UT だけ(DB・Redis 不要)        | `uv run pytest tests/unit`       |
| カバレッジ                       | `uv run pytest --cov`            |
| 型チェック                       | `uv run mypy app`                |
| コードの書き方を整える           | `uv run ruff format .`           |
| 問題のある書き方をチェック       | `uv run ruff check .`            |
| シードデータを入れる(ローカルだけ) | `uv run python -m scripts.seed --users 20 --posts 10` |
| 負荷テスト                       | `uv run locust -f tests/load/locustfile.py --host http://localhost:8000` |
| パッケージを追加                 | `uv add <パッケージ名>`          |
| `uv.lock` どおりに入れ直す       | `uv sync`                        |

- Python のコマンドは必ず `uv run` を付ける(`.venv` の Python が使われる)
- IT は `supabase start` と `docker compose up -d redis` が必要。テストごとに DB をロールバックするので、データは残らない

### フロントエンド(`apps/web` で実行)

| やりたいこと     | コマンド             |
| ---------------- | -------------------- |
| 起動             | `pnpm dev`           |
| テスト           | `pnpm test`          |
| パッケージを追加 | `pnpm add <名前>`    |


---

## 5. 環境変数

値そのものは **リポジトリに書かない**。項目名は `.env.example` を見る。

### バックエンド:`apps/api/.env`

項目と説明は [apps/api/.env.example](apps/api/.env.example) にすべて書いてある。主なもの:

| 項目                     | 取得場所・内容                                                                  |
| ------------------------ | ------------------------------------------------------------------------------- |
| `SUPABASE_URL`・`SUPABASE_SECRET_KEY` | ローカル:`supabase status` / クラウド:Project Settings → API Keys。**秘密** |
| `DATABASE_URL`           | ローカル:`postgresql://postgres:postgres@127.0.0.1:54322/postgres` / クラウド:Connect → Session pooler。**秘密** |
| `REDIS_URL`              | `redis://localhost:6379/0`                                                      |
| `GEMINI_API_KEY`         | [Google AI Studio](https://aistudio.google.com/apikey)。**秘密**               |
| `RATE_LIMIT_*`           | レート制限の上限(要件定義書 4.2)                                             |
| `CORS_ALLOW_ORIGINS`     | `http://localhost:3000`(複数ある場合はカンマ区切り)                          |
| `APP_ENV`                | development / test / production。本番では /docs が非公開になる                 |

- 必須項目が空だと、API の起動時にエラーになる(エラーに項目名が出る)
- テストは `.env` の秘密の値を使わない(ダミー値とローカルの DB・Redis で動く)

### フロントエンド:`apps/web/.env.local`

| 項目                                   | 取得場所・内容                                             |
| -------------------------------------- | ---------------------------------------------------------- |
| `NEXT_PUBLIC_SUPABASE_URL`             | バックエンドの `SUPABASE_URL` と同じ                        |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Supabase → Project Settings → API Keys(`sb_publishable_...`) |
| `NEXT_PUBLIC_API_BASE_URL`             | `http://localhost:8000/api/v1`(API は /api/v1 の下)     |

- `NEXT_PUBLIC_` で始まる値はブラウザに公開される。**秘密の値(secret key など)は絶対に入れない**

---

## 6. 開発の進め方

`.github/copilot-instructions.md`(家庭教師モード)の工程で進める。V 字モデル:

```
要件定義 ─────────────────── 総合テスト(ST)
   基本設計 ─────────── 結合テスト(IT)
      詳細設計 ─── 単体テスト(UT)
            製造
```

| 工程 | 成果物 |
|---|---|
| 要件定義 | [docs/要件定義書.md](docs/要件定義書.md) |
| 基本設計 | [docs/基本設計/](docs/基本設計/API一覧.md) |
| 詳細設計 | [docs/詳細設計/](docs/詳細設計/基盤.md) |
| 製造 | `apps/api/app/`([バックエンド構成](docs/バックエンド構成.md)に従う) |
| UT・IT・ST | [docs/テスト仕様/](docs/テスト仕様/IT_シナリオ.md)・`apps/api/tests/` |
| 不具合 | [docs/不具合管理表.md](docs/不具合管理表.md) |

- 作業は必ずブランチを切る(`feature/<機能>`・`practice/<問題ID>`。[運用手順書](docs/運用手順書.md) 5章)
- API の応答は必ず Pydantic モデルで定義する(フロントエンドの型を自動生成するため)

---

## 7. DB のスキーマ変更

テーブルの追加・変更は、必ず SQL ファイルで管理する。

1. `supabase migration new <名前>` でファイルを作る(`supabase/migrations/<日時>_<名前>.sql`)
2. SQL を書き、`supabase db reset` でローカルに最初から適用し直して確かめる(ローカルのデータは消える)
3. テスト(`uv run pytest`)が通ったら、本番は `supabase link` → `supabase db push`

- 管理画面(Table Editor)で直接テーブルを変更しない。SQL ファイルと実際の DB がずれてしまう
- すでに適用した SQL ファイルは書き換えず、変更は新しいファイルで追加する
- 既存データがあるテーブルに NOT NULL の列を足すときは「NULL 可で追加 → 既存行を埋める → 制約を付ける」の順にする(例:`20261022000000_profiles_extend.sql`)

---

## 8. コミット前のチェック

push すると GitHub Actions が同じチェックを自動で行う(`.github/workflows/api.yml`)。手元でも確認してからコミットする。

```
cd apps/api
uv run ruff format . && uv run ruff check . && uv run mypy app && uv run pytest
```

- 自動で確認したい場合:`uv run pre-commit install --config ../../.pre-commit-config.yaml`
- `apps/api/.env`・`apps/web/.env.local` が `git status` に **出ていない** こと(出ていたら絶対にコミットしない)
- コミットメッセージは日本語で、先頭に章や問題の ID を付ける

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
| クラウドの開発用 DB につながらない                        | Supabase のダッシュボードで `jelgram-dev` が Paused なら Restore(しばらく使わないと止まる) |
| 起動やテストがエラーも出ずに固まる                      | プロジェクトが iCloud 同期のフォルダ(デスクトップ・書類)にある。`~/dev` に移す([2.2](#22-リポジトリを取得する)) |
| `node -v` が 24 系にならない                             | `~/.zshrc` の fnm の設定が末尾にあるか確認し、ターミナルを開き直す                       |
| `VIRTUAL_ENV=... does not match` という警告              | 別の仮想環境が有効なだけで、動作に問題はない。気になる場合は `deactivate`                 |
| VS Code で import に赤い波線                             | Python のインタープリターを `apps/api/.venv` に切り替える                                |
| ブラウザで API の結果が CORS エラーになる                | `CORS_ALLOW_ORIGINS` に画面の URL(`http://localhost:3000`)が入っているか確認する        |
| IT が「ローカルの DB が必要です」で止まる               | `supabase start` と `docker compose up -d redis` を実行する                              |
| `supabase/config.toml` を変えたのに反映されない         | `supabase stop` → `supabase start` で再起動する                                          |
| Docker のイメージ取得で `error getting credentials`     | Docker Desktop にサインインし直す。急ぐなら空の設定で取得:`DOCKER_CONFIG=$(mktemp -d) docker pull <イメージ>` |
| `/health` が 503                                        | 応答の `checks` で DB・Redis のどちらが落ちているか見る                                  |
| 画像の URL がすぐ見られなくなる                          | 署名付き URL の期限(既定 10 分)。画面は取り直す                                        |

障害の調べ方は [運用手順書](docs/運用手順書.md) 4章。

---

## 11. 資料一覧

| 資料 | 内容 |
|---|---|
| [APP_STATUS.md](APP_STATUS.md) | 現状(機能一覧・問題点・ライブラリ) |
| [要件定義書](docs/要件定義書.md) | 何を作るか・技術選定・非機能要件 |
| [基本設計/](docs/基本設計/API一覧.md) | API 一覧・ER 図・認証認可・エラー方針・外部連携 |
| [詳細設計/](docs/詳細設計/基盤.md) | 機能ごとの処理フロー・関数・SQL |
| [テスト仕様/](docs/テスト仕様/IT_シナリオ.md) | UT・IT・ST の仕様と結果 |
| [不具合管理表](docs/不具合管理表.md) | 見つかった不具合と再発防止 |
| [バックエンド構成](docs/バックエンド構成.md) | フォルダ構成・層のルール |
| [運用手順書](docs/運用手順書.md) | デプロイ・監視・バックアップ・障害対応 |
| [学習更新履歴](docs/学習更新履歴.md) | ライブラリ・書き方の最新化の記録 |
| [WBS](docs/WBS_進捗管理表.md) | 作業一覧と進捗 |
| [開発環境構築手順](docs/開発環境構築手順.md) | アカウント・Supabase・Google の設定手順 |
| [画面設計/](docs/画面設計/画面一覧.md) | 画面ごとの画像と仕様(モック) |
