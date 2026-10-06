"use client";

import { Activity, Gauge, Plus, Radio, Timer, Video, Zap } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/common/empty-state";
import { ErrorState, InlineAlert } from "@/components/common/error-state";
import { StatCard } from "@/components/common/stat-card";
import { PageHeader } from "@/components/layout/page-header";
import { MatchTable } from "@/components/matches/match-table";
import { Button } from "@/components/ui/button";
import { useMatches, useSummary } from "@/hooks/queries";
import { formatFixed, formatInt } from "@/lib/format";

export default function DashboardPage() {
  const summary = useSummary();
  const recent = useMatches({ limit: 8 });
  const s = summary.data;
  const noGpu = s != null && s.gpu_utilization == null;

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Processing overview across all matches"
        actions={
          <Button nativeButton={false} render={<Link href="/matches/new" />}>
            <Plus /> New match
          </Button>
        }
      />

      {summary.isError ? (
        <ErrorState error={summary.error} onRetry={() => summary.refetch()} className="mb-5" />
      ) : (
        <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <StatCard label="Active matches" icon={Radio} loading={summary.isPending} value={formatInt(s?.active_matches)}
            hint="starting, processing or paused" />
          <StatCard label="Processing now" icon={Video} loading={summary.isPending} value={formatInt(s?.processing_matches)}
            hint={s ? `${s.workers} worker${s.workers === 1 ? "" : "s"} online` : undefined} />
          <StatCard label="Events today" icon={Activity} loading={summary.isPending} value={formatInt(s?.events_today)}
            hint="since 00:00 UTC" />
          <StatCard label="GPU utilization" icon={Zap} loading={summary.isPending}
            value={noGpu ? <span className="text-base text-muted-foreground">No GPU</span> : formatFixed(s?.gpu_utilization, 0, "%")}
            hint={s?.devices.length ? `device: ${s.devices.join(", ")}` : "no workers"} />
          <StatCard label="Avg inference FPS" icon={Gauge} loading={summary.isPending}
            value={formatFixed(s?.average_inference_fps, 1)} hint="across processing matches" />
          <StatCard label="Avg latency" icon={Timer} loading={summary.isPending}
            value={formatFixed(s?.average_latency_ms, 0, " ms")} hint="capture → publish" />
        </div>
      )}

      {s && s.workers === 0 ? (
        <div className="mb-4">
          <InlineAlert tone="warn" title="No inference worker online">
            matches can be created, but processing will not start until the worker service is running.
          </InlineAlert>
        </div>
      ) : null}

      <section className="rounded-lg border bg-card">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="text-sm font-medium">Recent matches</h2>
          <Link href="/matches" className="text-xs text-muted-foreground hover:text-foreground">
            View all
          </Link>
        </div>
        {recent.isError ? (
          <ErrorState error={recent.error} onRetry={() => recent.refetch()} className="m-4" />
        ) : !recent.isPending && recent.data?.data.length === 0 ? (
          <EmptyState
            icon={Video}
            title="No matches yet"
            description="Create a match, add an HLS stream or upload a video, and start processing."
            action={
              <Button size="sm" nativeButton={false} render={<Link href="/matches/new" />}>
                <Plus /> Create match
              </Button>
            }
          />
        ) : (
          <MatchTable matches={recent.data?.data ?? []} loading={recent.isPending} compact />
        )}
      </section>
    </>
  );
}
