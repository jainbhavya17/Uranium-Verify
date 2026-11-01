import { Link as RLink, useNavigate } from "@tanstack/react-router";
import type { AnchorHTMLAttributes, FC } from "react";

/** Router Link that accepts fully-resolved path strings (e.g. built from record IDs). */
export const Link = RLink as unknown as FC<
  Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & {
    to: string;
    search?: Record<string, string>;
    activeProps?: { className?: string };
    activeOptions?: { exact?: boolean };
  }
>;

export function useGo() {
  const navigate = useNavigate();
  return (to: string) => navigate({ to: to as never });
}
