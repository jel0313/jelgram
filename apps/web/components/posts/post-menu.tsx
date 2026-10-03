"use client";

import { Loader2Icon, MoreHorizontalIcon, PencilIcon, Trash2Icon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { PhaseBadge } from "@/components/common/phase-badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/lib/api/errors";
import { deletePost, updatePost } from "@/lib/api/posts";
import type { Post } from "@/lib/api/types";
import { CONTENT_MAX_LENGTH } from "@/lib/constants";

type Props = {
  post: Post;
  onUpdated: (post: Post) => void;
  onDeleted: (postId: number) => void;
};

/** 自分の投稿の「…」メニュー(編集・削除。2次) */
export function PostMenu({ post, onUpdated, onDeleted }: Props) {
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" className="text-muted-foreground" aria-label="投稿のメニュー">
            <MoreHorizontalIcon />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => setEditing(true)}>
            <PencilIcon />
            編集
            <PhaseBadge phase="2次" className="ml-auto" />
          </DropdownMenuItem>
          <DropdownMenuItem variant="destructive" onClick={() => setDeleting(true)}>
            <Trash2Icon />
            削除
            <PhaseBadge phase="2次" className="ml-auto" />
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      {editing && <EditDialog post={post} onClose={() => setEditing(false)} onUpdated={onUpdated} />}
      <DeleteDialog post={post} open={deleting} onOpenChange={setDeleting} onDeleted={onDeleted} />
    </>
  );
}

function EditDialog({
  post,
  onClose,
  onUpdated,
}: {
  post: Post;
  onClose: () => void;
  onUpdated: (post: Post) => void;
}) {
  const [content, setContent] = useState(post.content);
  const [saving, setSaving] = useState(false);
  const length = content.trim().length;
  const canSave = length > 0 && length <= CONTENT_MAX_LENGTH && content.trim() !== post.content && !saving;

  const save = async () => {
    setSaving(true);
    try {
      onUpdated(await updatePost(post.id, { content: content.trim() }));
      toast.success("投稿を編集しました");
      onClose();
    } catch (error) {
      toast.error(errorMessage(error));
      setSaving(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>投稿を編集</DialogTitle>
          <DialogDescription>画像は変更できません</DialogDescription>
        </DialogHeader>
        <Textarea value={content} onChange={(e) => setContent(e.target.value)} rows={5} className="resize-none" />
        <p className="text-right text-xs text-muted-foreground tabular-nums">
          {length} / {CONTENT_MAX_LENGTH}
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            キャンセル
          </Button>
          <Button onClick={save} disabled={!canSave}>
            {saving && <Loader2Icon className="animate-spin" />}
            保存する
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DeleteDialog({
  post,
  open,
  onOpenChange,
  onDeleted,
}: {
  post: Post;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDeleted: (postId: number) => void;
}) {
  const [pending, setPending] = useState(false);

  const remove = async () => {
    setPending(true);
    try {
      await deletePost(post.id);
      onOpenChange(false);
      onDeleted(post.id);
      toast.success("投稿を削除しました");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setPending(false);
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>投稿を削除しますか?</AlertDialogTitle>
          <AlertDialogDescription>削除すると元に戻せません。いいねも一緒に消えます。</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>キャンセル</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            onClick={(e) => {
              e.preventDefault(); // 削除が終わるまでダイアログを閉じない
              void remove();
            }}
            disabled={pending}
          >
            {pending && <Loader2Icon className="animate-spin" />}
            削除する
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
