"use client";

import { ChevronLeftIcon } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";

type Props = {
  title: string;
  /** 戻るボタンを出す(詳細などの画面) */
  back?: boolean;
  children?: React.ReactNode;
};

/** 中央の列の上部に固定する見出し(スマホは上のバーの下に付く) */
export function PageHeader({ title, back = false, children }: Props) {
  const router = useRouter();

  return (
    <div className="sticky top-14 z-20 flex h-12 items-center gap-2 bg-background/80 px-2 backdrop-blur-xl md:top-0 md:h-14 md:px-0">
      {back && (
        <Button
          variant="ghost"
          size="icon"
          className="rounded-full"
          aria-label="戻る"
          onClick={() => (window.history.length > 1 ? router.back() : router.push("/"))}
        >
          <ChevronLeftIcon className="size-6" />
        </Button>
      )}
      <h1 className="truncate text-base font-bold md:text-lg">{title}</h1>
      {children}
    </div>
  );
}
