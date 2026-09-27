-- アプリ全体のレート制限(要件定義書 4.2:全ユーザー合計の分・日の回数)の集計用
create index chat_messages_created_at_idx on public.chat_messages (created_at);
