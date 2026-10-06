import { z } from "zod";

import { apiBaseUrl } from "@/lib/config";
import {
  AppSettingsSchema,
  DashboardSummarySchema,
  EventRecordSchema,
  GpuSchema,
  HealthSchema,
  MatchSchema,
  ModelSchema,
  SessionSchema,
  UploadSchema,
  WorkerSchema,
  type AppSettings,
  type DetectionModel,
  type Sport,
  type Match,
  type SourceType,
  type Upload,
} from "@/lib/types";

export interface FieldIssue {
  loc: (string | number)[];
  msg: string;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
  }

  get fieldIssues(): FieldIssue[] {
    return Array.isArray(this.details) ? (this.details as FieldIssue[]) : [];
  }
}

const ErrorEnvelope = z.object({
  error: z.object({ code: z.string(), message: z.string(), details: z.unknown().optional() }),
});

const meta = z.record(z.string(), z.unknown()).nullable().optional();

interface Page<T> {
  data: T;
  meta: Record<string, unknown> | null;
}

async function request<S extends z.ZodType>(path: string, schema: S, init?: RequestInit): Promise<Page<z.infer<S>>> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}), ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the API. Is the backend running?");
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const parsed = ErrorEnvelope.safeParse(body);
    if (parsed.success) {
      const { code, message, details } = parsed.data.error;
      throw new ApiError(response.status, code, message, details ?? null);
    }
    throw new ApiError(response.status, "http_error", `Request failed (${response.status})`);
  }
  const envelope = z.object({ data: z.unknown(), meta }).safeParse(body);
  const parsed = envelope.success ? schema.safeParse(envelope.data.data) : null;
  if (!envelope.success || !parsed?.success) {
    throw new ApiError(response.status, "invalid_response", "The API returned an unexpected response");
  }
  return { data: parsed.data as z.infer<S>, meta: envelope.data.meta ?? null };
}

const json = (body: unknown): RequestInit => ({ body: JSON.stringify(body) });

/* -------------------------------- matches -------------------------------- */

export interface MatchInput {
  sport: Sport;
  name: string;
  home_team: string;
  away_team: string;
  competition: string | null;
  match_date: string;
  video_source_type: SourceType | null;
  video_source: string | null;
  processing_fps: number;
  detection_model: DetectionModel;
  model_name: string;
  confidence_threshold: number;
  enable_event_detection: boolean;
  enable_player_tracking: boolean;
  enable_pitch_mapping: boolean;
  kickoff_offset_seconds: number;
}

export interface MatchListParams {
  status?: string[];
  q?: string;
  limit?: number;
  offset?: number;
}

function query(params: Record<string, string | number | string[] | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    for (const v of Array.isArray(value) ? value : [value]) search.append(key, String(v));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

export const api = {
  listMatches: (params: MatchListParams = {}) =>
    request(`/api/matches${query({ ...params })}`, z.array(MatchSchema)),
  getMatch: async (id: string) => (await request(`/api/matches/${id}`, MatchSchema)).data,
  createMatch: async (input: MatchInput) =>
    (await request("/api/matches", MatchSchema, { method: "POST", ...json(input) })).data,
  updateMatch: async (id: string, input: Partial<MatchInput>) =>
    (await request(`/api/matches/${id}`, MatchSchema, { method: "PATCH", ...json(input) })).data,
  deleteMatch: async (id: string) =>
    (await request(`/api/matches/${id}`, z.object({ id: z.string() }), { method: "DELETE" })).data,
  listSessions: async (id: string) => (await request(`/api/matches/${id}/sessions`, z.array(SessionSchema))).data,

  processing: async (id: string, action: ProcessingAction): Promise<Match> =>
    (await request(`/api/matches/${id}/${action}`, MatchSchema, { method: "POST" })).data,

  listEvents: (params: { matchId?: string; groups?: string[]; limit?: number; beforeId?: number }) => {
    const path = params.matchId ? `/api/matches/${params.matchId}/events` : "/api/events";
    return request(
      `${path}${query({ group: params.groups, limit: params.limit, before_id: params.beforeId })}`,
      z.array(EventRecordSchema),
    );
  },
  exportUrl: (id: string) => `${apiBaseUrl()}/api/matches/${id}/events/export`,

  health: async () => (await request("/api/system/health", HealthSchema)).data,
  workers: async () => (await request("/api/system/workers", z.array(WorkerSchema))).data,
  gpus: async () => (await request("/api/system/gpu", z.array(GpuSchema))).data,
  models: async () => (await request("/api/models", z.array(ModelSchema))).data,
  summary: async () => (await request("/api/dashboard/summary", DashboardSummarySchema)).data,

  getSettings: async () => (await request("/api/settings", AppSettingsSchema)).data,
  saveSettings: async (input: Omit<AppSettings, "updated_at">) =>
    (await request("/api/settings", AppSettingsSchema, { method: "PUT", ...json(input) })).data,
};

export type ProcessingAction = "start" | "pause" | "stop" | "restart";

/** Multipart upload with progress (fetch has no upload progress events). */
export function uploadVideo(file: File, onProgress: (fraction: number) => void, signal?: AbortSignal): Promise<Upload> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${apiBaseUrl()}/api/uploads`);
    xhr.responseType = "json";
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onerror = () => reject(new ApiError(0, "network_error", "Upload failed: cannot reach the API"));
    xhr.onabort = () => reject(new ApiError(0, "aborted", "Upload cancelled"));
    xhr.onload = () => {
      const body: unknown = xhr.response;
      if (xhr.status >= 200 && xhr.status < 300) {
        const parsed = z.object({ data: UploadSchema }).safeParse(body);
        if (parsed.success) return resolve(parsed.data.data);
        return reject(new ApiError(xhr.status, "invalid_response", "Unexpected upload response"));
      }
      const err = ErrorEnvelope.safeParse(body);
      reject(
        err.success
          ? new ApiError(xhr.status, err.data.error.code, err.data.error.message, err.data.error.details ?? null)
          : new ApiError(xhr.status, "http_error", `Upload failed (${xhr.status})`),
      );
    };
    signal?.addEventListener("abort", () => xhr.abort());
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong";
}
