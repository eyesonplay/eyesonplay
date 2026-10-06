"use client";

import { Loader2, Pause, Play, RotateCcw, Square } from "lucide-react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { Button } from "@/components/ui/button";
import { useProcessingAction } from "@/hooks/queries";
import { errorMessage, type ProcessingAction } from "@/lib/api";
import type { MatchStatus } from "@/lib/types";

const CAN: Record<ProcessingAction | "resume", ReadonlySet<MatchStatus>> = {
  start: new Set(["ready", "completed", "failed"]),
  resume: new Set(["paused"]),
  pause: new Set(["starting", "processing"]),
  stop: new Set(["starting", "processing", "paused"]),
  restart: new Set(["starting", "processing", "paused", "completed", "failed"]),
};

const DONE: Record<ProcessingAction, string> = {
  start: "Processing started",
  pause: "Processing paused",
  stop: "Processing stopped",
  restart: "Processing restarted",
};

export function ProcessingControls({ matchId, status, hasSource }: { matchId: string; status: MatchStatus; hasSource: boolean }) {
  const mutation = useProcessingAction(matchId);
  const pending = mutation.isPending ? mutation.variables : null;

  const run = (action: ProcessingAction, label = DONE[action]) =>
    mutation.mutate(action, {
      onSuccess: () => toast.success(label),
      onError: (error) => toast.error(`Could not ${action} processing`, { description: errorMessage(error) }),
    });

  const icon = (action: ProcessingAction, Icon: typeof Play) =>
    pending === action ? <Loader2 className="animate-spin" /> : <Icon />;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {CAN.resume.has(status) ? (
        <Button size="sm" onClick={() => run("start", "Processing resumed")} disabled={!!pending}>
          {icon("start", Play)} Resume
        </Button>
      ) : (
        <Button size="sm" onClick={() => run("start")} disabled={!!pending || !CAN.start.has(status) || !hasSource}>
          {icon("start", Play)} Start
        </Button>
      )}
      <Button size="sm" variant="outline" onClick={() => run("pause")} disabled={!!pending || !CAN.pause.has(status)}>
        {icon("pause", Pause)} Pause
      </Button>
      <Button size="sm" variant="outline" onClick={() => run("stop")} disabled={!!pending || !CAN.stop.has(status)}>
        {icon("stop", Square)} Stop
      </Button>
      <ConfirmDialog
        trigger={
          <Button size="sm" variant="outline" disabled={!!pending || !CAN.restart.has(status) || !hasSource}>
            {icon("restart", RotateCcw)} Restart
          </Button>
        }
        title="Restart processing?"
        description="A new session starts from the beginning of the source. Events detected so far for this match are cleared."
        confirmLabel="Restart"
        onConfirm={() => run("restart")}
      />
    </div>
  );
}
