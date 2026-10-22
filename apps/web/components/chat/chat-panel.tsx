"use client";

import { ArrowUpIcon, FileTextIcon, SparklesIcon, SquarePenIcon, XIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { ChatMessage } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { CHAT_INPUT_ID, useChat } from "./chat-provider";
import { ChatSessionMenu } from "./chat-session-menu";

/** AI チャット(PC では右の列、スマホでは下から出るパネルの中身) */
export function ChatPanel({ className }: { className?: string }) {
  const { messages, loadingHistory, sending, rateLimitMessage, newSession } = useChat();
  const scrollRef = useRef<HTMLDivElement>(null);

  // 新しいメッセージが来たら、チャットの中だけを一番下までスクロールする(ページ全体は動かさない)
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages, sending, rateLimitMessage]);

  return (
    <div className={cn("flex h-full min-h-0 flex-col bg-card", className)}>
      <header className="flex items-center justify-between gap-2 border-b border-border/60 px-4 py-3">
        <div className="flex items-center gap-3">
          <AiAvatar className="size-9" />
          <div className="leading-tight">
            <h2 className="text-[15px] font-semibold">AI チャット</h2>
            <p className="flex items-center gap-1 text-xs text-muted-foreground">
              <span className="size-1.5 rounded-full bg-emerald-500" />
              いつでも話せる
            </p>
          </div>
        </div>
        <div className="flex items-center">
          <ChatSessionMenu />
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" className="rounded-full" onClick={newSession} aria-label="新しい会話">
                <SquarePenIcon className="size-4.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>新しい会話</TooltipContent>
          </Tooltip>
        </div>
      </header>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-5">
        {loadingHistory ? (
          <div className="space-y-3">
            <Skeleton className="h-12 w-3/4 rounded-2xl" />
            <Skeleton className="ml-auto h-9 w-1/2 rounded-2xl" />
          </div>
        ) : (
          <div className="space-y-4">
            {messages.length === 0 && (
              <AssistantBubble content="で、何の用?投稿について聞きたいなら、投稿の「この投稿について AI に聞く」から呼んで。" />
            )}
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {sending && <TypingBubble />}
            {rateLimitMessage && (
              <p className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">
                {rateLimitMessage}
              </p>
            )}
          </div>
        )}
      </div>

      <ChatInput />
    </div>
  );
}

/** AI のアイコン(ブランドのグラデーション) */
function AiAvatar({ className }: { className?: string }) {
  return (
    <span className={cn("bg-brand flex size-7 shrink-0 items-center justify-center rounded-full text-white", className)}>
      <SparklesIcon className="size-[45%]" />
    </span>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const { postSnippets } = useChat();
  if (message.role === "assistant") return <AssistantBubble content={message.content} />;

  const snippet = message.post_id !== null ? postSnippets[message.post_id] : undefined;
  return (
    <div className="ml-auto flex max-w-[85%] flex-col items-end gap-1.5">
      {message.post_id !== null && (
        <span className="flex max-w-full items-center gap-1 rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">
          <FileTextIcon className="size-3 shrink-0" />
          <span className="truncate">{snippet ? `「${snippet}」について` : "投稿について"}</span>
        </span>
      )}
      <p className="bg-brand rounded-3xl rounded-br-md px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap text-white">
        {message.content}
      </p>
    </div>
  );
}

function AssistantBubble({ content }: { content: string }) {
  return (
    <div className="flex max-w-[90%] items-end gap-2">
      <AiAvatar />
      <p className="rounded-3xl rounded-bl-md bg-muted px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap">
        {content}
      </p>
    </div>
  );
}

/** AI の応答を待っている間の「…」 */
function TypingBubble() {
  return (
    <div className="flex items-end gap-2" role="status" aria-label="考え中">
      <AiAvatar />
      <span className="flex items-center gap-1 rounded-3xl rounded-bl-md bg-muted px-4 py-3.5">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="animate-typing-dot size-1.5 rounded-full bg-foreground/60"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </span>
    </div>
  );
}

function ChatInput() {
  const { sending, send, contextPost, clearContext } = useChat();
  const [text, setText] = useState("");
  const canSend = text.trim().length > 0 && !sending;

  const submit = async () => {
    if (!canSend) return;
    const message = text.trim();
    setText("");
    const ok = await send(message);
    if (!ok) setText(message); // 失敗したら、入力した文を戻す
  };

  return (
    <div className="space-y-2 p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
      {contextPost && (
        <div className="flex items-center gap-2 rounded-2xl border border-border/70 bg-muted/60 px-3 py-2 text-xs">
          <FileTextIcon className="size-3.5 shrink-0 text-(--brand-via)" />
          <span className="min-w-0 flex-1 truncate">
            <span className="font-semibold">この投稿について:</span>
            {contextPost.content}
          </span>
          <button
            type="button"
            onClick={clearContext}
            className="rounded-full p-0.5 text-muted-foreground transition-colors hover:bg-background hover:text-foreground"
            aria-label="投稿の指定をやめる"
          >
            <XIcon className="size-3.5" />
          </button>
        </div>
      )}
      <form
        className="flex items-end gap-2 rounded-3xl border border-border/80 bg-background py-1 pr-1 pl-4 transition-colors focus-within:border-foreground/30"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <Textarea
          id={CHAT_INPUT_ID}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            // Enter で送信、Shift + Enter で改行(日本語の変換中は送らない)
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              void submit();
            }
          }}
          placeholder={contextPost ? "この投稿について聞く…" : "AI に話しかける…"}
          rows={1}
          aria-label="AI へのメッセージ"
          className="max-h-32 min-h-9 resize-none rounded-none border-none bg-transparent px-0 py-2 text-sm shadow-none focus-visible:ring-0 md:text-sm dark:bg-transparent"
        />
        <Button
          type="submit"
          size="icon"
          disabled={!canSend}
          aria-label="送信"
          className="bg-brand mb-0.5 size-8 rounded-full text-white disabled:bg-none disabled:bg-muted disabled:text-muted-foreground disabled:opacity-100"
        >
          <ArrowUpIcon className="size-4.5" strokeWidth={2.5} />
        </Button>
      </form>
    </div>
  );
}
