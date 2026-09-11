export default function ColdStartBadge({
  customerNoHistory,
  productNoHistory,
}: {
  customerNoHistory: boolean;
  productNoHistory: boolean;
}) {
  if (!customerNoHistory && !productNoHistory) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {customerNoHistory && (
        <span className="rounded border border-sky-300 bg-sky-50 px-1.5 py-0.5 text-xs text-sky-700 dark:border-sky-800 dark:bg-sky-950 dark:text-sky-300">
          New customer
        </span>
      )}
      {productNoHistory && (
        <span className="rounded border border-violet-300 bg-violet-50 px-1.5 py-0.5 text-xs text-violet-700 dark:border-violet-800 dark:bg-violet-950 dark:text-violet-300">
          New product
        </span>
      )}
    </div>
  );
}
