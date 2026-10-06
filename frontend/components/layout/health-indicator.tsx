"use client";

import Link from "next/link";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useHealth } from "@/hooks/queries";
import { cn } from "@/lib/utils";

type Tone = "ok" | "warn" | "down" | "unknown";

const DOT: Record<Tone, string> = {
  ok: "bg-primary",
  warn: "bg-amber-400",
  down: "bg-destructive",
  unknown: "bg-muted-foreground/50",
};

export function HealthIndicator({ variant }: { variant: "sidebar" | "compact" }) {
  const { data, isError, isPending } = useHealth();

  let tone: Tone = "unknown";
  let label = "Checking services…";
  let detail = "";
  if (isError) {
    tone = "down";
    label = "API unreachable";
    detail = "The dashboard cannot reach the backend API.";
  } else if (data) {
    const problems = [!data.database.ok && "database", !data.redis.ok && "Redis"].filter(Boolean);
    if (problems.length) {
      tone = "down";
      label = `${problems.join(" & ")} unavailable`;
      detail = [data.database.detail, data.redis.detail].filter(Boolean).join(" · ");
    } else if (data.workers === 0) {
      tone = "warn";
      label = "No inference worker";
      detail = "Processing cannot start until a worker is running.";
    } else {
      tone = "ok";
      label = `${data.workers} worker${data.workers === 1 ? "" : "s"} online`;
      detail = "API, database and Redis are healthy.";
    }
  }

  const content = (
    <Link href="/system" className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground">
      <span className={cn("size-2 rounded-full", DOT[tone], tone === "ok" && "shadow-[0_0_8px] shadow-primary/60")} />
      <span className={cn(variant === "compact" && "hidden sm:inline")}>{isPending ? "Checking…" : label}</span>
    </Link>
  );

  return (
    <Tooltip>
      <TooltipTrigger render={<div />}>{content}</TooltipTrigger>
      <TooltipContent side="top">{detail || label}</TooltipContent>
    </Tooltip>
  );
}
