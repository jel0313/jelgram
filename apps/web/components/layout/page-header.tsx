"use client";

import { ArrowLeftIcon } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Props = {
  title: string;
  /** 戻るボタンを出す(詳細などの画面) */
  back?: boolean;
  children?: React.ReactNode;
};

/** 中央の列の上部に固定する見出し */
export function PageHeader({ title, back = false, children }: Props) {
  const router = useRouter();

  return (
    <div
      className={cn(
        "sticky top-0 z-20 items-center gap-2 border-b bg-background/90 px-4 py-2 backdrop-blur md:flex md:min-h-13",
        back ? "flex" : "hidden",
      )}
    >
      {back && (
        <Button
          variant="ghost"
          size="icon-sm"
          className="-ml-1"
          aria-label="戻る"
          onClick={() => (window.history.length > 1 ? router.back() : router.push("/"))}
        >
          <ArrowLeftIcon />
        </Button>
      )}
      <h1 className="text-lg font-bold">{title}</h1>
      {children}
    </div>
  );
}
