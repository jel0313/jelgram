-- 投稿の拡張とコメント(2-3 1対多・2-6・3-4 編集・3-6 論理削除・10-2 カウンタ・楽観的ロック)

-- ============================================================
-- posts に列を追加
-- ============================================================
alter table public.posts
  add column updated_at        timestamptz not null default now(),
  add column deleted_at        timestamptz,                      -- 論理削除(3-6)
  add column hidden_at         timestamptz,                      -- 管理者による非表示(7-5)
  add column comments_disabled boolean not null default false,
  add column version           integer not null default 1,       -- 楽観的ロック(10-2)
  add column like_count        integer not null default 0 check (like_count >= 0),
  add column comment_count     integer not null default 0 check (comment_count >= 0);

alter table public.posts
  add constraint posts_content_max_length check (char_length(content) <= 500);

-- 既存のいいねからカウンタを埋める(21-5)
update public.posts p
set like_count = (select count(*) from public.likes l where l.post_id = p.id);

create trigger posts_set_updated_at
  before update on public.posts
  for each row execute function public.set_updated_at();

-- 一覧用のインデックスを、削除・非表示を除いた部分インデックスに置き換える(4-7)
drop index public.posts_created_at_idx;
create index posts_timeline_idx on public.posts (created_at desc, id desc)
  where deleted_at is null and hidden_at is null;
create index posts_user_id_idx on public.posts (user_id, created_at desc, id desc)
  where deleted_at is null;

-- ============================================================
-- comments(コメント)
-- ============================================================
create table public.comments (
  id         bigint generated always as identity primary key,
  post_id    bigint not null references public.posts (id) on delete cascade,
  user_id    uuid not null references public.profiles (id) on delete cascade,
  content    text not null check (char_length(content) between 1 and 300),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create index comments_post_id_idx on public.comments (post_id, created_at, id)
  where deleted_at is null;
create index comments_user_id_idx on public.comments (user_id);

create trigger comments_set_updated_at
  before update on public.comments
  for each row execute function public.set_updated_at();

alter table public.comments enable row level security;
