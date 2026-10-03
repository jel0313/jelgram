// API の入出力の形。項目名は API の JSON と同じ(snake_case)にしている。
// 画面接続(WBS 5.x)で、API 仕様に合わせて見直す。5.2 で OpenAPI から生成した型に置き換えてもよい。

/** 投稿者 */
export type Author = {
  id: string;
  display_name: string;
  avatar_url: string | null;
};

/** 投稿 1 件(タイムラインの 1 行) */
export type Post = {
  id: number;
  content: string;
  image_url: string | null;
  /** ISO 8601(UTC) */
  created_at: string;
  author: Author;
  like_count: number;
  liked_by_me: boolean;
};

/** 投稿するときに送る内容 */
export type PostCreate = {
  content: string;
  image_url: string | null;
};

/** いいね・取り消しの結果 */
export type LikeResult = {
  post_id: number;
  like_count: number;
  liked_by_me: boolean;
};

/** AI チャットの 1 メッセージ */
export type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  /** 「この投稿について」で質問したときの投稿 id */
  post_id: number | null;
  /** ISO 8601(UTC) */
  created_at: string;
};

/** AI チャットに送る内容 */
export type ChatRequest = {
  message: string;
  session_id: string;
  post_id: number | null;
};

/** AI チャットの応答 */
export type ChatResponse = {
  reply: ChatMessage;
};

/** 投稿を編集するときに送る内容(2次) */
export type PostUpdate = {
  content: string;
};

/** ユーザー(ユーザーページの上部。4次) */
export type UserProfile = {
  id: string;
  display_name: string;
  avatar_url: string | null;
  /** ISO 8601(UTC)。参加した日 */
  created_at: string;
  post_count: number;
};

/** プロフィールを変更するときに送る内容(4次) */
export type ProfileUpdate = {
  display_name: string;
  avatar_url: string | null;
};

/** AI チャットの会話 1 つ(会話の一覧。5次) */
export type ChatSession = {
  session_id: string;
  /** 最初のメッセージ(一覧の見出し) */
  title: string;
  /** ISO 8601(UTC) */
  last_message_at: string;
};
