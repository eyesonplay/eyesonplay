"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { ErrorState, InlineAlert } from "@/components/common/error-state";
import { StatusBadge } from "@/components/common/status-badge";
import { PageHeader } from "@/components/layout/page-header";
import { MatchForm, applyServerErrors, useMatchForm, type SubmitIntent } from "@/components/matches/match-form";
import { toMatchInput, valuesFromMatch, type MatchFormValues } from "@/components/matches/form-schema";
import { SessionHistory } from "@/components/matches/session-history";
import { Skeleton } from "@/components/ui/skeleton";
import { useMatch, useUpdateMatch } from "@/hooks/queries";
import { api, errorMessage } from "@/lib/api";
import type { Match } from "@/lib/types";

const ACTIVE = new Set(["starting", "processing", "paused"]);

export default function EditMatchPage() {
  const { id } = useParams<{ id: string }>();
  const match = useMatch(id);
  if (match.isError) return <ErrorState error={match.error} onRetry={() => match.refetch()} />;
  if (!match.data) return <Skeleton className="h-96" />;
  // Keyed by id: the form is seeded once and not overwritten by background refetches.
  return <EditMatch key={match.data.id} match={match.data} />;
}

function EditMatch({ match }: { match: Match }) {
  const id = match.id;
  const router = useRouter();
  const update = useUpdateMatch(id);
  const form = useMatchForm(valuesFromMatch(match));
  const [submitting, setSubmitting] = useState<SubmitIntent | null>(null);
  const locked = ACTIVE.has(match.status);

  const onSubmit = async (values: MatchFormValues, intent: SubmitIntent) => {
    setSubmitting(intent);
    try {
      const input = toMatchInput(values);
      // While processing, only descriptive fields may change (the API enforces this too).
      const { name, home_team, away_team, competition, match_date } = input;
      await update.mutateAsync(locked ? { name, home_team, away_team, competition, match_date } : input);
      if (intent === "start") {
        await api.processing(id, "start");
        toast.success("Processing started");
        router.push(`/matches/${id}/live`);
      } else {
        toast.success("Changes saved");
      }
    } catch (error) {
      applyServerErrors(form, error);
      toast.error("Could not save changes", { description: errorMessage(error) });
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <>
      <PageHeader
        title={
          <span className="flex items-center gap-3">
            Edit match <StatusBadge status={match.status} />
          </span>
        }
        description={`${match.home_team} vs ${match.away_team}`}
      />
      {locked ? (
        <div className="mb-4">
          <InlineAlert tone="warn" title="Processing is active">
            stop processing to change the video source or processing settings. Names and dates can still be edited.
          </InlineAlert>
        </div>
      ) : null}
      <MatchForm form={form} onSubmit={onSubmit} submitting={submitting} mode="edit" locked={locked} />
      <SessionHistory matchId={id} />
    </>
  );
}
