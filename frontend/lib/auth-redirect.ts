/** Where to send a signed-out user, and where to return them after signing in. */

export const LOGIN_PATH = "/login";

/** A same-site path to return to after login; anything else falls back to "/". */
export function safeNext(next: string | null | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return "/";
  if (next === LOGIN_PATH || next.startsWith(`${LOGIN_PATH}?`)) return "/";
  return next;
}

export function loginPath(current: string): string {
  const next = safeNext(current);
  return next === "/" && current.startsWith(LOGIN_PATH) ? LOGIN_PATH : `${LOGIN_PATH}?next=${encodeURIComponent(next)}`;
}

/** Send the browser to the login page, keeping the current page to come back to. */
export function redirectToLogin(): void {
  if (typeof window === "undefined" || window.location.pathname === LOGIN_PATH) return;
  window.location.assign(loginPath(window.location.pathname + window.location.search));
}
