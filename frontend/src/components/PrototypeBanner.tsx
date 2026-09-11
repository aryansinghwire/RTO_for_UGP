import { useState } from "react";
import { useMeta } from "../api/hooks";

const DISMISS_KEY = "rto-dashboard.banner-dismissed";

export default function PrototypeBanner() {
  const { data: meta } = useMeta();
  const [dismissed, setDismissed] = useState(() => sessionStorage.getItem(DISMISS_KEY) === "1");

  if (dismissed || !meta) return null;

  return (
    <div className="flex items-start gap-3 border-b border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
      <span className="mt-0.5 shrink-0 rounded bg-amber-200 px-1.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-amber-900 dark:bg-amber-800 dark:text-amber-100">
        Prototype
      </span>
      <p className="flex-1">{meta.notice}</p>
      <button
        type="button"
        onClick={() => {
          sessionStorage.setItem(DISMISS_KEY, "1");
          setDismissed(true);
        }}
        className="shrink-0 text-amber-700 hover:text-amber-900 dark:text-amber-400 dark:hover:text-amber-200"
        aria-label="Dismiss"
      >
        ✕
      </button>
    </div>
  );
}
