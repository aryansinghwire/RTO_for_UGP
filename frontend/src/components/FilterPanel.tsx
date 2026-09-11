import type { OrderFilters } from "../api/types";

// Fixed, known bucket taxonomies from the Layer 1 export (anonymized letter
// buckets - see serving/export_seed.py). Not real country/category names.
const COUNTRY_BUCKETS = ["Country_A", "Country_B", "Country_C", "Country_D", "Country_E",
  "Country_F", "Country_G", "Country_H", "Country_I"];
const PRODUCT_TYPE_BUCKETS = ["productType_A", "productType_B", "productType_C", "productType_D",
  "productType_E", "productType_F", "productType_G", "productType_H", "productType_I",
  "productType_J", "productType_K"];

interface Props {
  filters: OrderFilters;
  onChange: (next: OrderFilters) => void;
}

export default function FilterPanel({ filters, onChange }: Props) {
  function set<K extends keyof OrderFilters>(key: K, value: OrderFilters[K]) {
    onChange({ ...filters, [key]: value, page: 1 });
  }

  return (
    <div className="flex flex-wrap items-end gap-3 border-b border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-950">
      <div>
        <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Status</label>
        <select
          value={filters.status ?? ""}
          onChange={(e) => set("status", (e.target.value || undefined) as OrderFilters["status"])}
          className="mt-1 rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        >
          <option value="">Any</option>
          <option value="pending">Pending</option>
          <option value="overridden">Overridden</option>
          <option value="actioned">Actioned</option>
          <option value="closed">Closed</option>
        </select>
      </div>

      <div>
        <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Min score</label>
        <input
          type="number"
          min={0}
          max={1}
          step={0.05}
          value={filters.min_score ?? ""}
          onChange={(e) => set("min_score", e.target.value ? Number(e.target.value) : undefined)}
          className="mt-1 w-20 rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Max score</label>
        <input
          type="number"
          min={0}
          max={1}
          step={0.05}
          value={filters.max_score ?? ""}
          onChange={(e) => set("max_score", e.target.value ? Number(e.target.value) : undefined)}
          className="mt-1 w-20 rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Country bucket</label>
        <select
          value={filters.country ?? ""}
          onChange={(e) => set("country", e.target.value || undefined)}
          className="mt-1 rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        >
          <option value="">Any</option>
          {COUNTRY_BUCKETS.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Product type</label>
        <select
          value={filters.product_type ?? ""}
          onChange={(e) => set("product_type", e.target.value || undefined)}
          className="mt-1 rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        >
          <option value="">Any</option>
          {PRODUCT_TYPE_BUCKETS.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Cold-start</label>
        <select
          value={filters.cold_start === undefined ? "" : String(filters.cold_start)}
          onChange={(e) =>
            set("cold_start", e.target.value === "" ? undefined : e.target.value === "true")
          }
          className="mt-1 rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        >
          <option value="">Any</option>
          <option value="true">Cold-start only</option>
          <option value="false">Warm only</option>
        </select>
      </div>

      <div>
        <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Sort</label>
        <select
          value={filters.sort ?? "-score"}
          onChange={(e) => set("sort", e.target.value as OrderFilters["sort"])}
          className="mt-1 rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        >
          <option value="-score">Risk score (high to low)</option>
          <option value="score">Risk score (low to high)</option>
          <option value="-date">Date (newest)</option>
          <option value="date">Date (oldest)</option>
        </select>
      </div>

      <button
        type="button"
        onClick={() => onChange({ sort: "-score", page: 1, page_size: filters.page_size })}
        className="rounded border border-neutral-300 px-3 py-1 text-sm text-neutral-600 hover:bg-neutral-100 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
      >
        Clear filters
      </button>
    </div>
  );
}
