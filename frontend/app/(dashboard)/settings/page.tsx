"use client";

import { Loader2, Save } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ErrorState } from "@/components/common/error-state";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { useAppSettings, useSaveSettings } from "@/hooks/queries";
import { errorMessage } from "@/lib/api";
import { apiBaseUrl, wsBaseUrl } from "@/lib/config";
import { MODEL_LABEL, formatDateTime } from "@/lib/format";
import { DETECTION_MODELS, PROCESSING_FPS, type AppSettings } from "@/lib/types";
import { cn } from "@/lib/utils";

type Draft = Omit<AppSettings, "updated_at">;
const MODEL_NAME = /^[A-Za-z0-9._-]{1,120}$/;

function toDraft({ updated_at, ...rest }: AppSettings): Draft {
  void updated_at;
  return rest;
}

export default function SettingsPage() {
  const settings = useAppSettings();
  if (settings.isError) return <ErrorState error={settings.error} onRetry={() => settings.refetch()} />;
  if (!settings.data) return <Skeleton className="h-96" />;
  return <SettingsForm initial={settings.data} />;
}

function SettingsForm({ initial }: { initial: AppSettings }) {
  const save = useSaveSettings();
  const [draft, setDraft] = useState<Draft>(() => toDraft(initial));

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft({ ...draft, [key]: value });
  const modelNameValid = MODEL_NAME.test(draft.default_model_name);

  const onSave = () =>
    save.mutate(draft, {
      onSuccess: () => toast.success("Settings saved", { description: "New matches will use these defaults." }),
      onError: (error) => toast.error("Could not save settings", { description: errorMessage(error) }),
    });

  return (
    <>
      <PageHeader
        title="Settings"
        description={`Defaults for new matches · last saved ${formatDateTime(save.data?.updated_at ?? initial.updated_at)}`}
        actions={
          <Button onClick={onSave} disabled={save.isPending || !modelNameValid}>
            {save.isPending ? <Loader2 className="animate-spin" /> : <Save />} Save settings
          </Button>
        }
      />
      <div className="grid gap-5 lg:grid-cols-2">
        <section className="flex flex-col gap-5 rounded-lg border bg-card p-5">
          <h2 className="text-sm font-medium">Processing defaults</h2>
          <div className="flex flex-col gap-1.5">
            <Label>Processing FPS</Label>
            <div className="flex gap-1 rounded-lg bg-muted/50 p-1">
              {PROCESSING_FPS.map((fps) => (
                <button
                  key={fps}
                  type="button"
                  aria-pressed={draft.default_processing_fps === fps}
                  onClick={() => set("default_processing_fps", fps)}
                  className={cn(
                    "flex-1 rounded-md py-1.5 text-xs text-muted-foreground",
                    draft.default_processing_fps === fps && "bg-background text-foreground ring-1 ring-border",
                  )}
                >
                  {fps}
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Detection model</Label>
            <Select
              items={MODEL_LABEL}
              value={draft.default_detection_model}
              onValueChange={(v) => v && set("default_detection_model", v)}
            >
              <SelectTrigger className="w-full" aria-label="Default detection model">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DETECTION_MODELS.map((m) => (
                  <SelectItem key={m} value={m}>
                    {MODEL_LABEL[m]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="model-name">Model weights</Label>
            <Input
              id="model-name"
              value={draft.default_model_name}
              onChange={(e) => set("default_model_name", e.target.value)}
              className="font-mono text-xs"
              aria-invalid={!modelNameValid}
            />
            {!modelNameValid ? <p className="text-xs text-destructive">Letters, digits, dot, dash and underscore only</p> : null}
          </div>
          <div className="flex flex-col gap-2">
            <div className="flex justify-between">
              <Label>Confidence threshold</Label>
              <span className="font-mono text-xs tabular-nums">{draft.default_confidence_threshold.toFixed(2)}</span>
            </div>
            <Slider
              min={0.05}
              max={0.95}
              step={0.05}
              value={draft.default_confidence_threshold}
              onValueChange={(v) => set("default_confidence_threshold", Array.isArray(v) ? v[0] : v)}
              aria-label="Default confidence threshold"
            />
          </div>
          <div className="flex flex-col divide-y rounded-lg border">
            {(
              [
                ["default_enable_event_detection", "Event detection"],
                ["default_enable_player_tracking", "Player tracking"],
                ["default_enable_pitch_mapping", "Pitch mapping"],
              ] as const
            ).map(([key, label]) => (
              <label key={key} className="flex items-center justify-between px-3 py-2.5 text-sm">
                {label}
                <Switch checked={draft[key]} onCheckedChange={(v) => set(key, v)} />
              </label>
            ))}
          </div>
        </section>

        <section className="flex flex-col gap-4 rounded-lg border bg-card p-5">
          <h2 className="text-sm font-medium">Environment</h2>
          <dl className="grid grid-cols-[140px_1fr] gap-y-2 text-xs">
            <dt className="text-muted-foreground">API</dt>
            <dd className="truncate font-mono">{apiBaseUrl()}</dd>
            <dt className="text-muted-foreground">WebSocket</dt>
            <dd className="truncate font-mono">{wsBaseUrl()}/ws/matches/:id</dd>
          </dl>
          <p className="text-xs text-muted-foreground">
            Inference mode (mock or real), worker capacity and GPU selection are configured on the worker service with the{" "}
            <code className="font-mono">INFERENCE_MODE</code> and <code className="font-mono">MAX_CONCURRENT_MATCHES</code>{" "}
            environment variables. See the System page for the device each worker selected.
          </p>
        </section>
      </div>
    </>
  );
}
