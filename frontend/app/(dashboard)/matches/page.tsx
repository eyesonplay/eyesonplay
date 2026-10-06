"use client";

import { ListVideo, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useDeferredValue, useState } from "react";

import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { PageHeader } from "@/components/layout/page-header";
import { MatchTable } from "@/components/matches/match-table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useMatches } from "@/hooks/queries";
import { STATUS_LABEL } from "@/lib/format";
import { MATCH_STATUSES, type MatchStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 25;

export default function MatchesPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<MatchStatus | null>(null);
  const [page, setPage] = useState(0);
  const q = useDeferredValue(search.trim());
  const matches = useMatches({ q, status: status ? [status] : undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE });
  const total = Number(matches.data?.meta?.total ?? 0);
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <PageHeader
        title="Matches"
        description="All matches and their processing state"
        actions={
          <Button nativeButton={false} render={<Link href="/matches/new" />}>
            <Plus /> New match
          </Button>
        }
      />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative w-full sm:w-64">
          <Search className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            placeholder="Search teams, competition…"
            className="pl-8"
            aria-label="Search matches"
          />
        </div>
        <div className="scrollbar-thin flex gap-1 overflow-x-auto">
          {[null, ...MATCH_STATUSES].map((s) => (
            <button
              key={s ?? "all"}
              type="button"
              onClick={() => {
                setStatus(s);
                setPage(0);
              }}
              className={cn(
                "shrink-0 rounded-md px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground",
                status === s && "bg-muted text-foreground",
              )}
            >
              {s ? STATUS_LABEL[s] : "All"}
            </button>
          ))}
        </div>
      </div>

      <section className="rounded-lg border bg-card">
        {matches.isError ? (
          <ErrorState error={matches.error} onRetry={() => matches.refetch()} className="m-4" />
        ) : !matches.isPending && total === 0 ? (
          <EmptyState
            icon={ListVideo}
            title={q || status ? "No matches match these filters" : "No matches yet"}
            description={q || status ? "Try a different search or status." : "Create your first match to start analysing video."}
            action={
              q || status ? undefined : (
                <Button size="sm" nativeButton={false} render={<Link href="/matches/new" />}>
                  <Plus /> Create match
                </Button>
              )
            }
          />
        ) : (
          <MatchTable matches={matches.data?.data ?? []} loading={matches.isPending} />
        )}
      </section>

      {pages > 1 ? (
        <div className="mt-3 flex items-center justify-end gap-2 text-xs text-muted-foreground">
          <span className="tabular-nums">
            Page {page + 1} of {pages} · {total} matches
          </span>
          <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            Previous
          </Button>
          <Button variant="outline" size="sm" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>
            Next
          </Button>
        </div>
      ) : null}
    </>
  );
}
