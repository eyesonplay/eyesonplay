import { z } from "zod";

export const SPORTS = ["football", "tennis"] as const;
export const SportSchema = z.enum(SPORTS);
export type Sport = z.infer<typeof SportSchema>;

export const MATCH_STATUSES = ["draft", "ready", "starting", "processing", "paused", "completed", "failed"] as const;
export const SOURCE_TYPES = ["hls", "rtmp", "url", "upload"] as const;
export const DETECTION_MODELS = ["ball", "ball_players", "ball_players_pitch"] as const;
export const PROCESSING_FPS = [5, 10, 15, 25, 30] as const;

export const MatchStatusSchema = z.enum(MATCH_STATUSES);
export const SourceTypeSchema = z.enum(SOURCE_TYPES);
export const DetectionModelSchema = z.enum(DETECTION_MODELS);

export type MatchStatus = z.infer<typeof MatchStatusSchema>;
export type SourceType = z.infer<typeof SourceTypeSchema>;
export type DetectionModel = z.infer<typeof DetectionModelSchema>;

export const LiveMetricsSchema = z.object({
  inference_fps: z.number().nullable(),
  latency_ms: z.number().nullable(),
  frames_processed: z.number().nullable(),
  device: z.string().nullable(),
});

export const MatchSchema = z.object({
  id: z.string(),
  sport: SportSchema.default("football"),
  name: z.string(),
  home_team: z.string(),
  away_team: z.string(),
  competition: z.string().nullable(),
  match_date: z.string(),
  video_source_type: SourceTypeSchema.nullable(),
  video_source: z.string().nullable(),
  status: MatchStatusSchema,
  status_message: z.string().nullable(),
  last_error: z.string().nullable(),
  processing_fps: z.number(),
  detection_model: DetectionModelSchema,
  model_name: z.string(),
  confidence_threshold: z.number(),
  enable_event_detection: z.boolean(),
  enable_player_tracking: z.boolean(),
  enable_pitch_mapping: z.boolean(),
  kickoff_offset_seconds: z.number(),
  current_session_id: z.string().nullable(),
  event_count: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
  live: LiveMetricsSchema.nullable(),
});
export type Match = z.infer<typeof MatchSchema>;

const PointSchema = z.object({ x: z.number(), y: z.number() });
export type Point = z.infer<typeof PointSchema>;

/** Event payload as produced by the event engine; extra keys vary by type. */
export const EventPayloadSchema = z.looseObject({
  event_id: z.string(),
  match_id: z.string(),
  timestamp: z.number(),
  video_timestamp: z.number(),
  frame: z.number().optional(),
  match_clock: z.string(),
  event: z.string(),
  confidence: z.number(),
  team: z.string().nullable().optional(),
  player: z.string().nullable().optional(),
  ball: z
    .object({ pixel: PointSchema, pitch: PointSchema.nullable(), confidence: z.number() })
    .nullable()
    .optional(),
});
export type EventPayload = z.infer<typeof EventPayloadSchema>;

export const EventRecordSchema = z.object({
  id: z.number(),
  event_uid: z.string(),
  match_id: z.string(),
  session_id: z.string().nullable(),
  event_type: z.string(),
  video_timestamp: z.number(),
  match_clock: z.string(),
  confidence: z.number(),
  payload: EventPayloadSchema,
  created_at: z.string(),
});
export type EventRecord = z.infer<typeof EventRecordSchema>;

export const SessionSchema = z.object({
  id: z.string(),
  match_id: z.string(),
  started_at: z.string(),
  stopped_at: z.string().nullable(),
  status: z.string(),
  frames_processed: z.number(),
  average_fps: z.number().nullable(),
  average_latency: z.number().nullable(),
  worker_id: z.string().nullable(),
  device: z.string().nullable(),
  error: z.string().nullable(),
});
export type ProcessingSession = z.infer<typeof SessionSchema>;

const ComponentHealthSchema = z.object({ ok: z.boolean(), detail: z.string().nullable() });
export const HealthSchema = z.object({
  status: z.enum(["ok", "degraded"]),
  database: ComponentHealthSchema,
  redis: ComponentHealthSchema,
  workers: z.number(),
});
export type Health = z.infer<typeof HealthSchema>;

export const GpuInfoSchema = z.object({
  index: z.number(),
  name: z.string(),
  utilization: z.number(),
  memory_used_mb: z.number(),
  memory_total_mb: z.number(),
  temperature_c: z.number().nullable(),
});
export type GpuInfo = z.infer<typeof GpuInfoSchema>;

