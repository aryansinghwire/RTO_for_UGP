function tier(score: number): { label: string; classes: string } {
  if (score >= 0.7) return { label: "High", classes: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300" };
  if (score >= 0.4) return { label: "Medium", classes: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300" };
  return { label: "Low", classes: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300" };
}

export default function ScoreBadge({ score, size = "md" }: { score: number; size?: "sm" | "md" }) {
  const { label, classes } = tier(score);
  const padding = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-medium ${padding} ${classes}`}>
      <span className="tabular-nums">{score.toFixed(2)}</span>
      <span className="opacity-70">{label}</span>
    </span>
  );
}
