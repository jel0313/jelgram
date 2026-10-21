-- フォロー・ブロック・ハッシュタグ・全文検索(2-4 多対多・7-3・7-4・4-3・21-7)

-- ============================================================
-- follows(フォロー。User ↔ User の自己参照の多対多)
-- 非公開アカウントへのフォローは pending → 承認で accepted
-- ============================================================
create table public.follows (
  follower_id uuid not null references public.profiles (id) on delete cascade,
  followee_id uuid not null references public.profiles (id) on delete cascade,
  status      text not null default 'accepted' check (status in ('pending', 'accepted')),
  created_at  timestamptz not null default now(),
  primary key (follower_id, followee_id),
  check (follower_id <> followee_id)
);

-- 「この人のフォロワー」の取得用(主キーは follower_id が先頭なので逆向きが必要)
create index follows_followee_id_idx on public.follows (followee_id, status);

-- ============================================================
-- blocks(ブロック)
-- ============================================================
create table public.blocks (
  blocker_id uuid not null references public.profiles (id) on delete cascade,
  blocked_id uuid not null references public.profiles (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (blocker_id, blocked_id),
  check (blocker_id <> blocked_id)
);

create index blocks_blocked_id_idx on public.blocks (blocked_id);

-- ============================================================
-- hashtags / post_hashtags(Post ↔ Hashtag の多対多)
-- ============================================================
create table public.hashtags (
  id         bigint generated always as identity primary key,
  name       text not null unique check (char_length(name) between 1 and 50),
  created_at timestamptz not null default now()
);

create table public.post_hashtags (
  post_id    bigint not null references public.posts (id) on delete cascade,
  hashtag_id bigint not null references public.hashtags (id) on delete cascade,
  primary key (post_id, hashtag_id)
);

create index post_hashtags_hashtag_id_idx on public.post_hashtags (hashtag_id, post_id desc);

-- ============================================================
-- 全文検索(21-7):日本語は単語の区切りがないため、3文字単位の部分一致(pg_trgm)を使う
-- ============================================================
create extension if not exists pg_trgm with schema extensions;

create index posts_content_trgm_idx on public.posts
  using gin (content extensions.gin_trgm_ops);
create index profiles_username_trgm_idx on public.profiles
  using gin (username extensions.gin_trgm_ops);
create index profiles_display_name_trgm_idx on public.profiles
  using gin (display_name extensions.gin_trgm_ops);

alter table public.follows       enable row level security;
alter table public.blocks        enable row level security;
alter table public.hashtags      enable row level security;
alter table public.post_hashtags enable row level security;
