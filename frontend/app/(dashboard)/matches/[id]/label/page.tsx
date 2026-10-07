"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { ErrorState } from "@/components/common/error-state";
import { PageHeader } from "@/components/layout/page-header";
import { LabelWorkbench } from "@/components/labelling/label-workbench";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useLabels, useMatch } from "@/hooks/queries";

export default function LabelPage() {
  const { id } = useParams<{ id: string }>();
  const match = useMatch(id);
  const labels = useLabels(id);

  if (match.isError) return <ErrorState error={match.error} onRetry={() => match.refetch()} />;
  if (labels.isError) return <ErrorState error={labels.error} onRetry={() => labels.refetch()} />;
  if (!match.data || !labels.data) return <Skeleton className="h-[520px]" />;

  return (
    <>
      <PageHeader
        title={`Label · ${match.data.name}`}
        description="Mark what happens in the video. Labels train the models and measure accuracy (benchmark)."
        actions={
          <Button size="sm" variant="ghost" nativeButton={false} render={<Link href={`/matches/${id}/live`} />}>
            <ArrowLeft /> Live view
          </Button>
        }
      />
      <LabelWorkbench match={match.data} initial={labels.data} />
    </>
  );
}
