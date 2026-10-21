-- 通知・Outbox・プッシュ通知・通報・監査ログ・冪等性キー・Webhook・AI 使用量
-- (11-2・20-4・11-7・7-5・15-4・10-4・11-6・12-4)

-- ============================================================
-- notifications(通知)
-- ============================================================
create table public.notifications (
  id           bigint generated always as identity primary key,
  recipient_id uuid not null references public.profiles (id) on delete cascade,
  actor_id     uuid not null references public.profiles (id) on delete cascade,
  type         text not null check (type in ('like', 'comment', 'follow', 'follow_request', 'follow_accepted')),
  post_id      bigint references public.posts (id) on delete cascade,
  comment_id   bigint references public.comments (id) on delete cascade,
  read_at      timestamptz,
  created_at   timestamptz not null default now()
);

create index notifications_recipient_idx on public.notifications (recipient_id, created_at desc, id desc);
create index notifications_unread_idx on public.notifications (recipient_id) where read_at is null;

-- ============================================================
-- outbox_events(Outbox パターン:DB 更新と同じトランザクションで「やること」を記録し、
-- ワーカーが後から確実に実行する。20-4)
-- ============================================================
create table public.outbox_events (
  id           bigint generated always as identity primary key,
  event_type   text not null,
  payload      jsonb not null,
  attempts     integer not null default 0,
  last_error   text,
  created_at   timestamptz not null default now(),
  processed_at timestamptz
);

create index outbox_events_pending_idx on public.outbox_events (id) where processed_at is null;

-- ============================================================
-- push_subscriptions(Web Push の宛先。11-7)
-- ============================================================
create table public.push_subscriptions (
  id         bigint generated always as identity primary key,
  user_id    uuid not null references public.profiles (id) on delete cascade,
  endpoint   text not null unique,
  p256dh     text not null,
  auth       text not null,
  created_at timestamptz not null default now()
);

create index push_subscriptions_user_id_idx on public.push_subscriptions (user_id);

-- ============================================================
-- reports(通報。7-5)
-- ============================================================
create table public.reports (
  id          bigint generated always as identity primary key,
  reporter_id uuid references public.profiles (id) on delete set null,
  post_id     bigint not null references public.posts (id) on delete cascade,
  reason      text not null check (char_length(reason) between 1 and 500),
  status      text not null default 'open' check (status in ('open', 'resolved', 'dismissed')),
  resolved_by uuid references public.profiles (id) on delete set null,
  resolved_at timestamptz,
  created_at  timestamptz not null default now(),
  unique (reporter_id, post_id)
);

create index reports_status_idx on public.reports (status, created_at);

-- ============================================================
-- audit_logs(監査ログ。15-4)
-- ============================================================
create table public.audit_logs (
  id          bigint generated always as identity primary key,
  actor_id    uuid references public.profiles (id) on delete set null,
  action      text not null,
  target_type text not null,
  target_id   text not null,
  details     jsonb not null default '{}'::jsonb,
  request_id  text,
  created_at  timestamptz not null default now()
);

create index audit_logs_created_at_idx on public.audit_logs (created_at desc);

-- ============================================================
-- idempotency_keys(冪等性キー:二度押しで二重投稿しない。10-4)
-- ============================================================
create table public.idempotency_keys (
  user_id         uuid not null references public.profiles (id) on delete cascade,
  key             text not null check (char_length(key) between 1 and 255),
  request_hash    text not null,
  response_status integer,
  response_body   jsonb,
  created_at      timestamptz not null default now(),
  primary key (user_id, key)
);

create index idempotency_keys_created_at_idx on public.idempotency_keys (created_at);

-- ============================================================
-- webhook_events(Webhook の受信記録。同じイベントの重複受信を防ぐ。11-6)
-- ============================================================
create table public.webhook_events (
  provider    text not null,
  event_id    text not null,
  payload     jsonb not null,
  received_at timestamptz not null default now(),
  primary key (provider, event_id)
);

-- ============================================================
-- AI のトークン使用量(12-4)
-- ============================================================
alter table public.chat_messages
  add column prompt_tokens     integer,
  add column completion_tokens integer;

alter table public.notifications      enable row level security;
alter table public.outbox_events      enable row level security;
alter table public.push_subscriptions enable row level security;
alter table public.reports            enable row level security;
alter table public.audit_logs         enable row level security;
alter table public.idempotency_keys   enable row level security;
alter table public.webhook_events     enable row level security;