export const GpuSchema = GpuInfoSchema.extend({ worker_id: z.string() });
export type Gpu = z.infer<typeof GpuSchema>;

export const ModelSchema = z.object({
  name: z.string(),
  family: z.string(),
  description: z.string().nullable(),
  device: z.string(),
  loaded: z.boolean(),
  worker_id: z.string(),
  classes: z.array(z.string()).nullable(),
});
export type Model = z.infer<typeof ModelSchema>;

export const WorkerSchema = z.object({
  worker_id: z.string(),
  mode: z.string(),
  device: z.string(),
  active_matches: z.array(z.string()),
  capacity: z.number(),
  started_at: z.number(),
  last_seen: z.number(),
  gpu: z.array(GpuInfoSchema).nullable(),
  models: z.array(z.record(z.string(), z.unknown())),
});
export type Worker = z.infer<typeof WorkerSchema>;

export const DashboardSummarySchema = z.object({
  active_matches: z.number(),
  processing_matches: z.number(),
  events_today: z.number(),
  gpu_utilization: z.number().nullable(),
  average_inference_fps: z.number().nullable(),
  average_latency_ms: z.number().nullable(),
  devices: z.array(z.string()),
  workers: z.number(),
});
export type DashboardSummary = z.infer<typeof DashboardSummarySchema>;

export const AppSettingsSchema = z.object({
  default_processing_fps: z.number(),
  default_detection_model: DetectionModelSchema,
  default_model_name: z.string(),
  default_confidence_threshold: z.number(),
  default_enable_event_detection: z.boolean(),
  default_enable_player_tracking: z.boolean(),
  default_enable_pitch_mapping: z.boolean(),
  updated_at: z.string(),
});
export type AppSettings = z.infer<typeof AppSettingsSchema>;

export const UploadSchema = z.object({
  video_source: z.string(),
  original_filename: z.string(),
  size_bytes: z.number(),
  duration_s: z.number().nullable(),
  width: z.number().nullable(),
  height: z.number().nullable(),
});
export type Upload = z.infer<typeof UploadSchema>;

/* ------------------------------ live feed ------------------------------ */

export interface BallState {
  track_id: number;
  bbox: [number, number, number, number];
  pixel: Point;
  pitch: Point | null;
  confidence: number;
  velocity: Point;
  speed: number;
  predicted: boolean;
}

export interface TrailPoint {
  t: number;
  x: number;
  y: number;
  pitch: Point | null;
}

export interface PlayerDetection {
  track_id: number | null;
  class: "player" | "goalkeeper" | "referee";
  bbox: [number, number, number, number];
  confidence: number;
  pitch: Point | null;
  team?: number | null; // 0 = A, 1 = B, by shirt colour; null when unassigned
}

export interface TeamInfo {
  id: number;
  label: "A" | "B";
  color: string; // kit colour as seen on video, "#rrggbb"
}

export interface CalibrationInfo {
  state: "fixed" | "ok" | "tracking" | "searching" | "no_court" | "no_model" | "disabled";
  keypoints?: number;
  error_px?: number | null;
  age_s?: number | null;
  pending?: boolean; // a new fit is waiting for a second agreeing fit
  pitch_in_view?: boolean; // false during graphics, close-ups and crowd shots
}

export interface FrameData {
  frame_number: number;
  video_timestamp: number;
  timestamp: number;
  width: number;
  height: number;
  coordinate_mode: "pitch" | "pixel";
  calibration?: CalibrationInfo;
  teams?: TeamInfo[];
  ball: BallState | null;
  trail: TrailPoint[];
  players: PlayerDetection[];
  latency_ms: number;
}

export interface MetricsData {
  source_fps: number | null;
  inference_fps: number;
  detect_ms: number;
  event_ms: number;
  latency_ms: number;
  frames_processed: number;
  events_emitted: number;
  device: string;
  gpu: GpuInfo | null;
}

export interface StatusData {
  status: string;
  message: string | null;
  error?: string | null;
  origin?: "api" | "snapshot";
  worker_id?: string;
  device?: string;
}

export type LiveMessage =
  | { type: "status"; data: StatusData }
  | { type: "frame"; data: FrameData }
  | { type: "ball"; data: BallState | null }
  | { type: "players"; data: PlayerDetection[] }
  | { type: "event"; data: EventPayload }
  | { type: "metrics"; data: MetricsData }
  | { type: "error"; data: { message: string } };

export type LiveEnvelope = LiveMessage & {
  match_id: string;
  session_id: string | null;
  ts: number;
  seq: number;
};
