import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiKeyCreatedSchema, ApiKeySchema } from "@/lib/api";
import { loginPath, safeNext } from "@/lib/auth-redirect";
import { apiBaseUrl, wsBaseUrl } from "@/lib/config";

describe("after-login redirect", () => {
  it("returns to the page the user was on", () => {
    expect(loginPath("/matches/m1/live?tab=events")).toBe("/login?next=%2Fmatches%2Fm1%2Flive%3Ftab%3Devents");
    expect(safeNext("/matches/m1/live?tab=events")).toBe("/matches/m1/live?tab=events");
  });

  it("never redirects off-site (open redirect)", () => {
    for (const next of [
      "https://evil.example",
      "//evil.example/x",
      "/\\evil.example",
      "javascript:alert(1)",
      "",
      null,
    ]) {
      expect(safeNext(next)).toBe("/");
    }
  });

  it("does not send the login page back to itself", () => {
    expect(loginPath("/login?next=%2F")).toBe("/login");
    expect(safeNext("/login")).toBe("/");
  });
});

describe("same-origin API (production behind a reverse proxy)", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("uses the dashboard's own origin", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "same-origin");
    vi.stubGlobal("window", {
      location: { origin: "https://eyesonplay.example", protocol: "https:", hostname: "eyesonplay.example" },
    });

    expect(apiBaseUrl()).toBe("https://eyesonplay.example");
    expect(wsBaseUrl()).toBe("wss://eyesonplay.example");
    vi.unstubAllGlobals();
  });
});

describe("API key responses", () => {
  const listed = {
    id: "key_1",
    name: "riosport",
    prefix: "psk_AbCdEfGh",
    created_at: "2026-10-06T12:00:00Z",
    last_used_at: null,
    revoked_at: null,
  };

  it("never expects the full key when listing", () => {
    expect(ApiKeySchema.parse({ ...listed, key: "psk_secret" })).not.toHaveProperty("key");
  });

  it("requires the full key on creation, the only time it is shown", () => {
    expect(ApiKeyCreatedSchema.safeParse(listed).success).toBe(false);
    expect(ApiKeyCreatedSchema.parse({ ...listed, key: "psk_secret" }).key).toBe("psk_secret");
  });
});
