-- 画像(メタデータは DB、本体はストレージ)・カルーセル・ストーリー(9章・11-5)

-- ============================================================
-- 非公開バケット:画像は API が認可チェックしたうえで、期限付きの署名付き URL で返す(9-6・9-7)
-- ============================================================
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'media',
  'media',
  false,
  5242880, -- 5MB
  array['image/jpeg', 'image/png', 'image/webp', 'image/gif']
);

-- ============================================================
-- media(画像のメタデータ)
-- ============================================================
create table public.media (
  id             uuid primary key default gen_random_uuid(),
  owner_id       uuid not null references public.profiles (id) on delete cascade,
  path           text not null unique,  -- ストレージ内のパス(<owner_id>/<uuid>.<拡張子>)
  thumbnail_path text,
  content_type   text not null,
  size_bytes     integer not null check (size_bytes > 0),
  width          integer,
  height         integer,
  status         text not null default 'pending' check (status in ('pending', 'ready', 'failed')),
  created_at     timestamptz not null default now()
);

create index media_owner_id_idx on public.media (owner_id, created_at desc);

-- ============================================================
-- post_media(カルーセル:1投稿に最大10枚、並び順つき)
-- ============================================================
create table public.post_media (
  post_id  bigint not null references public.posts (id) on delete cascade,
  media_id uuid not null unique references public.media (id) on delete cascade,
  position smallint not null check (position between 0 and 9),
  primary key (post_id, position)
);

-- ============================================================
-- プロフィール画像(9-9)
-- ============================================================
alter table public.profiles
  add column avatar_media_id uuid references public.media (id) on delete set null;

-- ============================================================
-- stories(ストーリー:24時間で期限切れ)
-- ============================================================
create table public.stories (
  id         bigint generated always as identity primary key,
  user_id    uuid not null references public.profiles (id) on delete cascade,
  media_id   uuid not null references public.media (id) on delete cascade,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default now() + interval '24 hours'
);

create index stories_user_id_idx on public.stories (user_id, expires_at desc);
create index stories_expires_at_idx on public.stories (expires_at);

alter table public.media      enable row level security;
alter table public.post_media enable row level security;
alter table public.stories    enable row level security;
