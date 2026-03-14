/**
 * DataTable — Sortable table for structured gate review data.
 *
 * Generic table component with column definitions, sortable headers,
 * and SG brand styling. Used by gate-specific panels.
 */

"use client";

import { useState, useMemo, useCallback } from "react";

export interface DataTableColumn<T> {
  /** Column key matching data field */
  key: string;
  /** Display header label */
  label: string;
  /** Whether this column is sortable */
  sortable?: boolean;
  /** Custom cell renderer */
  render?: (row: T, index: number) => React.ReactNode;
  /** Column width class (e.g., "w-1/4") */
  width?: string;
}

export interface DataTableProps<T> {
  /** Column definitions */
  columns: DataTableColumn<T>[];
  /** Row data */
  data: T[];
  /** Unique key extractor */
  getRowKey: (row: T, index: number) => string;
  /** Optional empty state message */
  emptyMessage?: string;
  /** Optional CSS class */
  className?: string;
}

type SortDirection = "asc" | "desc";

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  getRowKey,
  emptyMessage = "No data",
  className = "",
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDirection>("asc");

  const handleSort = useCallback(
    (key: string) => {
      if (sortKey === key) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortKey(key);
        setSortDir("asc");
      }
    },
    [sortKey],
  );

  const sortedData = useMemo(() => {
    if (!sortKey) return data;

    return [...data].sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];

      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;

      let cmp = 0;
      if (typeof aVal === "string" && typeof bVal === "string") {
        cmp = aVal.localeCompare(bVal);
      } else if (typeof aVal === "number" && typeof bVal === "number") {
        cmp = aVal - bVal;
      } else {
        cmp = String(aVal).localeCompare(String(bVal));
      }

      return sortDir === "desc" ? -cmp : cmp;
    });
  }, [data, sortKey, sortDir]);

  if (data.length === 0) {
    return (
      <div className={`rounded-lg border border-sg-border p-6 text-center text-sm text-sg-slate/60 ${className}`}>
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className={`overflow-x-auto rounded-lg border border-sg-border ${className}`}>
      <table className="w-full text-sm" data-testid="data-table">
        <thead>
          <tr className="border-b border-sg-border bg-sg-mist/50">
            {columns.map((col) => (
              <th
                key={col.key}
                className={[
                  "px-4 py-2.5 text-start text-xs font-semibold uppercase tracking-wider text-sg-slate/70",
                  col.width,
                  col.sortable && "cursor-pointer select-none hover:text-sg-navy",
                ]
                  .filter(Boolean)
                  .join(" ")}
                onClick={col.sortable ? () => handleSort(col.key) : undefined}
                aria-sort={
                  sortKey === col.key
                    ? sortDir === "asc"
                      ? "ascending"
                      : "descending"
                    : undefined
                }
              >
                <span className="inline-flex items-center gap-1">
                  {col.label}
                  {col.sortable && sortKey === col.key && (
                    <SortArrow direction={sortDir} />
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedData.map((row, rowIndex) => (
            <tr
              key={getRowKey(row, rowIndex)}
              className="border-b border-sg-border last:border-b-0 hover:bg-sg-mist/30"
            >
              {columns.map((col) => (
                <td key={col.key} className={`px-4 py-2.5 ${col.width ?? ""}`}>
                  {col.render
                    ? col.render(row, rowIndex)
                    : String(row[col.key] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SortArrow({ direction }: { direction: SortDirection }) {
  return (
    <svg
      viewBox="0 0 8 12"
      fill="currentColor"
      className="h-3 w-2"
      aria-hidden="true"
    >
      {direction === "asc" ? (
        <path d="M4 0L8 5H0L4 0Z" />
      ) : (
        <path d="M4 12L0 7H8L4 12Z" />
      )}
    </svg>
  );
}
