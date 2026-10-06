import {
  Activity,
  Boxes,
  Cpu,
  LayoutDashboard,
  ListVideo,
  Radio,
  Settings,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/matches", label: "Matches", icon: ListVideo },
  { href: "/live", label: "Live Processing", icon: Radio },
  { href: "/events", label: "Events", icon: Activity },
  { href: "/models", label: "Models", icon: Boxes },
  { href: "/system", label: "System", icon: Cpu },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (href === "/live") return pathname === "/live" || pathname.endsWith("/live");
  if (href === "/matches") return pathname.startsWith("/matches") && !pathname.endsWith("/live");
  return pathname.startsWith(href);
}
