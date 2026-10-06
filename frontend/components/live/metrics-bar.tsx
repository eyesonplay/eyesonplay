import type { ReactNode } from "react";

import { formatFixed, formatInt } from "@/lib/format";
import type { MetricsData } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { ConnectionState } from "@/lib/ws";

const CONNECTION: Record<ConnectionState, { label: string; dot: string }> = {
  connecting: { label: "Connecting", dot: "bg-amber-300" },
  open: { label: "Live", dot: "bg-primary" },
  reconnecting: { label: "Reconnecting", dot: "bg-amber-300 animate-pulse" },
  closed: { label: "Disconnected", dot: "bg-destructive" },
};

export function MetricsBar({
  metrics,
  connection,
  connectionDetail,
}: {
  metrics: MetricsData | null;
  connection: ConnectionState;
  connectionDetail: string | null;
}) {
  const gpu = metrics?.gpu ?? null;
  const conn = CONNECTION[connection];
  return (
    <div className="scrollbar-thin flex items-center gap-x-5 gap-y-1 overflow-x-auto rounded-lg border bg-card/95 px-4 py-2.5 text-xs shadow-lg backdrop-blur">
      <span className="flex shrink-0 items-center gap-1.5" title={connectionDetail ?? undefined}>
        <span className={cn("size-1.5 rounded-full", conn.dot)} />
        <span className="text-muted-foreground">{conn.label}</span>
      </span>
      <Divider />
      <Metric label="Source FPS" value={formatFixed(metrics?.source_fps, 0)} />
      <Metric label="Inference FPS" value={formatFixed(metrics?.inference_fps, 1)} />
      <Metric label="Latency" value={formatFixed(metrics?.latency_ms, 0, " ms")} />
      <Metric label="Detect" value={formatFixed(metrics?.detect_ms, 1, " ms")} />
      <Metric label="Frames processed" value={formatInt(metrics?.frames_processed)} />
      {gpu ? (
        <>
          <Divider />
          <Metric label="GPU" value={`${formatFixed(gpu.utilization, 0)}%`} />
          <Metric
            label="GPU memory"
            value={`${formatFixed(gpu.memory_used_mb / 1024, 1)} / ${formatFixed(gpu.memory_total_mb / 1024, 0)} GB`}
          />
          {gpu.temperature_c != null ? <Metric label="Temp" value={`${gpu.temperature_c}°C`} /> : null}
        </>
      ) : null}
      <span className="ml-auto shrink-0 rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground uppercase">
        {metrics?.device ? `device: ${metrics.device}` : "device: —"}
      </span>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <span className="flex shrink-0 items-baseline gap-1.5">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono tabular-nums">{value}</span>
    </span>
  );
}

function Divider() {
  return <span className="h-3.5 w-px shrink-0 bg-border" />;
}
