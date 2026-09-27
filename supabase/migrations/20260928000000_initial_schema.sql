-- 初期スキーマ(要件定義書 8章)
-- DB へのアクセスは FastAPI 経由のみ。ブラウザ(anon / authenticated ロール)からの
-- テーブル直接アクセスは、RLS を有効にしてポリシーを作らないことで禁止する。

-- ============================================================
-- profiles(プロフィール)
-- ============================================================
create table public.profiles (
  id           uuid primary key references auth.users (id) on delete cascade,
  display_name text not null,
  avatar_url   text,
  created_at   timestamptz not null default now()
);

-- ============================================================
-- posts(投稿)
-- ============================================================
create table public.posts (
  id         bigint generated always as identity primary key,
  user_id    uuid not null references public.profiles (id) on delete cascade,
  content    text not null check (char_length(content) > 0),
  image_url  text,
  created_at timestamptz not null default now()
);

-- タイムライン(新しい順)の取得用
create index posts_created_at_idx on public.posts (created_at desc);

-- ============================================================
-- likes(いいね)
-- ============================================================
create table public.likes (
  user_id    uuid not null references public.profiles (id) on delete cascade,
  post_id    bigint not null references public.posts (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, post_id) -- 1人1投稿1回をDBで保証
);

-- 投稿ごとのいいね数の集計用
create index likes_post_id_idx on public.likes (post_id);

-- ============================================================
-- chat_messages(会話履歴)
-- ============================================================
create table public.chat_messages (
  id         bigint generated always as identity primary key,
  user_id    uuid not null references public.profiles (id) on delete cascade,
  session_id text not null,
  role       text not null check (role in ('user', 'assistant')),
  content    text not null,
  post_id    bigint references public.posts (id) on delete set null,
  created_at timestamptz not null default now()
);

-- レート制限の集計用(要件定義書 4.2)
create index chat_messages_user_id_created_at_idx on public.chat_messages (user_id, created_at);
-- 会話履歴の取得用
create index chat_messages_session_idx on public.chat_messages (user_id, session_id, created_at);

-- ============================================================
-- 新規ユーザー登録時に profiles を自動作成するトリガー
-- 表示名・アイコンは Google アカウントの情報を初期値にする
-- ============================================================
create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, display_name, avatar_url)
  values (
    new.id,
    coalesce(
      new.raw_user_meta_data ->> 'full_name',
      new.raw_user_meta_data ->> 'name',
      split_part(new.email, '@', 1)
    ),
    new.raw_user_meta_data ->> 'avatar_url'
  );
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ============================================================
-- RLS(行レベルセキュリティ)
-- ポリシーを作らないため、anon / authenticated ロールからは一切アクセスできない。
-- FastAPI はテーブル所有者(postgres)で接続するため RLS の影響を受けない。
-- ============================================================
alter table public.profiles      enable row level security;
alter table public.posts         enable row level security;
alter table public.likes         enable row level security;
alter table public.chat_messages enable row level security;
