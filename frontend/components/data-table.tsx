import { useMemo, useState, type ReactNode } from "react";

export type DataTableColumn<TData extends Record<string, unknown>> = {
  accessorKey: keyof TData | string;
  header: string;
  sortable?: boolean;
  cell?: (value: TData, row: TData) => ReactNode;
};

export type DataTableProps<TData extends Record<string, unknown>> = {
  ariaLabel: string;
  columns: DataTableColumn<TData>[];
  data: TData[];
  emptyState?: string;
  pageSize?: number;
  searchPlaceholder?: string;
};

type SortDirection = "asc" | "desc";

function getCellValue<TData extends Record<string, unknown>>(row: TData, accessorKey: keyof TData | string): string {
  const key = accessorKey.toString();
  const value = row[key as keyof TData];
  return value == null ? "" : String(value);
}

export default function DataTable<TData extends Record<string, unknown>>({
  ariaLabel,
  columns,
  data,
  emptyState = "No rows to display.",
  pageSize = 10,
  searchPlaceholder = "Filter rows",
}: DataTableProps<TData>) {
  const [sortState, setSortState] = useState<{ accessorKey: string; direction: SortDirection } | null>(null);
  const [globalFilter, setGlobalFilter] = useState("");
  const [pageIndex, setPageIndex] = useState(0);

  const filteredRows = useMemo(() => {
    const term = globalFilter.trim().toLowerCase();
    let rows = [...data];

    if (term) {
      rows = rows.filter((row) =>
        Object.keys(row).some((key) => getCellValue(row, key).toLowerCase().includes(term)),
      );
    }

    if (sortState) {
      rows = [...rows].sort((a, b) => {
        const aValue = getCellValue(a, sortState.accessorKey).toLowerCase();
        const bValue = getCellValue(b, sortState.accessorKey).toLowerCase();
        if (aValue < bValue) return sortState.direction === "asc" ? -1 : 1;
        if (aValue > bValue) return sortState.direction === "asc" ? 1 : -1;
        return 0;
      });
    }

    return rows;
  }, [data, globalFilter, sortState]);

  const totalPages = Math.max(Math.ceil(filteredRows.length / pageSize), 1);
  const start = pageIndex * pageSize;
  const currentPage = filteredRows.slice(start, start + pageSize);

  const toggleSort = (accessorKey: string): void => {
    setPageIndex(0);
    setSortState((current) => {
      if (!current || current.accessorKey !== accessorKey) {
        return { accessorKey, direction: "asc" };
      }
      return { accessorKey, direction: current.direction === "asc" ? "desc" : "asc" };
    });
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-end">
        <label className="input input-bordered flex min-h-11 items-center gap-2">
          <span className="text-sm opacity-70">Search</span>
          <input
            aria-label={`${ariaLabel} filter`}
            className="grow border-0 bg-transparent outline-none"
            onChange={(event) => {
              setPageIndex(0);
              setGlobalFilter(event.target.value);
            }}
            placeholder={searchPlaceholder}
            type="search"
            value={globalFilter}
          />
        </label>
      </div>

      <div className="overflow-x-auto rounded-box border border-base-300">
        <table aria-label={ariaLabel} className="table table-zebra w-full">
          <thead>
            <tr>
              {columns.map((column) => {
                const isSorted = sortState?.accessorKey === column.accessorKey?.toString();
                const direction = isSorted ? sortState?.direction : null;
                const canSort = column.sortable ?? true;

                return (
                  <th
                    aria-sort={direction === "asc" ? "ascending" : direction === "desc" ? "descending" : "none"}
                    key={column.accessorKey.toString()}
                    scope="col"
                  >
                    {canSort ? (
                      <button
                        aria-label={`Sort by ${column.header}`}
                        className="flex items-center gap-1 font-semibold"
                        onClick={() => toggleSort(column.accessorKey.toString())}
                        type="button"
                      >
                        {column.header}
                        <span aria-label={direction === "asc" ? "ascending" : direction === "desc" ? "descending" : "not sorted"}>
                          {direction === "asc" ? "↑" : direction === "desc" ? "↓" : "↕"}
                        </span>
                      </button>
                    ) : (
                      <span className="font-semibold">{column.header}</span>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>

          <tbody>
            {currentPage.length === 0 ? (
              <tr>
                <td className="py-6 text-center opacity-70" colSpan={columns.length}>
                  {emptyState}
                </td>
              </tr>
            ) : (
              currentPage.map((row, rowIndex) => (
                <tr key={`${JSON.stringify(row)}-${rowIndex}`}>
                  {columns.map((column) => (
                    <td key={`${column.accessorKey.toString()}-${rowIndex}`}>
                      {column.cell ? column.cell(row, row) : getCellValue(row, column.accessorKey)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between gap-3 text-sm">
        <span>{`Page ${pageIndex + 1} of ${totalPages}`}</span>
        <div className="flex items-center gap-2">
          <button
            aria-label="Previous page"
            className="btn btn-sm min-h-11"
            disabled={pageIndex === 0}
            onClick={() => setPageIndex((current) => Math.max(current - 1, 0))}
            type="button"
          >
            Prev
          </button>
          <button
            aria-label="Next page"
            className="btn btn-sm min-h-11"
            disabled={pageIndex >= totalPages - 1}
            onClick={() => setPageIndex((current) => Math.min(current + 1, totalPages - 1))}
            type="button"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
