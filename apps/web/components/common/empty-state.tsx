type Props = {
  icon: React.ReactNode;
  title: string;
  description?: string;
};

/** 表示するものがないときの表示 */
export function EmptyState({ icon, title, description }: Props) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-16 text-center">
      <div className="flex size-16 items-center justify-center rounded-full border-2 border-foreground/80 text-foreground/80 [&_svg]:size-7 [&_svg]:stroke-[1.5]">
        {icon}
      </div>
      <p className="text-lg font-bold">{title}</p>
      {description && <p className="text-sm text-muted-foreground">{description}</p>}
    </div>
  );
}
