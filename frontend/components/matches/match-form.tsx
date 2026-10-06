"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, Play, Save } from "lucide-react";
import type { ReactNode } from "react";
import { Controller, useForm, type UseFormReturn } from "react-hook-form";

import { UploadField } from "@/components/matches/upload-field";
import { matchFormSchema, type MatchFormValues } from "@/components/matches/form-schema";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { ApiError } from "@/lib/api";
import { SOURCE_LABEL, SPORT_LABEL, modelLabel, sideLabels } from "@/lib/format";
import { DETECTION_MODELS, PROCESSING_FPS, SOURCE_TYPES, SPORTS, type SourceType } from "@/lib/types";
import { cn } from "@/lib/utils";

const PLACEHOLDER: Record<Exclude<SourceType, "upload">, string> = {
  hls: "https://example.com/live-match.m3u8",
  rtmp: "rtmp://ingest.example.com/live/match",
  url: "https://example.com/full-match.mp4",
};

export type SubmitIntent = "save" | "start";

export function useMatchForm(defaults: MatchFormValues) {
  return useForm<MatchFormValues>({ resolver: zodResolver(matchFormSchema), defaultValues: defaults, mode: "onBlur" });
}

/** Maps API validation details (`loc: ["body", field]`) onto form fields. */
export function applyServerErrors(form: UseFormReturn<MatchFormValues>, error: unknown): boolean {
  if (!(error instanceof ApiError)) return false;
  let applied = false;
  for (const issue of error.fieldIssues) {
    const field = issue.loc.at(-1);
    if (typeof field === "string" && field in form.getValues()) {
      form.setError(field as keyof MatchFormValues, { message: issue.msg });
      applied = true;
    }
  }
  return applied;
}

