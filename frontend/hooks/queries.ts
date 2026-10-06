"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type MatchInput, type MatchListParams, type ProcessingAction } from "@/lib/api";
import type { AppSettings, Match } from "@/lib/types";

export const queryKeys = {
  matches: ["matches"] as const,
  matchList: (params: MatchListParams) => ["matches", "list", params] as const,
  match: (id: string) => ["matches", "detail", id] as const,
  sessions: (id: string) => ["matches", "sessions", id] as const,
  events: (params: object) => ["events", params] as const,
  summary: ["dashboard", "summary"] as const,
  health: ["system", "health"] as const,
  workers: ["system", "workers"] as const,
  gpus: ["system", "gpus"] as const,
  models: ["models"] as const,
  settings: ["settings"] as const,
};

const LIVE_REFRESH_MS = 3_000;
const SLOW_REFRESH_MS = 10_000;

export function useMatches(params: MatchListParams = {}) {
  return useQuery({
    queryKey: queryKeys.matchList(params),
    queryFn: () => api.listMatches(params),
    refetchInterval: LIVE_REFRESH_MS,
    placeholderData: keepPreviousData,
  });
}

export function useMatch(id: string) {
  return useQuery({ queryKey: queryKeys.match(id), queryFn: () => api.getMatch(id), refetchInterval: SLOW_REFRESH_MS });
}

export function useSessions(id: string) {
  return useQuery({ queryKey: queryKeys.sessions(id), queryFn: () => api.listSessions(id), refetchInterval: SLOW_REFRESH_MS });
}

export function useSummary() {
  return useQuery({ queryKey: queryKeys.summary, queryFn: api.summary, refetchInterval: LIVE_REFRESH_MS });
}

export function useHealth() {
  return useQuery({ queryKey: queryKeys.health, queryFn: api.health, refetchInterval: SLOW_REFRESH_MS, retry: false });
}

export function useWorkers() {
  return useQuery({ queryKey: queryKeys.workers, queryFn: api.workers, refetchInterval: LIVE_REFRESH_MS });
}

export function useGpus() {
  return useQuery({ queryKey: queryKeys.gpus, queryFn: api.gpus, refetchInterval: LIVE_REFRESH_MS });
}

export function useModels() {
  return useQuery({ queryKey: queryKeys.models, queryFn: api.models, refetchInterval: SLOW_REFRESH_MS });
}

export function useAppSettings() {
  return useQuery({ queryKey: queryKeys.settings, queryFn: api.getSettings });
}

function useInvalidateMatches() {
  const client = useQueryClient();
  return (match?: Match) => {
    if (match) client.setQueryData(queryKeys.match(match.id), match);
    void client.invalidateQueries({ queryKey: queryKeys.matches });
    void client.invalidateQueries({ queryKey: queryKeys.summary });
  };
}

export function useCreateMatch() {
  const invalidate = useInvalidateMatches();
  return useMutation({ mutationFn: (input: MatchInput) => api.createMatch(input), onSuccess: invalidate });
}

export function useUpdateMatch(id: string) {
  const invalidate = useInvalidateMatches();
  return useMutation({ mutationFn: (input: Partial<MatchInput>) => api.updateMatch(id, input), onSuccess: invalidate });
}

export function useDeleteMatch() {
  const invalidate = useInvalidateMatches();
  return useMutation({ mutationFn: (id: string) => api.deleteMatch(id), onSuccess: () => invalidate() });
}

export function useProcessingAction(id: string) {
  const invalidate = useInvalidateMatches();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (action: ProcessingAction) => api.processing(id, action),
    onSuccess: (match) => {
      invalidate(match);
      void client.invalidateQueries({ queryKey: queryKeys.sessions(id) });
    },
  });
}

export function useSaveSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: Omit<AppSettings, "updated_at">) => api.saveSettings(input),
    onSuccess: (saved) => client.setQueryData(queryKeys.settings, saved),
  });
}
