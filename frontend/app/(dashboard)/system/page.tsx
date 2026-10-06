"use client";

import { CheckCircle2, Cpu, XCircle } from "lucide-react";

import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { PageHeader } from "@/components/layout/page-header";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useGpus, useHealth, useWorkers } from "@/hooks/queries";
import { formatRelative } from "@/lib/format";

export default function SystemPage() {
  const health = useHealth();
  const workers = useWorkers();
  const gpus = useGpus();

  return (
    <>
      <PageHeader title="System" description="Service health, inference workers and GPU telemetry" />

      <div className="mb-6 grid gap-3 sm:grid-cols-3">
        {health.isError ? (
          <ErrorState error={health.error} title="API unreachable" className="sm:col-span-3" onRetry={() => health.refetch()} />
        ) : !health.data ? (
          Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-20" />)
        ) : (
          <>
            <ServiceCard name="API" ok detail="Responding" />
            <ServiceCard name="PostgreSQL" ok={health.data.database.ok} detail={health.data.database.detail ?? "Connected"} />
            <ServiceCard name="Redis" ok={health.data.redis.ok} detail={health.data.redis.detail ?? "Connected"} />
          </>
        )}
      </div>

      <section className="mb-6 rounded-lg border bg-card">
        <h2 className="border-b px-4 py-3 text-sm font-medium">Inference workers</h2>
        {workers.isError ? (
          <ErrorState error={workers.error} onRetry={() => workers.refetch()} className="m-4" />
        ) : workers.isPending ? (
          <div className="p-4">
            <Skeleton className="h-16" />
          </div>
        ) : workers.data.length === 0 ? (
          <EmptyState icon={Cpu} title="No workers online" description="Start the worker service (docker compose up worker) to process matches." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Worker</TableHead>
                <TableHead>Mode</TableHead>
                <TableHead>Device</TableHead>
                <TableHead className="text-right">Load</TableHead>
                <TableHead className="hidden text-right sm:table-cell">Last heartbeat</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {workers.data.map((w) => (
                <TableRow key={w.worker_id}>
                  <TableCell className="font-mono text-xs">{w.worker_id}</TableCell>
                  <TableCell className="text-xs uppercase">{w.mode}</TableCell>
                  <TableCell className="font-mono text-xs uppercase">{w.device}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {w.active_matches.length} / {w.capacity}
                  </TableCell>
                  <TableCell className="hidden text-right text-xs text-muted-foreground sm:table-cell">
                    {formatRelative(w.last_seen)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <section className="rounded-lg border bg-card">
        <h2 className="border-b px-4 py-3 text-sm font-medium">GPUs</h2>
        {gpus.isError ? (
          <ErrorState error={gpus.error} onRetry={() => gpus.refetch()} className="m-4" />
        ) : gpus.isPending ? (
          <div className="p-4">
            <Skeleton className="h-16" />
          </div>
        ) : gpus.data.length === 0 ? (
          <EmptyState
            icon={Cpu}
            title="No NVIDIA GPU detected"
            description="Workers are running on CPU (or in mock mode). GPU metrics appear automatically on NVIDIA hosts."
          />
        ) : (
          <div className="grid gap-3 p-4 md:grid-cols-2">
            {gpus.data.map((g) => (
              <div key={`${g.worker_id}:${g.index}`} className="rounded-md border p-3">
                <div className="flex justify-between text-sm">
                  <span>{g.name}</span>
                  <span className="font-mono text-xs text-muted-foreground">{g.worker_id}</span>
                </div>
                <GpuBar label="Utilization" value={g.utilization} text={`${g.utilization}%`} />
                <GpuBar
                  label="VRAM"
                  value={(g.memory_used_mb / g.memory_total_mb) * 100}
                  text={`${(g.memory_used_mb / 1024).toFixed(1)} / ${(g.memory_total_mb / 1024).toFixed(0)} GB`}
                />
                {g.temperature_c != null ? (
                  <div className="mt-2 text-xs text-muted-foreground">Temperature {g.temperature_c}°C</div>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}

function ServiceCard({ name, ok, detail }: { name: string; ok: boolean; detail: string }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border bg-card p-4">
      {ok ? <CheckCircle2 className="mt-0.5 size-4 text-primary" /> : <XCircle className="mt-0.5 size-4 text-destructive" />}
      <div className="min-w-0">
        <div className="text-sm font-medium">{name}</div>
        <div className="truncate text-xs text-muted-foreground" title={detail}>
          {detail}
        </div>
      </div>
    </div>
  );
}

function GpuBar({ label, value, text }: { label: string; value: number; text: string }) {
  return (
    <div className="mt-3">
      <div className="mb-1 flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono tabular-nums">{text}</span>
      </div>
      <Progress value={value} />
    </div>
  );
}
