"use client";

import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

/** 投稿の画像。押すと大きく表示する */
export function ImageViewer({ src, className }: { src: string; className?: string }) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <button type="button" className="block w-full cursor-zoom-in" aria-label="画像を大きく表示">
          {/* 画像は Supabase Storage の URL(外部)なので、next/image ではなく img で表示する */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt="" className={className} />
        </button>
      </DialogTrigger>
      <DialogContent className="max-w-[min(95vw,1200px)] border-none bg-transparent p-0 shadow-none sm:max-w-[min(95vw,1200px)]">
        <DialogTitle className="sr-only">画像</DialogTitle>
        <DialogDescription className="sr-only">投稿の画像を大きく表示しています</DialogDescription>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={src} alt="" className="max-h-[90dvh] w-full rounded-lg object-contain" />
      </DialogContent>
    </Dialog>
  );
}
