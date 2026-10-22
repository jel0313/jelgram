import { RotateCwIcon, WifiOffIcon } from "lucide-react";

import { Button } from "@/components/ui/button";

type Props = {
  message: string;
  onRetry?: () => void;
};

/** 読み込みに失敗したときの表示(再読み込みボタン付き) */
export function ErrorState({ message, onRetry }: Props) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-16 text-center">
      <div className="flex size-14 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <WifiOffIcon className="size-6" />
      </div>
      <p className="max-w-xs text-sm text-muted-foreground">{message}</p>
      {onRetry && (
        <Button variant="outline" className="rounded-full px-4" onClick={onRetry}>
          <RotateCwIcon />
          もう一度読み込む
        </Button>
      )}
    </div>
  );
}
