import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BackendSessionProvider, useBackendSession, userHome } from "@/lib/backend-session";
import { api } from "@/features/api";
import { Fields } from "@/features/officer/common";
import { EvidenceTrail } from "@/features/officer/EvidenceTrail";
import { isSafeNoticeLink } from "@/lib/portal-content";
import type { User } from "@/features/api";

const user: User = {
  id: "test-user",
  email: "officer@example.test",
  name: "Example Officer",
  roles: ["officer"],
  institution_ids: [],
  landing: "/officer/dashboard",
  expires_at: 2000000000,
  mode: "DEMO",
};
const reply = (data: unknown, status = 200) => ({
  ok: status < 400,
  status,
  json: async () =>
    status < 400
      ? { data, meta: { request_id: "test" }, error: null }
      : { error: { message: "Sign in required", field_errors: {} } },
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  document.cookie = "uv_csrf=; max-age=0";
});
function SessionProbe() {
  const s = useBackendSession();
  return (
    <>
      <p>{s.pending ? "Loading" : (s.user?.name ?? "Signed out")}</p>
      <button onClick={() => void s.login("officer@example.test", "test-input")}>Sign in</button>
      <button onClick={() => void s.logout()}>Sign out</button>
    </>
  );
}
function mountSession() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <BackendSessionProvider>
        <SessionProbe />
      </BackendSessionProvider>
    </QueryClientProvider>,
  );
  return client;
}
describe("Server-backed session", () => {
  it("keeps an anonymous initial session stable and does not repeatedly expire it", async () => {
    const expired = vi.fn();
    window.addEventListener("uranium:session-expired", expired);
    const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(reply(null, 401) as Response);
    mountSession();
    await screen.findByText("Signed out");
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(expired).not.toHaveBeenCalled();
    window.removeEventListener("uranium:session-expired", expired);
  });
  it("loads authority from the server and clears previously cached private records on logout", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async (_url, options) => reply(options?.method === "DELETE" ? {} : user) as Response,
    );
    const client = mountSession();
    await screen.findByText("Example Officer");
    client.setQueryData(["private-record"], { name: "private" });
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await screen.findByText("Signed out");
    expect(client.getQueryData(["private-record"])).toBeUndefined();
  });
  it("maps specialist and auditor landing pages to actual protected routes", () => {
    expect(userHome({ ...user, landing: "/officer/verifications" })).toBe(
      "/officer/verification-queue",
    );
    expect(userHome({ ...user, roles: ["auditor"], landing: "/admin/audit" })).toBe("/admin/audit");
  });
});
describe("API and public links", () => {
  it("uses the server session cookie and CSRF token for authenticated mutations", async () => {
    document.cookie = "uv_csrf=test-csrf; path=/";
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(reply({ saved: true }) as Response);
    await api("/test", { method: "POST", body: "{}" });
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/test",
      expect.objectContaining({
        credentials: "same-origin",
        headers: expect.objectContaining({ "X-CSRF-Token": "test-csrf" }),
      }),
    );
  });
  it("signals session expiry for a protected request", async () => {
    const expired = vi.fn();
    window.addEventListener("uranium:session-expired", expired);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(reply(null, 401) as Response);
    await expect(api("/applications")).rejects.toThrow("Sign in required");
    expect(expired).toHaveBeenCalledOnce();
    window.removeEventListener("uranium:session-expired", expired);
  });
  it("rejects executable, network-relative and control-character notice links", () => {
    for (const link of [
      "javascript:alert(1)",
      "//outside.test",
      "/\\outside.test",
      "/notices\n",
      "https://user@outside.test",
    ])
      expect(isSafeNoticeLink(link)).toBe(false);
    expect(isSafeNoticeLink("/resources")).toBe(true);
    expect(isSafeNoticeLink("https://www.aicte.gov.in/")).toBe(true);
  });
});
describe("Evidence presentation", () => {
  it("renders nested results as readable labels and lists rather than JSON", () => {
    render(
      <Fields
        data={{
          verification_state: "INSUFFICIENT_EVIDENCE",
          confirmed: false,
          source: { page: 2 },
          reasons: ["Expiry date is missing"],
        }}
      />,
    );
    expect(screen.getByText("More evidence needed")).toBeVisible();
    expect(screen.getByText("No")).toBeVisible();
    expect(screen.getByText("Page")).toBeVisible();
    expect(document.body.textContent).not.toContain('{"');
  });
  it("opens the exact saved document page from the evidence trail", () => {
    const openSource = vi.fn();
    render(
      <EvidenceTrail
        nodes={[
          {
            id: "node",
            kind: "EXTRACTED_FIELD",
            reference: { version_id: "version", field_id: "field" },
          },
        ]}
        edges={[]}
        versions={[{ id: "version", name: "Fire certificate.pdf", number: 2 }]}
        fields={[{ id: "field", key: "institution_name", page: 3 }]}
        openSource={openSource}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Open original source" }));
    expect(openSource).toHaveBeenCalledWith("version", 3, "field");
  });
});
