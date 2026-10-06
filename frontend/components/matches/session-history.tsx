"use client";

import { History } from "lucide-react";

import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useSessions } from "@/hooks/queries";
import { formatDateTime, formatFixed, formatInt } from "@/lib/format";

export function SessionHistory({ matchId }: { matchId: string }) {
  const sessions = useSessions(matchId);
  return (
    <section className="mt-5 rounded-lg border bg-card">
      <h2 className="border-b px-4 py-3 text-sm font-medium">Processing sessions</h2>
      {sessions.isError ? (
        <ErrorState error={sessions.error} onRetry={() => sessions.refetch()} className="m-4" />
      ) : sessions.isPending ? (
        <div className="p-4">
          <Skeleton className="h-16" />
        </div>
      ) : sessions.data.length === 0 ? (
        <EmptyState icon={History} title="No sessions yet" description="Each start or restart creates a session." />
      ) : (
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Started</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Frames</TableHead>
              <TableHead className="hidden text-right sm:table-cell">Avg FPS</TableHead>
              <TableHead className="hidden text-right sm:table-cell">Avg latency</TableHead>
              <TableHead className="hidden md:table-cell">Worker</TableHead>
              <TableHead className="hidden lg:table-cell">Error</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sessions.data.map((s) => (
              <TableRow key={s.id}>
                <TableCell className="tabular-nums">{formatDateTime(s.started_at)}</TableCell>
                <TableCell className="capitalize">{s.status}</TableCell>
                <TableCell className="text-right tabular-nums">{formatInt(s.frames_processed)}</TableCell>
                <TableCell className="hidden text-right tabular-nums sm:table-cell">{formatFixed(s.average_fps, 1)}</TableCell>
                <TableCell className="hidden text-right tabular-nums sm:table-cell">
                  {formatFixed(s.average_latency, 0, " ms")}
                </TableCell>
                <TableCell className="hidden font-mono text-xs md:table-cell">
                  {s.worker_id ?? "—"} {s.device ? <span className="text-muted-foreground">({s.device})</span> : null}
                </TableCell>
                <TableCell className="hidden max-w-72 truncate text-xs text-destructive lg:table-cell">{s.error ?? ""}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
