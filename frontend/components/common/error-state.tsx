import { AlertTriangle, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";

export function ErrorState({
  error,
  title = "Couldn't load data",
  onRetry,
  className,
}: {
  error: unknown;
  title?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center gap-2 rounded-lg border border-destructive/25 bg-destructive/5 px-6 py-8 text-center",
        className,
      )}
    >
      <AlertTriangle className="size-5 text-destructive" />
      <p className="text-sm font-medium">{title}</p>
      <p className="max-w-md text-xs text-muted-foreground">{errorMessage(error)}</p>
      {onRetry ? (
        <Button variant="outline" size="sm" className="mt-1" onClick={onRetry}>
          <RotateCw /> Retry
        </Button>
      ) : null}
    </div>
  );
}

export function InlineAlert({ tone, title, children }: { tone: "error" | "warn" | "info"; title: string; children?: React.ReactNode }) {
  const styles = {
    error: "border-destructive/30 bg-destructive/8 text-destructive",
    warn: "border-amber-300/25 bg-amber-300/8 text-amber-200",
    info: "border-sky-400/25 bg-sky-400/8 text-sky-200",
  }[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={cn("rounded-md border px-3 py-2 text-xs", styles)}>
      <span className="font-medium">{title}</span>
      {children ? <span className="text-foreground/75"> — {children}</span> : null}
    </div>
  );
}
