import { useQuery } from "@tanstack/react-query";
import { api } from "@/features/api";
import type { Announcement, PortalNotice } from "./data";
export type ServerNotice = Omit<PortalNotice, "published"> & {
  status: "Draft" | "Published" | "Archived";
};
export type PortalContent = {
  version: number;
  notices: ServerNotice[];
  announcement: Announcement;
};
export function usePortalContent(admin = false) {
  return useQuery({
    queryKey: ["portal-content", admin],
    queryFn: () => api<PortalContent>(admin ? "/admin/portal/content" : "/portal/content"),
    staleTime: 15000,
  });
}
export function isSafeNoticeLink(link: string) {
  if (!link || link.includes("\\") || Array.from(link).some((c) => c.charCodeAt(0) < 32))
    return false;
  if (link.startsWith("/") && !link.startsWith("//")) return true;
  try {
    const url = new URL(link);
    return url.protocol === "https:" && !url.username;
  } catch {
    return false;
  }
}
