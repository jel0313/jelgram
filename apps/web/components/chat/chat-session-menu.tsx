"use client";

import { CheckIcon, HistoryIcon, Loader2Icon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { PhaseBadge } from "@/components/common/phase-badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { getChatSessions } from "@/lib/api/chat";
import { errorMessage } from "@/lib/api/errors";
import type { ChatSession } from "@/lib/api/types";
import { formatRelativeTime } from "@/lib/format";

import { useChat } from "./chat-provider";

/** 過去の会話の一覧と切り替え(5次) */
export function ChatSessionMenu() {
  const { sessionId, switchSession } = useChat();
  const [sessions, setSessions] = useState<ChatSession[] | null>(null);

  // 開くたびに最新の一覧を読み込む
  const handleOpenChange = (open: boolean) => {
    if (!open) return;
    setSessions(null);
    getChatSessions()
      .then(setSessions)
      .catch((error) => {
        toast.error(errorMessage(error));
        setSessions([]);
      });
  };

  return (
    <DropdownMenu onOpenChange={handleOpenChange}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label="会話の履歴">
          <HistoryIcon />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72">
        <DropdownMenuLabel className="flex items-center gap-2">
          会話の履歴
          <PhaseBadge phase="5次" />
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {sessions === null ? (
          <div className="flex justify-center py-4">
            <Loader2Icon className="size-4 animate-spin text-muted-foreground" />
          </div>
        ) : sessions.length === 0 ? (
          <p className="px-2 py-4 text-center text-sm text-muted-foreground">まだ会話がありません</p>
        ) : (
          sessions.map((session) => (
            <DropdownMenuItem key={session.session_id} onClick={() => switchSession(session.session_id)}>
              <span className="min-w-0 flex-1">
                <span className="block truncate">{session.title}</span>
                <span className="block text-xs text-muted-foreground">
                  {formatRelativeTime(session.last_message_at)}
                </span>
              </span>
              {session.session_id === sessionId && <CheckIcon className="text-violet-600" />}
            </DropdownMenuItem>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
