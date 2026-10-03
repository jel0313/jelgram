type Props = {
  icon: React.ReactNode;
  title: string;
  description?: string;
};

/** 表示するものがないときの表示 */
export function EmptyState({ icon, title, description }: Props) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-12 text-center">
      <div className="text-muted-foreground [&_svg]:size-8">{icon}</div>
      <p className="font-medium">{title}</p>
      {description && <p className="text-sm text-muted-foreground">{description}</p>}
    </div>
  );
}
