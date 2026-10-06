"use client";

import { ArrowRight, Radio } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { StatusBadge } from "@/components/common/status-badge";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useMatches } from "@/hooks/queries";
import { SOURCE_LABEL, formatFixed, formatInt } from "@/lib/format";
import type { Match } from "@/lib/types";

export default function LiveIndexPage() {
  const active = useMatches({ status: ["starting", "processing", "paused"], limit: 50 });
  const recent = useMatches({ status: ["ready", "completed", "failed"], limit: 6 });

  return (
    <>
      <PageHeader title="Live Processing" description="Open a match to watch detections and events in real time" />
      <h2 className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">Active</h2>
      {active.isError ? (
        <ErrorState error={active.error} onRetry={() => active.refetch()} />
      ) : active.isPending ? (
        <CardGrid>{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-28" />)}</CardGrid>
      ) : active.data.data.length === 0 ? (
        <div className="rounded-lg border bg-card">
          <EmptyState icon={Radio} title="Nothing is processing" description="Start processing from a match below or from the Matches page." />
        </div>
      ) : (
        <CardGrid>
          {active.data.data.map((m) => <MatchCard key={m.id} match={m} />)}
        </CardGrid>
      )}

      <h2 className="mt-7 mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">Ready to start</h2>
      {recent.data && recent.data.data.length > 0 ? (
        <CardGrid>
          {recent.data.data.map((m) => <MatchCard key={m.id} match={m} />)}
        </CardGrid>
      ) : (
        <p className="text-sm text-muted-foreground">
          No idle matches. <Link className="text-primary hover:underline" href="/matches/new">Create one</Link>.
        </p>
      )}
    </>
  );
}

function CardGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{children}</div>;
}

function MatchCard({ match }: { match: Match }) {
  return (
    <Link
      href={`/matches/${match.id}/live`}
      className="group rounded-lg border bg-card p-4 transition-colors hover:border-primary/30"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate font-medium">
            {match.home_team} <span className="text-muted-foreground">vs</span> {match.away_team}
          </div>
          <div className="truncate text-xs text-muted-foreground">
            {match.competition || match.name} · {match.video_source_type ? SOURCE_LABEL[match.video_source_type] : "No source"}
          </div>
        </div>
        <StatusBadge status={match.status} />
      </div>
      <div className="mt-4 flex items-end justify-between text-xs text-muted-foreground">
        <div className="flex gap-4 tabular-nums">
          <span>
            <span className="text-foreground">{formatInt(match.event_count)}</span> events
          </span>
          {match.live ? (
            <span>
              <span className="text-foreground">{formatFixed(match.live.inference_fps, 1)}</span> fps
            </span>
          ) : null}
        </div>
        <Button variant="ghost" size="xs" nativeButton={false} render={<span />} className="text-muted-foreground group-hover:text-foreground">
          Open <ArrowRight />
        </Button>
      </div>
    </Link>
  );
}
