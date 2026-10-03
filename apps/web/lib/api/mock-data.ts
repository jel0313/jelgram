// モック用のダミーデータと、ダミーの API が使う小さな道具。
// 画面接続がすべて終わったら、このファイルは削除する。

import type { Author, ChatMessage, Post } from "./types";

/** ログイン中のユーザー(ダミー) */
export const MOCK_ME: Author = {
  id: "c01057d5-1269-47c0-8d7c-87da6c571c77",
  display_name: "makino_test",
  avatar_url: null,
};

const HANAKO: Author = {
  id: "5b0e3c1a-9d2f-4a7e-8c61-2f4b8e9a1d03",
  display_name: "花子",
  avatar_url: "/mock/avatar-hanako.svg",
};

const TARO: Author = {
  id: "9f1c2b7e-3a4d-4e5f-8a6b-7c8d9e0f1a2b",
  display_name: "taro_dev",
  avatar_url: null,
};

/** ユーザー(id → 投稿者の情報と参加日) */
export const mockUsers = new Map<string, Author & { created_at: string }>(
  [
    { ...MOCK_ME, created_at: "2026-09-28T01:00:00Z" },
    { ...HANAKO, created_at: "2026-09-10T03:00:00Z" },
    { ...TARO, created_at: "2026-08-01T09:00:00Z" },
  ].map((user) => [user.id, user]),
);

const minutesAgo = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString();

/** タイムラインの初期データ(新しい順) */
export const mockPosts: Post[] = [
  {
    id: 12,
    content: "今日のランチ。オムライスにケチャップで猫を描いたら、ただの事件現場になった",
    image_url: "/mock/lunch.svg",
    created_at: minutesAgo(3),
    author: HANAKO,
    like_count: 2,
    liked_by_me: true,
  },
  {
    id: 11,
    content: "FastAPI で JWT の検証ができた!\naud と iss のチェックを忘れがちなので要注意",
    image_url: null,
    created_at: minutesAgo(48),
    author: MOCK_ME,
    like_count: 5,
    liked_by_me: false,
  },
  {
    id: 10,
    content: "夕焼けがきれいだったので。",
    image_url: "/mock/sunset.svg",
    created_at: minutesAgo(60 * 5),
    author: TARO,
    like_count: 0,
    liked_by_me: false,
  },
  {
    id: 9,
    content: "うちの猫、キーボードの上で寝るのやめてほしい。コミットメッセージが「ggggggggg」になった",
    image_url: "/mock/cat.svg",
    created_at: minutesAgo(60 * 26),
    author: HANAKO,
    like_count: 12,
    liked_by_me: true,
  },
  {
    id: 8,
    content: "おはようございます。今日も一日がんばりましょう",
    image_url: null,
    created_at: minutesAgo(60 * 24 * 3),
    author: TARO,
    like_count: 1,
    liked_by_me: false,
  },
];

/** いいねの数のうち、自分以外の分(投稿 id → 数) */
export const mockOthersLikeCount = new Map<number, number>(
  mockPosts.map((post) => [post.id, post.like_count - (post.liked_by_me ? 1 : 0)]),
);

/** AI チャットの履歴(セッション id → メッセージ)。過去の会話を 2 つ入れておく */
export const mockChatSessions = new Map<string, ChatMessage[]>([
  [
    "mock-session-1",
    [
      { id: 1, role: "user", content: "FastAPI と Django、どっちがいい?", post_id: null, created_at: minutesAgo(60 * 20) },
      {
        id: 2,
        role: "assistant",
        content: "それ聞く?API だけなら FastAPI、管理画面まで欲しいなら Django。まず作りたいものを決めな",
        post_id: null,
        created_at: minutesAgo(60 * 20),
      },
    ],
  ],
  [
    "mock-session-2",
    [
      { id: 3, role: "user", content: "週末なにしよう", post_id: null, created_at: minutesAgo(60 * 24 * 2) },
      {
        id: 4,
        role: "assistant",
        content: "知らん。けど、天気がいいなら散歩。悪いなら積んでる本を 1 冊崩そう",
        post_id: null,
        created_at: minutesAgo(60 * 24 * 2),
      },
    ],
  ],
]);

let nextId = 100;
/** ダミーの id を振る */
export const newId = () => nextId++;

/** 通信している「ふり」をするための待ち時間 */
export const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * URL に ?mock_error=1 を付けると、ダミーの API がエラーを返す(エラー表示の確認用)。
 */
export function shouldMockFail(): boolean {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("mock_error") === "1";
}
