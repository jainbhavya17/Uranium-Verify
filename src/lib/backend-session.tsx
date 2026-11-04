import { createContext, useContext, useEffect, useSyncExternalStore, type ReactNode } from "react";
import { getConnectionWaiting, subscribeConnectionWaiting } from "@/lib/api-connection";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, type User } from "@/features/api";
import { portalPath } from "@/features/navigation";

export type PortalRole = "institution" | "officer" | "admin";
export function workspaceRole(user: User): PortalRole {
  if (user.roles.some((r) => r.startsWith("institution_"))) return "institution";
  if (user.roles.some((r) => ["officer", "specialist", "supervisor"].includes(r))) return "officer";
  return "admin";
}
export type PortalUser = User & { role: PortalRole };
const SessionContext = createContext<{
  user: PortalUser | null;
  pending: boolean;
  waking: boolean;
  error: Error | null;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  retry: () => void;
} | null>(null);
export function BackendSessionProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const waking = useSyncExternalStore(
    subscribeConnectionWaiting,
    getConnectionWaiting,
    () => false,
  );
  const q = useQuery({
    queryKey: ["backend-session"],
    retry: false,
    staleTime: 30000,
    queryFn: async ({ signal }) => {
      try {
        return (await api<User>("/me", { signal })).data;
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
  });
  useEffect(() => {
    const clear = () => {
      void qc.cancelQueries();
      qc.setQueryData(["backend-session"], null);
      qc.removeQueries({ predicate: (query) => query.queryKey[0] !== "backend-session" });
    };
    window.addEventListener("uranium:session-expired", clear);
    return () => window.removeEventListener("uranium:session-expired", clear);
  }, [qc]);
  const user = q.data ? { ...q.data, role: workspaceRole(q.data) } : null;
  return (
    <SessionContext.Provider
      value={{
        user,
        pending: q.isPending || (!q.data && q.isFetching),
        waking,
        error: q.error,
        retry: () => {
          void q.refetch();
        },
        login: async (email, password) => {
          const result = await api<User>("/auth/session", {
            method: "POST",
            body: JSON.stringify({ email, password }),
          });
          await qc.cancelQueries();
          qc.removeQueries({ predicate: (query) => query.queryKey[0] !== "backend-session" });
          qc.setQueryData(["backend-session"], result.data);
          return result.data;
        },
        logout: async () => {
          await api("/auth/session", { method: "DELETE" });
          await qc.cancelQueries();
          qc.setQueryData(["backend-session"], null);
          qc.removeQueries({ predicate: (query) => query.queryKey[0] !== "backend-session" });
        },
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}
export function useBackendSession() {
  const session = useContext(SessionContext);
  if (!session) throw new Error("Session provider missing");
  return session;
}
export const useCurrentUser = () => useBackendSession().user;
export const roleHome = {
  institution: "/institution/dashboard",
  officer: "/officer/dashboard",
  admin: "/admin/users",
};
export const userHome = (user: User) => portalPath(user.landing);
