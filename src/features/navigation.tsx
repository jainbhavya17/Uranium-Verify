import { Link as PortalLink } from "@/components/link";
import { useNavigate as useRouterNavigate, useRouterState } from "@tanstack/react-router";
import type { AnchorHTMLAttributes } from "react";

/** Translate the source workflow routes into the approved portal's route structure. */
export function portalPath(path: string) {
  return path
    .replace(/^\/institution\/history\/([^/?]+)/, "/institution/records/$1")
    .replace(/^\/admin\/knowledge(?=\?|$)/, "/admin/knowledge-sources")
    .replace(/^\/officer\/applications(?=\/|\?|$)/, "/officer/cases")
    .replace(/^\/officer\/cases(?=\?|$)/, "/officer/queue")
    .replace(/^\/officer\/verifications/, "/officer/verification-queue")
    .replace(/^\/admin\/users-roles/, "/admin/users")
    .replace(/^\/admin\/integrations/, "/admin/connectors")
    .replace(/\/review-submit(?=\?|$)/, "/review")
    .replace(/^(\/institution\/deficiencies\/[^/?]+)(?=\?|$)/, "$1/respond");
}
type Props = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & { to: string; end?: boolean };
export function Link({ to, end: _end, ...props }: Props) {
  const [pathname, query = ""] = portalPath(to).split("?");
  return (
    <PortalLink to={pathname} search={Object.fromEntries(new URLSearchParams(query))} {...props} />
  );
}
export const NavLink = Link;
export function useNavigate() {
  const navigate = useRouterNavigate();
  return (path: string, options?: { replace?: boolean }) => {
    const [to, query = ""] = portalPath(path).split("?");
    return navigate({
      to: to as never,
      search: Object.fromEntries(new URLSearchParams(query)) as never,
      replace: options?.replace,
    });
  };
}
export function useSearchParams(): [
  URLSearchParams,
  (next: URLSearchParams | Record<string, string>, options?: { replace?: boolean }) => void,
] {
  const location = useRouterState({ select: (s) => s.location });
  const navigate = useNavigate();
  return [
    new URLSearchParams(location.searchStr),
    (next, options) => {
      void navigate(`${location.pathname}?${new URLSearchParams(next)}`, options);
    },
  ];
}
