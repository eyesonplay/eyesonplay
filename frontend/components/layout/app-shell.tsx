"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { HealthIndicator } from "@/components/layout/health-indicator";
import { NAV_ITEMS, isActive } from "@/components/layout/nav";
import { cn } from "@/lib/utils";

function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2.5 px-1">
      <span className="grid size-7 place-items-center rounded-md bg-primary/15 ring-1 ring-primary/30">
        <span className="size-2.5 rounded-full bg-primary shadow-[0_0_12px] shadow-primary/60" />
      </span>
      <span className="text-sm font-semibold tracking-tight">EyesOnPlay</span>
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col border-r border-sidebar-border bg-sidebar lg:flex">
        <div className="flex h-14 items-center px-4">
          <Logo />
        </div>
        <nav className="flex flex-1 flex-col gap-0.5 px-2 py-2" aria-label="Main">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                  active && "bg-sidebar-accent text-sidebar-accent-foreground",
                )}
              >
                <Icon className={cn("size-4", active ? "text-primary" : "text-sidebar-foreground/50")} />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-sidebar-border p-3">
          <HealthIndicator variant="sidebar" />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur lg:hidden">
          <div className="flex h-12 items-center justify-between px-4">
            <Logo />
            <HealthIndicator variant="compact" />
          </div>
          <nav className="scrollbar-thin flex gap-1 overflow-x-auto px-3 pb-2" aria-label="Main">
            {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1 text-xs text-muted-foreground",
                  isActive(pathname, href) && "bg-muted text-foreground",
                )}
              >
                <Icon className="size-3.5" />
                {label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="flex-1 px-4 py-5 lg:px-7 lg:py-6">{children}</main>
      </div>
    </div>
  );
}
