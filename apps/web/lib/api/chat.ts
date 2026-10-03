// AI チャット。いまはダミー実装(画面接続で、本物の API 呼び出しに置き換える)。

import { RateLimitError } from "./errors";
import { mockChatSessions, mockPosts, newId, sleep } from "./mock-data";
import type { ChatMessage, ChatRequest, ChatResponse, ChatSession } from "./types";

/** 会話履歴(古い順) */
export async function getChatHistory(sessionId: string): Promise<ChatMessage[]> {
  await sleep(300);
  return structuredClone(mockChatSessions.get(sessionId) ?? []);
}

/** AI に送って、応答を受け取る */
export async function sendChatMessage(body: ChatRequest): Promise<ChatResponse> {
  await sleep(1200);
  // ダミー:「/429」と送ると、レート制限を超えたときの表示を確認できる
  if (body.message.trim() === "/429") {
    throw new RateLimitError("ちょっと待て、話しすぎ。1 分くらい休憩してから、また話しかけて");
  }

  const history = mockChatSessions.get(body.session_id) ?? [];
  const now = new Date().toISOString();
  history.push({
    id: newId(),
    role: "user",
    content: body.message,
    post_id: body.post_id,
    created_at: now,
  });
  const reply: ChatMessage = {
    id: newId(),
    role: "assistant",
    content: dummyReply(body),
    post_id: body.post_id,
    created_at: now,
  };
  history.push(reply);
  mockChatSessions.set(body.session_id, history);
  return { reply: structuredClone(reply) };
}

const REPLIES = [
  "で、それ本気で聞いてる?まあいいや、答えるとね、まずは手を動かしてみるのが一番早い。分からなくなったらまた聞いて",
  "いい質問じゃん。ただ情報が少なすぎて、エスパーじゃないと無理。もうちょい具体的に教えて",
  "知らん。でも調べ方なら教えられる。公式ドキュメントの検索から始めてみ",
  "それ、3 回くらい同じこと悩んでない?一回紙に書き出すと、意外とスッキリするよ",
];

function dummyReply(body: ChatRequest): string {
  if (body.post_id !== null) {
    const post = mockPosts.find((p) => p.id === body.post_id);
    if (post) {
      const quote = post.content.length > 20 ? `${post.content.slice(0, 20)}…` : post.content;
      return `「${quote}」ね。ツッコミどころはあるけど、嫌いじゃない。こういう投稿は、写真が 1 枚あるだけで伸び方が変わるよ`;
    }
  }
  return REPLIES[Math.floor(Math.random() * REPLIES.length)];
}

/** 自分の会話の一覧(新しい順。5次) */
export async function getChatSessions(): Promise<ChatSession[]> {
  await sleep(300);
  return [...mockChatSessions.entries()]
    .filter(([, messages]) => messages.length > 0)
    .map(([sessionId, messages]) => ({
      session_id: sessionId,
      title: messages[0].content,
      last_message_at: messages[messages.length - 1].created_at,
    }))
    .sort((a, b) => b.last_message_at.localeCompare(a.last_message_at));
}
