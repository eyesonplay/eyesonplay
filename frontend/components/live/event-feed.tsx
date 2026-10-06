"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowUp, Goal, Inbox } from "lucide-react";
import { useLayoutEffect, useMemo, useRef, useState } from "react";

import { EmptyState } from "@/components/common/empty-state";
import { EventFilters } from "@/components/events/event-filters";
import { EventTag } from "@/components/events/event-tag";
import { eventGroup, eventSummary, filtersFor, matchesFilter, type EventFilter } from "@/lib/events";
import type { EventPayload, Sport } from "@/lib/types";
import { cn } from "@/lib/utils";

const ROW_HEIGHT = 44;
const AT_TOP_PX = 8;

export function EventFeed({
  events,
  selectedId,
  onSelect,
  sport = "football",
}: {
  events: EventPayload[];
  selectedId: string | null;
  onSelect: (event: EventPayload) => void;
  sport?: Sport;
}) {
  const filters = filtersFor(sport);
  const [filter, setFilter] = useState<EventFilter>("all");
  const scrollRef = useRef<HTMLDivElement>(null);
  const [unseen, setUnseen] = useState(0);
  const filtered = useMemo(() => events.filter((e) => matchesFilter(e.event, filter)), [events, filter]);
  const counts = useMemo(() => {
    const result: Partial<Record<EventFilter, number>> = { all: events.length };
    for (const e of events) {
      const group = eventGroup(e.event);
      if (group) result[group] = (result[group] ?? 0) + 1;
    }
    return result;
  }, [events]);

  // TanStack Virtual is not React-Compiler friendly; the compiler simply skips this component.
  // eslint-disable-next-line react-hooks/incompatible-library
  const virtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
    getItemKey: (index) => filtered[index].event_id,
  });

  // Newest events are prepended. Keep the reader's position when they have
  // scrolled down, and tell them how many new events arrived above.
  const previousFirst = useRef<string | null>(null);
  const previousLength = useRef(0);
  useLayoutEffect(() => {
    const el = scrollRef.current;
    const first = filtered[0]?.event_id ?? null;
    const added = filtered.length - previousLength.current;
    if (el && first !== previousFirst.current && added > 0 && previousFirst.current !== null) {
      if (el.scrollTop > AT_TOP_PX) {
        el.scrollTop += added * ROW_HEIGHT;
        setUnseen((n) => n + added);
      }
    }
    previousFirst.current = first;
    previousLength.current = filtered.length;
  }, [filtered]);

  const filterLabel = filters.find((f) => f.key === filter)?.label ?? "";

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-b px-3 py-2">
        <EventFilters
          value={filter}
          filters={filters}
          counts={counts}
          onChange={(f) => {
            setFilter(f);
            setUnseen(0);
          }}
        />
      </div>
      <div className="relative min-h-0 flex-1">
        {unseen > 0 ? (
          <button
            type="button"
            onClick={() => {
              scrollRef.current?.scrollTo({ top: 0, behavior: "smooth" });
              setUnseen(0);
            }}
            className="absolute top-2 left-1/2 z-10 flex -translate-x-1/2 items-center gap-1 rounded-full bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground shadow"
          >
            <ArrowUp className="size-3" /> {unseen} new
          </button>
        ) : null}
        <div
          ref={scrollRef}
          className="scrollbar-thin absolute inset-0 overflow-y-auto"
          onScroll={(e) => e.currentTarget.scrollTop <= AT_TOP_PX && unseen && setUnseen(0)}
        >
          {filtered.length === 0 ? (
            filter === "goal" ? (
              <EmptyState icon={Goal} title="Goal detection is not available yet" description="Goals will appear here once the goal event model ships." />
            ) : (
              <EmptyState
                icon={Inbox}
                title={filter === "all" ? "Waiting for events" : `No ${filterLabel.toLowerCase()} events yet`}
                description={filter === "all" ? "Events stream in over WebSocket as soon as processing produces them." : undefined}
              />
            )
          ) : (
            <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
              {virtualizer.getVirtualItems().map((item) => {
                const event = filtered[item.index];
                const selected = event.event_id === selectedId;
                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => onSelect(event)}
                    style={{ transform: `translateY(${item.start}px)`, height: ROW_HEIGHT }}
                    className={cn(
                      "absolute inset-x-0 top-0 flex items-center gap-2.5 border-b border-border/60 px-3 text-left transition-colors hover:bg-muted/40",
                      selected && "bg-primary/8 hover:bg-primary/10",
                    )}
                    aria-pressed={selected}
                  >
                    <span className="w-11 shrink-0 font-mono text-xs text-muted-foreground tabular-nums">{event.match_clock}</span>
                    <EventTag type={event.event} />
                    <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-muted-foreground">
                      {eventSummary(event)}
                    </span>
                    <span className="shrink-0 font-mono text-[11px] tabular-nums text-muted-foreground">
                      {event.confidence.toFixed(2)}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
