"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { MatchForm, applyServerErrors, useMatchForm, type SubmitIntent } from "@/components/matches/match-form";
import { defaultValues, toMatchInput, type MatchFormValues } from "@/components/matches/form-schema";
import { useAppSettings, useCreateMatch } from "@/hooks/queries";
import { api, errorMessage } from "@/lib/api";
import type { AppSettings } from "@/lib/types";

export default function NewMatchPage() {
  const settings = useAppSettings();
  const header = <PageHeader title="New match" description="Enter match details, choose a video source and configure processing" />;
  if (settings.isPending) {
    return (
      <>
        {header}
        <Skeleton className="h-96" />
      </>
    );
  }
  // If the defaults can't be loaded the form still works with built-in defaults.
  return (
    <>
      {header}
      <NewMatchForm settings={settings.data} />
    </>
  );
}

function NewMatchForm({ settings }: { settings?: AppSettings }) {
  const router = useRouter();
  const form = useMatchForm(defaultValues(settings));
  const create = useCreateMatch();
  const [submitting, setSubmitting] = useState<SubmitIntent | null>(null);

  const onSubmit = async (values: MatchFormValues, intent: SubmitIntent) => {
    setSubmitting(intent);
    try {
      const match = await create.mutateAsync(toMatchInput(values));
      if (intent === "start") {
        try {
          await api.processing(match.id, "start");
          toast.success("Processing started", { description: `${match.home_team} vs ${match.away_team}` });
        } catch (error) {
          toast.error("Match created, but processing could not start", { description: errorMessage(error) });
        }
        router.push(`/matches/${match.id}/live`);
      } else {
        toast.success(match.status === "draft" ? "Draft saved" : "Match created");
        router.push("/matches");
      }
    } catch (error) {
      applyServerErrors(form, error);
      toast.error("Could not create match", { description: errorMessage(error) });
    } finally {
      setSubmitting(null);
    }
  };

  return <MatchForm form={form} onSubmit={onSubmit} submitting={submitting} mode="create" />;
}
