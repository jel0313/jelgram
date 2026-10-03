import { RotateCwIcon, TriangleAlertIcon } from "lucide-react";

import { Button } from "@/components/ui/button";

type Props = {
  message: string;
  onRetry?: () => void;
};

/** 読み込みに失敗したときの表示(再読み込みボタン付き) */
export function ErrorState({ message, onRetry }: Props) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      <TriangleAlertIcon className="size-8 text-destructive" />
      <p className="text-sm text-muted-foreground">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCwIcon />
          もう一度読み込む
        </Button>
      )}
    </div>
  );
}
