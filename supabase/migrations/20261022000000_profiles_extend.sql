-- プロフィールの拡張(2-5 ユーザー名の一意制約・2-6 updated_at・7-3 非公開・7-5 ロールと凍結・21-5 既存データの移行)

-- ============================================================
-- updated_at を自動で更新する共通のトリガー関数(2-6)
-- ============================================================
create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ============================================================
-- profiles に列を追加
-- ============================================================
alter table public.profiles
  add column username   text,
  add column bio        text not null default '' check (char_length(bio) <= 150),
  add column is_private boolean not null default false,
  add column role       text not null default 'user' check (role in ('user', 'admin')),
  add column status     text not null default 'active' check (status in ('active', 'suspended', 'deleted')),
  add column updated_at timestamptz not null default now();

alter table public.profiles
  add constraint profiles_display_name_length check (char_length(display_name) between 1 and 50);

-- 既存データの移行(21-5):既存ユーザーに仮のユーザー名を入れてから NOT NULL・一意にする
-- ① 列を NULL 可で追加 → ② 既存行を埋める → ③ 制約を付ける、の順にすると、既存データがあっても失敗しない
update public.profiles
set username = 'user_' || substr(replace(id::text, '-', ''), 1, 12)
where username is null;

alter table public.profiles
  alter column username set not null,
  add constraint profiles_username_format check (username ~ '^[a-z0-9_]{3,30}$');

create unique index profiles_username_key on public.profiles (username);

create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

-- ============================================================
-- 新規登録時のトリガーで username も入れる
-- ============================================================
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, username, display_name, avatar_url)
  values (
    new.id,
    'user_' || substr(replace(new.id::text, '-', ''), 1, 12),
    left(
      coalesce(
        nullif(new.raw_user_meta_data ->> 'full_name', ''),
        nullif(new.raw_user_meta_data ->> 'name', ''),
        split_part(new.email, '@', 1),
        'user'
      ),
      50
    ),
    new.raw_user_meta_data ->> 'avatar_url'
  );
  return new;
end;
$$;
