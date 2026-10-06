"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { Activity, Loader2 } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { JsonView } from "@/components/common/json-view";
import { EventFilters } from "@/components/events/event-filters";
import { EventTag } from "@/components/events/event-tag";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { queryKeys, useMatches } from "@/hooks/queries";
import { api } from "@/lib/api";
import { eventSummary, type EventFilter } from "@/lib/events";
import { formatDateTime } from "@/lib/format";
import type { EventRecord } from "@/lib/types";

const PAGE = 50;
const ALL = "__all__";

export default function EventsPage() {
  const [filter, setFilter] = useState<EventFilter>("all");
  const [matchId, setMatchId] = useState<string>(ALL);
  const [open, setOpen] = useState<EventRecord | null>(null);
  const matches = useMatches({ limit: 200 });
  const matchItems: Record<string, string> = { [ALL]: "All matches" };
  for (const m of matches.data?.data ?? []) matchItems[m.id] = `${m.home_team} vs ${m.away_team}`;

  const params = { matchId: matchId === ALL ? undefined : matchId, groups: filter === "all" ? undefined : [filter] };
  const events = useInfiniteQuery({
    queryKey: queryKeys.events(params),
    queryFn: ({ pageParam }) => api.listEvents({ ...params, limit: PAGE, beforeId: pageParam }),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (last) => (last.meta?.next_before_id as number | null) ?? undefined,
    refetchInterval: 5_000,
  });
  const rows = events.data?.pages.flatMap((p) => p.data) ?? [];

  return (
    <>
      <PageHeader title="Events" description="Every persisted event across matches" />
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <Select items={matchItems} value={matchId} onValueChange={(v) => setMatchId(v ?? ALL)}>
          <SelectTrigger className="w-64" aria-label="Filter by match">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(matchItems).map(([id, label]) => (
              <SelectItem key={id} value={id}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <EventFilters value={filter} onChange={setFilter} />
      </div>

      <section className="rounded-lg border bg-card">
        {events.isError ? (
          <ErrorState error={events.error} onRetry={() => events.refetch()} className="m-4" />
        ) : events.isPending ? (
          <div className="flex flex-col gap-2 p-4">
            {Array.from({ length: 6 }, (_, i) => (
              <Skeleton key={i} className="h-8" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <EmptyState
            icon={Activity}
            title={filter === "goal" ? "Goal detection is not available yet" : "No events found"}
            description="Events appear here once processing detects them."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-16">Clock</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="hidden md:table-cell">Details</TableHead>
                <TableHead className="hidden lg:table-cell">Match</TableHead>
                <TableHead className="text-right">Conf.</TableHead>
                <TableHead className="hidden text-right sm:table-cell">Recorded</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((e) => (
                <TableRow key={e.id} className="cursor-pointer" onClick={() => setOpen(e)}>
                  <TableCell className="font-mono text-xs tabular-nums">{e.match_clock}</TableCell>
                  <TableCell>
                    <EventTag type={e.event_type} />
                  </TableCell>
                  <TableCell className="hidden max-w-72 truncate font-mono text-xs text-muted-foreground md:table-cell">
                    {eventSummary(e.payload)}
                  </TableCell>
                  <TableCell className="hidden max-w-56 truncate text-xs lg:table-cell">{matchItems[e.match_id] ?? e.match_id}</TableCell>
                  <TableCell className="text-right font-mono text-xs tabular-nums">{e.confidence.toFixed(2)}</TableCell>
                  <TableCell className="hidden text-right text-xs text-muted-foreground tabular-nums sm:table-cell">
                    {formatDateTime(e.created_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>
      {events.hasNextPage ? (
        <div className="mt-3 flex justify-center">
          <Button variant="outline" size="sm" onClick={() => events.fetchNextPage()} disabled={events.isFetchingNextPage}>
            {events.isFetchingNextPage ? <Loader2 className="animate-spin" /> : null} Load older events
          </Button>
        </div>
      ) : null}

      <Dialog open={open !== null} onOpenChange={(o) => !o && setOpen(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {open ? <EventTag type={open.event_type} /> : null}
              <span className="font-mono text-sm">{open?.payload.event_id}</span>
            </DialogTitle>
          </DialogHeader>
          <div className="scrollbar-thin max-h-[60vh] overflow-auto rounded-md bg-black/25 p-3">
            {open ? <JsonView value={open.payload} /> : null}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