export function MatchForm({
  form,
  onSubmit,
  submitting,
  mode,
  locked,
}: {
  form: UseFormReturn<MatchFormValues>;
  onSubmit: (values: MatchFormValues, intent: SubmitIntent) => void;
  submitting: SubmitIntent | null;
  mode: "create" | "edit";
  locked?: boolean;
}) {
  const { register, control, watch, setValue, formState } = form;
  const errors = formState.errors;
  const sourceType = watch("video_source_type");
  const sport = watch("sport");
  const sides = sideLabels(sport);
  const tennis = sport === "tennis";
  const model = watch("detection_model");
  const hasSource = watch("video_source").trim().length > 0;
  const submit = (intent: SubmitIntent) => form.handleSubmit((values) => onSubmit(values, intent));

  return (
    <form onSubmit={submit("save")} className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]" noValidate>
      <div className="flex flex-col gap-5">
        <Section title="Match information">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Controller
                control={control}
                name="sport"
                render={({ field }) => (
                  <Segmented
                    label="Sport"
                    value={field.value}
                    options={SPORTS.map((s) => ({ value: s, label: SPORT_LABEL[s] }))}
                    onChange={(value) => {
                      field.onChange(value);
                      // Tennis events need a high frame rate (fast ball, short bounces).
                      if (value === "tennis" && form.getValues("processing_fps") < 25) setValue("processing_fps", 25);
                    }}
                  />
                )}
              />
            </div>
            <Field label="Match name" error={errors.name?.message} className="sm:col-span-2">
              <Input
                {...register("name")}
                placeholder={tennis ? "Alcaraz vs Sinner" : "Arsenal vs Chelsea"}
                aria-invalid={!!errors.name}
              />
            </Field>
            <Field label={sides.home} error={errors.home_team?.message}>
              <Input {...register("home_team")} placeholder={tennis ? "Alcaraz" : "Arsenal"} aria-invalid={!!errors.home_team} />
            </Field>
            <Field label={sides.away} error={errors.away_team?.message}>
              <Input {...register("away_team")} placeholder={tennis ? "Sinner" : "Chelsea"} aria-invalid={!!errors.away_team} />
            </Field>
            <Field label="Competition" hint="Optional" error={errors.competition?.message}>
              <Input {...register("competition")} placeholder={tennis ? "ATP Finals" : "Premier League"} />
            </Field>
            <Field label="Match date" error={errors.match_date?.message}>
              <Input type="datetime-local" {...register("match_date")} aria-invalid={!!errors.match_date} />
            </Field>
          </div>
        </Section>

        <Section
          title="Video source"
          description="Live streams are processed continuously; nothing is downloaded up front. Leave empty to save a draft."
        >
          <fieldset disabled={locked} className="flex flex-col gap-4">
            <Controller
              control={control}
              name="video_source_type"
              render={({ field }) => (
                <Segmented
                  label="Source type"
                  value={field.value}
                  options={SOURCE_TYPES.map((t) => ({ value: t, label: SOURCE_LABEL[t] }))}
                  onChange={(value) => {
                    field.onChange(value);
                    setValue("video_source", "", { shouldValidate: false });
                  }}
                />
              )}
            />
            {sourceType === "upload" ? (
              <Field label="Video file" error={errors.video_source?.message}>
                <UploadField
                  value={watch("video_source")}
                  disabled={locked}
                  invalid={!!errors.video_source}
                  onUploaded={(path) => setValue("video_source", path, { shouldValidate: true, shouldDirty: true })}
                />
              </Field>
            ) : (
              <Field
                label={sourceType === "hls" ? "HLS playlist URL" : sourceType === "rtmp" ? "RTMP URL" : "Video URL"}
                error={errors.video_source?.message}
                hint={sourceType === "rtmp" ? "Browsers can't play RTMP; the dashboard shows detections without video." : undefined}
              >
                <Input
                  {...register("video_source")}
                  placeholder={PLACEHOLDER[sourceType]}
                  className="font-mono text-xs"
                  aria-invalid={!!errors.video_source}
                />
              </Field>
            )}
          </fieldset>
        </Section>
      </div>

      <div className="flex flex-col gap-5">
        <Section title="Processing">
          <fieldset disabled={locked} className="flex flex-col gap-4">
            <Controller
              control={control}
              name="processing_fps"
              render={({ field }) => (
                <Segmented
                  label="Processing FPS"
                  value={String(field.value)}
                  options={PROCESSING_FPS.map((f) => ({ value: String(f), label: String(f) }))}
                  onChange={(v) => field.onChange(Number(v))}
                />
              )}
            />
            <Field label="Detection model">
              <Controller
                control={control}
                name="detection_model"
                render={({ field }) => (
                  <Select
                    items={Object.fromEntries(DETECTION_MODELS.map((m) => [m, modelLabel(sport, m)]))}
                    value={field.value}
                    onValueChange={(v) => v && field.onChange(v)}
                  >
                    <SelectTrigger className="w-full" aria-label="Detection model">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {DETECTION_MODELS.map((m) => (
                        <SelectItem key={m} value={m}>
                          {modelLabel(sport, m)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>
            <Field
              label="Model weights"
              hint="Used in real inference mode, e.g. yolov8n or a football fine-tune"
              error={errors.model_name?.message}
            >
              <Input {...register("model_name")} className="font-mono text-xs" />
            </Field>
            <Controller
              control={control}
              name="confidence_threshold"
              render={({ field }) => (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <Label>Confidence threshold</Label>
                    <span className="font-mono text-xs tabular-nums">{field.value.toFixed(2)}</span>
                  </div>
                  <Slider
                    min={0.05}
                    max={0.95}
                    step={0.05}
                    value={field.value}
                    onValueChange={(v) => field.onChange(Array.isArray(v) ? v[0] : v)}
                    aria-label="Confidence threshold"
                  />
                </div>
              )}
            />
            <Field
              label="Match clock at video start"
              hint="mm:ss — e.g. 45:00 for a second-half stream"
              error={errors.kickoff_clock?.message}
            >
              <Input {...register("kickoff_clock")} className="w-28 font-mono text-xs tabular-nums" />
            </Field>
            <div className="flex flex-col divide-y rounded-lg border">
              <Toggle
                form={form}
                name="enable_event_detection"
                label="Event detection"
                hint={tennis ? "Serve, hits, bounces (in/out), faults, points" : "Possession, passes, shots, ball out"}
              />
              <Toggle
                form={form}
                name="enable_player_tracking"
                label="Player tracking"
                hint={model === "ball" ? "Requires a model that detects players" : "Stable track IDs per player"}
                forcedOff={model === "ball"}
              />
              <Toggle
                form={form}
                name="enable_pitch_mapping"
                label={tennis ? "Court mapping" : "Pitch mapping"}
                hint={
                  model !== "ball_players_pitch"
                    ? `Requires the ${modelLabel(sport, "ball_players_pitch")} model`
                    : tennis
                      ? "Court coordinates for bounces and in/out calls"
                      : "Normalised 0–100 pitch coordinates"
                }
                forcedOff={model !== "ball_players_pitch"}
              />
            </div>
          </fieldset>
        </Section>

        <div className="flex flex-col gap-2 xl:sticky xl:top-6">
          <Button type="button" size="lg" disabled={!!submitting || locked || !hasSource} onClick={submit("start")}>
            {submitting === "start" ? <Loader2 className="animate-spin" /> : <Play />}
            {mode === "create" ? "Create & start processing" : "Save & start processing"}
          </Button>
          <Button type="submit" size="lg" variant="outline" disabled={!!submitting}>
            {submitting === "save" ? <Loader2 className="animate-spin" /> : <Save />}
            {mode === "create" ? (hasSource ? "Create match" : "Save as draft") : "Save changes"}
          </Button>
          {!hasSource ? <p className="text-center text-xs text-muted-foreground">Add a video source to enable processing.</p> : null}
        </div>
      </div>
    </form>
  );
}

function Section({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border bg-card p-4 sm:p-5">
      <h2 className="text-sm font-medium">{title}</h2>
      {description ? <p className="mt-0.5 text-xs text-muted-foreground">{description}</p> : null}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Field({
  label,
  hint,
  error,
  className,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <Label>{label}</Label>
      {children}
      {error ? (
        <p className="text-xs text-destructive">{error}</p>
      ) : hint ? (
        <p className="text-xs text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}

function Segmented({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-1 rounded-lg bg-muted/50 p-1">
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={o.value === value}
            onClick={() => onChange(o.value)}
            className={cn(
              "flex-1 rounded-md px-2.5 py-1.5 text-xs whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground",
              o.value === value && "bg-background text-foreground shadow-sm ring-1 ring-border",
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

type ToggleName = "enable_event_detection" | "enable_player_tracking" | "enable_pitch_mapping";

function Toggle({
  form,
  name,
  label,
  hint,
  forcedOff,
}: {
  form: UseFormReturn<MatchFormValues>;
  name: ToggleName;
  label: string;
  hint: string;
  forcedOff?: boolean;
}) {
  return (
    <Controller
      control={form.control}
      name={name}
      render={({ field }) => (
        <label className={cn("flex items-center justify-between gap-3 px-3 py-2.5", forcedOff && "opacity-60")}>
          <span>
            <span className="block text-sm">{label}</span>
            <span className="block text-xs text-muted-foreground">{hint}</span>
          </span>
          <Switch checked={!forcedOff && field.value} disabled={forcedOff} onCheckedChange={(v) => field.onChange(v)} />
        </label>
      )}
    />
  );
}
