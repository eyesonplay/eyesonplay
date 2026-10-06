/**
 * API/WebSocket base URLs. NEXT_PUBLIC_API_URL wins when set at build time;
 * otherwise the API is assumed on port 8000 of the host serving the dashboard,
 * which works for `docker compose up` and local development alike.
 */
const API_PORT = "8000";

export function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL;
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
