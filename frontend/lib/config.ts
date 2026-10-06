/**
 * API/WebSocket base URLs. NEXT_PUBLIC_API_URL wins when set at build time:
 * a URL, or "same-origin" when a reverse proxy serves the API on the
 * dashboard's own origin (production). Otherwise the API is assumed on port
 * 8000 of the host serving the dashboard (`docker compose up`, local dev).
 */
const API_PORT = "8000";
const SAME_ORIGIN = "same-origin";

export function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL;
  if (configured === SAME_ORIGIN) {
    return typeof window === "undefined" ? `http://localhost:${API_PORT}` : window.location.origin;
  }
  if (configured) return configured.replace(/\/$/, "");
  if (typeof window === "undefined") return `http://localhost:${API_PORT}`;
  return `${window.location.protocol}//${window.location.hostname}:${API_PORT}`;
}

export function wsBaseUrl(): string {
  return apiBaseUrl().replace(/^http/, "ws");
}

export function mediaUrl(relativePath: string): string {
  return `${apiBaseUrl()}/media/${relativePath}`;
}
