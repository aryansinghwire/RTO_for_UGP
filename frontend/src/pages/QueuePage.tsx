import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useOrders } from "../api/hooks";
import type { OrderFilters } from "../api/types";
import FilterPanel from "../components/FilterPanel";
import OrdersTable from "../components/OrdersTable";

export default function QueuePage() {
  const [searchParams] = useSearchParams();
  const [filters, setFilters] = useState<OrderFilters>(() => ({
    sort: "-score",
    page: 1,
    page_size: 25,
    country: searchParams.get("country") ?? undefined,
    product_type: searchParams.get("product_type") ?? undefined,
  }));

  const { data, isLoading } = useOrders(filters);

  const activeFilterCount = useMemo(
    () => Object.entries(filters).filter(([k, v]) => v !== undefined && k !== "sort" && k !== "page" && k !== "page_size").length,
    [filters],
  );

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-4 py-3">
        <h2 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">Risk queue</h2>
        {activeFilterCount > 0 && (
          <span className="text-xs text-neutral-500 dark:text-neutral-400">{activeFilterCount} filter(s) active</span>
        )}
      </div>
      <FilterPanel filters={filters} onChange={setFilters} />
      <OrdersTable data={data} isLoading={isLoading} onPageChange={(page) => setFilters((f) => ({ ...f, page }))} />
    </div>
  );
}
