"use client";

import { Boxes, CheckCircle2, CircleDashed } from "lucide-react";

import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { PageHeader } from "@/components/layout/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { useModels } from "@/hooks/queries";

const ROADMAP = [
  { name: "RF-DETR", detail: "Transformer detector; plugs in via the Detector interface (worker/detect/registry.py)." },
  { name: "Pitch keypoints", detail: "Automatic homography for normalised pitch coordinates (Phase 5)." },
  { name: "TensorRT / ONNX", detail: "Optimised GPU inference builds (Phase 6)." },
];

export default function ModelsPage() {
  const models = useModels();
  return (
    <>
      <PageHeader title="Models" description="Detection models reported by running inference workers" />
      {models.isError ? (
        <ErrorState error={models.error} onRetry={() => models.refetch()} />
      ) : models.isPending ? (
        <div className="grid gap-3 md:grid-cols-2">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
      ) : models.data.length === 0 ? (
        <div className="rounded-lg border bg-card">
          <EmptyState icon={Boxes} title="No workers online" description="Models are listed once an inference worker reports its heartbeat." />
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {models.data.map((m) => (
            <div key={`${m.worker_id}:${m.name}`} className="rounded-lg border bg-card p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate font-mono text-sm">{m.name}</div>
                  <div className="text-xs text-muted-foreground uppercase">{m.family}</div>
                </div>
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  {m.loaded ? <CheckCircle2 className="size-3.5 text-primary" /> : <CircleDashed className="size-3.5" />}
                  {m.loaded ? "Loaded" : "Not loaded"}
                </span>
              </div>
              {m.description ? <p className="mt-3 text-xs text-muted-foreground">{m.description}</p> : null}
              <dl className="mt-3 grid grid-cols-2 gap-y-1 text-xs">
                <dt className="text-muted-foreground">Device</dt>
                <dd className="font-mono uppercase">{m.device}</dd>
                <dt className="text-muted-foreground">Worker</dt>
                <dd className="truncate font-mono">{m.worker_id}</dd>
                {m.classes ? (
                  <>
                    <dt className="text-muted-foreground">Classes</dt>
                    <dd>{m.classes.join(", ")}</dd>
                  </>
                ) : null}
              </dl>
            </div>
          ))}
        </div>
      )}
      <h2 className="mt-8 mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">Planned</h2>
      <div className="grid gap-3 md:grid-cols-3">
        {ROADMAP.map((r) => (
          <div key={r.name} className="rounded-lg border border-dashed p-4">
            <div className="text-sm">{r.name}</div>
            <p className="mt-1 text-xs text-muted-foreground">{r.detail}</p>
          </div>
        ))}
      </div>
    </>
  );
}
