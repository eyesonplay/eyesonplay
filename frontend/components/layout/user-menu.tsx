"use client";

import { useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useMe } from "@/hooks/queries";
import { api } from "@/lib/api";
import { LOGIN_PATH } from "@/lib/auth-redirect";

/** Signed-in email and a sign-out button (sidebar footer). */
export function UserMenu() {
  const me = useMe();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState(false);

  async function signOut() {
    setPending(true);
    try {
      await api.logout();
    } finally {
      queryClient.clear();
      window.location.assign(LOGIN_PATH);
    }
  }

  if (!me.data) return null;
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="truncate text-xs text-sidebar-foreground/70" title={me.data.email}>
        {me.data.email}
      </span>
      <Button
        size="icon-sm"
        variant="ghost"
        onClick={signOut}
        disabled={pending}
        aria-label="Sign out"
        title="Sign out"
      >
        <LogOut />
      </Button>
    </div>
  );
}
