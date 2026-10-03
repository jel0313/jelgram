"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { toast } from "sonner";

import { getChatHistory, sendChatMessage } from "@/lib/api/chat";
import { errorMessage, RateLimitError } from "@/lib/api/errors";
import type { ChatMessage, Post } from "@/lib/api/types";

const SESSION_KEY = "jelgram-chat-session";

type ChatState = {
  messages: ChatMessage[];
  /** 履歴を読み込み中か */
  loadingHistory: boolean;
  /** AI の応答を待っているか */
  sending: boolean;
  /** レート制限を超えたときのメッセージ */
  rateLimitMessage: string | null;
  /** 「この投稿について」で選んだ投稿 */
  contextPost: Post | null;
  /** 投稿 id → 本文(メッセージに「どの投稿の話か」を出すため) */
  postSnippets: Record<number, string>;
  /** スマホでチャットの画面を開いているか */
  mobileOpen: boolean;
  setMobileOpen: (open: boolean) => void;
  /** メッセージを送る。失敗したら false */
  send: (message: string) => Promise<boolean>;
  /** 新しい会話を始める */
  newSession: () => void;
  /** 今の会話のセッション id */
  sessionId: string;
  /** 過去の会話に切り替える(5次) */
  switchSession: (sessionId: string) => void;
  /** 投稿についてチャットで聞く */
  askAbout: (post: Post) => void;
  clearContext: () => void;
};

const ChatContext = createContext<ChatState | null>(null);

/** 前回の会話のセッション id(なければ新しく作る)。ブラウザに保存しておく */
function loadSessionId(): string {
  let id = window.localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

/** ログイン後にだけ表示する(ブラウザの中でだけ動く)ので、localStorage を直接読んでよい */
export function ChatProvider({ children }: { children: React.ReactNode }) {
  const [sessionId, setSessionId] = useState<string>(loadSessionId);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [sending, setSending] = useState(false);
  const [rateLimitMessage, setRateLimitMessage] = useState<string | null>(null);
  const [contextPost, setContextPost] = useState<Post | null>(null);
  const [postSnippets, setPostSnippets] = useState<Record<number, string>>({});
  const [mobileOpen, setMobileOpen] = useState(false);

  // 最初の表示で、前回の会話の履歴を読み込む
  useEffect(() => {
    getChatHistory(sessionId)
      .then(setMessages)
      .catch((error) => toast.error(errorMessage(error)))
      .finally(() => setLoadingHistory(false));
    // 「新しい会話」では履歴を読まない(空から始める)ので、最初の 1 回だけ
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const send = useCallback(
    async (message: string) => {
      const postId = contextPost?.id ?? null;
      const tempMessage: ChatMessage = {
        id: -Date.now(),
        role: "user",
        content: message,
        post_id: postId,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, tempMessage]);
      setRateLimitMessage(null);
      setSending(true);
      try {
        const { reply } = await sendChatMessage({ message, session_id: sessionId, post_id: postId });
        setMessages((prev) => [...prev, reply]);
        setContextPost(null);
        return true;
      } catch (error) {
        setMessages((prev) => prev.filter((m) => m.id !== tempMessage.id));
        if (error instanceof RateLimitError) {
          setRateLimitMessage(error.detail);
        } else {
          toast.error(errorMessage(error));
        }
        return false;
      } finally {
        setSending(false);
      }
    },
    [sessionId, contextPost],
  );

  const newSession = useCallback(() => {
    const id = crypto.randomUUID();
    window.localStorage.setItem(SESSION_KEY, id);
    setSessionId(id);
    setMessages([]);
    setRateLimitMessage(null);
    setContextPost(null);
  }, []);

  const switchSession = useCallback((id: string) => {
    window.localStorage.setItem(SESSION_KEY, id);
    setSessionId(id);
    setRateLimitMessage(null);
    setContextPost(null);
    setLoadingHistory(true);
    getChatHistory(id)
      .then(setMessages)
      .catch((error) => toast.error(errorMessage(error)))
      .finally(() => setLoadingHistory(false));
  }, []);

  const askAbout = useCallback((post: Post) => {
    setContextPost(post);
    setPostSnippets((prev) => ({ ...prev, [post.id]: post.content }));
    // PC(lg 以上)では右の列にチャットが常にあるので、スマホ用のパネルは開かない
    if (!window.matchMedia("(min-width: 1024px)").matches) setMobileOpen(true);
  }, []);

  const clearContext = useCallback(() => setContextPost(null), []);

  return (
    <ChatContext
      value={{
        messages,
        loadingHistory,
        sending,
        rateLimitMessage,
        contextPost,
        postSnippets,
        mobileOpen,
        setMobileOpen,
        send,
        newSession,
        sessionId,
        switchSession,
        askAbout,
        clearContext,
      }}
    >
      {children}
    </ChatContext>
  );
}

export function useChat(): ChatState {
  const state = useContext(ChatContext);
  if (!state) throw new Error("useChat は ChatProvider の中で使う");
  return state;
}
