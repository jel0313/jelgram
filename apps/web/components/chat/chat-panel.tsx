"use client";

import { BotIcon, FileTextIcon, Loader2Icon, SendIcon, SquarePenIcon, XIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { ChatMessage } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { useChat } from "./chat-provider";
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
    <div className={cn("flex h-full min-h-0 flex-col", className)}>
      <header className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <BotIcon className="size-5 text-violet-500" />
          <h2 className="font-semibold">AI チャット</h2>
        </div>
        <div className="flex items-center gap-1">
          <ChatSessionMenu />
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon-sm" onClick={newSession} aria-label="新しい会話">
                <SquarePenIcon />
              </Button>
            </TooltipTrigger>
            <TooltipContent>新しい会話</TooltipContent>
          </Tooltip>
        </div>
      </header>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {loadingHistory ? (
          <div className="space-y-3">
            <Skeleton className="h-12 w-3/4" />
            <Skeleton className="ml-auto h-8 w-1/2" />
          </div>
        ) : (
          <div className="space-y-3">
            {messages.length === 0 && (
              <AssistantBubble content="で、何の用?投稿について聞きたいなら、投稿の「この投稿について」から呼んで。" />
            )}
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {sending && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2Icon className="size-4 animate-spin" />
                考え中…
              </div>
            )}
            {rateLimitMessage && (
              <Alert className="border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">
                <AlertDescription className="text-inherit">{rateLimitMessage}</AlertDescription>
              </Alert>
            )}
          </div>
        )}
      </div>

      <ChatInput />
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const { postSnippets } = useChat();
  if (message.role === "assistant") return <AssistantBubble content={message.content} />;

  const snippet = message.post_id !== null ? postSnippets[message.post_id] : undefined;
  return (
    <div className="ml-auto flex max-w-[85%] flex-col items-end gap-1">
      {message.post_id !== null && (
        <span className="flex max-w-full items-center gap-1 text-xs text-muted-foreground">
          <FileTextIcon className="size-3 shrink-0" />
          <span className="truncate">{snippet ? `「${snippet}」について` : "投稿について"}</span>
        </span>
      )}
      <p className="rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-sm whitespace-pre-wrap text-primary-foreground">
        {message.content}
      </p>
    </div>
  );
}

function AssistantBubble({ content }: { content: string }) {
  return (
    <div className="flex max-w-[90%] items-start gap-2">
      <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-violet-100 text-violet-600 dark:bg-violet-950 dark:text-violet-300">
        <BotIcon className="size-4" />
      </div>
      <p className="rounded-2xl rounded-tl-sm bg-muted px-3 py-2 text-sm whitespace-pre-wrap">{content}</p>
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
    <div className="space-y-2 border-t p-3">
      {contextPost && (
        <div className="flex items-center gap-2 rounded-lg bg-muted px-3 py-2 text-xs">
          <FileTextIcon className="size-3.5 shrink-0 text-muted-foreground" />
          <span className="min-w-0 flex-1 truncate">
            <span className="text-muted-foreground">この投稿について:</span>
            {contextPost.content}
          </span>
          <button
            type="button"
            onClick={clearContext}
            className="text-muted-foreground hover:text-foreground"
            aria-label="投稿の指定をやめる"
          >
            <XIcon className="size-3.5" />
          </button>
        </div>
      )}
      <form
        className="flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            // Enter で送信、Shift + Enter で改行(日本語の変換中は送らない)
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              void submit();
            }
          }}
          placeholder={contextPost ? "この投稿について聞く" : "AI に話しかける"}
          rows={1}
          className="max-h-32 min-h-9 resize-none"
        />
        <Button type="submit" size="icon" disabled={!canSend} aria-label="送信">
          <SendIcon />
        </Button>
      </form>
    </div>
  );
}
