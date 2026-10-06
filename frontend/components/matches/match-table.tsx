"use client";

import { MoreHorizontal, Pencil, Radio, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { StatusBadge } from "@/components/common/status-badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useDeleteMatch } from "@/hooks/queries";
import { errorMessage } from "@/lib/api";
import { SOURCE_LABEL, SPORT_LABEL, formatDateTime, formatFixed, formatInt, sourceSummary } from "@/lib/format";
import type { Match } from "@/lib/types";

const ACTIVE = new Set(["starting", "processing", "paused"]);

export function MatchTable({ matches, loading, compact }: { matches: Match[]; loading?: boolean; compact?: boolean }) {
  const router = useRouter();
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>Match</TableHead>
          <TableHead className="hidden md:table-cell">Date</TableHead>
          <TableHead className="hidden lg:table-cell">Video source</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Events</TableHead>
          <TableHead className="hidden text-right sm:table-cell">FPS</TableHead>
          {compact ? null : <TableHead className="w-10" />}
        </TableRow>
      </TableHeader>
      <TableBody>
        {loading
          ? Array.from({ length: 4 }, (_, i) => (
              <TableRow key={i}>
                {Array.from({ length: compact ? 6 : 7 }, (_, j) => (
                  <TableCell key={j}>
                    <Skeleton className="h-4 w-full max-w-28" />
                  </TableCell>
                ))}
              </TableRow>
            ))
          : matches.map((match) => (
              <TableRow
                key={match.id}
                className="cursor-pointer"
                onClick={() => router.push(`/matches/${match.id}/live`)}
              >
                <TableCell className="max-w-64">
                  <div className="truncate font-medium">
                    {match.home_team} <span className="text-muted-foreground">vs</span> {match.away_team}
                  </div>
                  <div className="truncate text-xs text-muted-foreground">
                    {SPORT_LABEL[match.sport]} · {match.competition || match.name}
                  </div>
                </TableCell>
                <TableCell className="hidden text-muted-foreground tabular-nums md:table-cell">
                  {formatDateTime(match.match_date)}
                </TableCell>
                <TableCell className="hidden max-w-56 lg:table-cell">
                  <div className="text-xs">{match.video_source_type ? SOURCE_LABEL[match.video_source_type] : "—"}</div>
                  <div className="truncate font-mono text-[11px] text-muted-foreground">
                    {sourceSummary(match.video_source_type, match.video_source)}
                  </div>
                </TableCell>
                <TableCell>
                  <StatusBadge status={match.status} />
                </TableCell>
                <TableCell className="text-right tabular-nums">{formatInt(match.event_count)}</TableCell>
                <TableCell className="hidden text-right tabular-nums sm:table-cell">
                  {ACTIVE.has(match.status) ? formatFixed(match.live?.inference_fps, 1) : "—"}
                </TableCell>
                {compact ? null : (
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <RowActions match={match} />
                  </TableCell>
                )}
              </TableRow>
            ))}
      </TableBody>
    </Table>
  );
}

function RowActions({ match }: { match: Match }) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const remove = useDeleteMatch();
  const active = ACTIVE.has(match.status);

  const onDelete = () =>
    remove.mutate(match.id, {
      onSuccess: () => toast.success(`Deleted ${match.home_team} vs ${match.away_team}`),
      onError: (error) => toast.error("Delete failed", { description: errorMessage(error) }),
    });

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger render={<Button variant="ghost" size="icon-sm" aria-label="Match actions" />}>
          <MoreHorizontal />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-44">
          <DropdownMenuItem render={<Link href={`/matches/${match.id}/live`} />}>
            <Radio /> Open live view
          </DropdownMenuItem>
          <DropdownMenuItem render={<Link href={`/matches/${match.id}/edit`} />}>
            <Pencil /> Edit match
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" disabled={active} onClick={() => setConfirmOpen(true)}>
            <Trash2 /> Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Delete this match?"
        description="The match, its processing sessions and all detected events are permanently removed. An uploaded video is deleted too."
        confirmLabel="Delete match"
        destructive
        onConfirm={onDelete}
      />
    </>
  );
}
