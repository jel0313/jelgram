-- 投稿画像用の Storage バケット(要件定義書 3.4)
-- 公開バケット:画像は公開URLで誰でも表示できる(アプリ自体はログイン必須)
-- アップロードは FastAPI が発行する署名付きURL経由のみ。
-- storage.objects にポリシーを作らないため、ブラウザからの直接アップロード・削除はできない。

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'post-images',
  'post-images',
  true,
  5242880, -- 5MB
  array['image/jpeg', 'image/png', 'image/webp', 'image/gif']
);
