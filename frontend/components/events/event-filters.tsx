"use client";

import { EVENT_FILTERS, type EventFilter, type FilterOption } from "@/lib/events";
import { cn } from "@/lib/utils";

export function EventFilters({
  value,
  onChange,
  counts,
  filters = EVENT_FILTERS,
}: {
  value: EventFilter;
  onChange: (filter: EventFilter) => void;
  counts?: Partial<Record<EventFilter, number>>;
  filters?: FilterOption[];
}) {
  return (
    <div role="tablist" aria-label="Event type filter" className="scrollbar-thin flex gap-1 overflow-x-auto">
      {filters.map(({ key, label }) => (
        <button
          key={key}
          type="button"
          role="tab"
          aria-selected={value === key}
          onClick={() => onChange(key)}
          className={cn(
            "flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground",
            value === key && "bg-muted text-foreground",
          )}
        >
          {label}
          {counts?.[key] ? <span className="text-[10px] text-muted-foreground tabular-nums">{counts[key]}</span> : null}
        </button>
      ))}
    </div>
  );
}
