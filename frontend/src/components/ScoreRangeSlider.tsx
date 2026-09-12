import { useId } from "react";

/**
 * Dual-thumb window selector for a risk-score range.
 *
 * Built from two stacked native range inputs rather than a library: the pair
 * keeps full keyboard support and needs no dependency. The tracks are
 * transparent and `pointer-events: none`, so only the thumbs are clickable and
 * the two inputs don't steal drags from each other; the visible track and the
 * highlighted window are drawn underneath.
 */
export default function ScoreRangeSlider({
  min,
  max,
  onChange,
  disabled = false,
  label = "Score window",
}: {
  min: number;
  max: number;
  onChange: (next: { min: number; max: number }) => void;
  disabled?: boolean;
  label?: string;
}) {
  const id = useId();
  const pct = (v: number) => `${Math.round(v * 100)}%`;

  return (
    <div className="w-64">
      <div className="flex items-baseline justify-between">
        <label htmlFor={`${id}-min`} className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
          {label}
        </label>
        <span className="font-mono text-xs tabular-nums text-neutral-700 dark:text-neutral-300">
          {min.toFixed(2)} – {max.toFixed(2)}
        </span>
      </div>

      <div className={`relative mt-3 h-5 ${disabled ? "opacity-40" : ""}`}>
        {/* full track */}
        <div className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-neutral-200 dark:bg-neutral-700" />
        {/* the selected window */}
        <div
          className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-teal-600 dark:bg-teal-400"
          style={{ left: pct(min), right: `${Math.round((1 - max) * 100)}%` }}
        />
        <input
          id={`${id}-min`}
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={min}
          disabled={disabled}
          aria-label={`${label} lower bound`}
          onChange={(e) => onChange({ min: Math.min(Number(e.target.value), max), max })}
          className="range-thumb absolute inset-x-0 top-0 h-5 w-full"
        />
        <input
          id={`${id}-max`}
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={max}
          disabled={disabled}
          aria-label={`${label} upper bound`}
          onChange={(e) => onChange({ min, max: Math.max(Number(e.target.value), min) })}
          className="range-thumb absolute inset-x-0 top-0 h-5 w-full"
        />
      </div>

      <div className="mt-1 flex justify-between text-[10px] text-neutral-400">
        <span>0.00 lower risk</span>
        <span>higher risk 1.00</span>
      </div>
    </div>
  );
}
