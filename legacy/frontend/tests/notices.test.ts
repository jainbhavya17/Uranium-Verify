import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PortalNotice } from "@/lib/data";
const notice: PortalNotice = {
  id: "PN-test",
  title: "New guidance",
  summary: "A new document update.",
  body: "First paragraph.\n\nSecond paragraph.",
  category: "Guidance",
  publishedOn: "2026-10-01",
  published: false,
  pinned: false,
};
beforeEach(() => {
  vi.resetModules();
  localStorage.clear();
});
describe("Notice publishing", () => {
  it("requires an administrator for create, update, delete, and announcement changes", async () => {
    const { actions } = await import("@/lib/store");
    expect(() => actions.saveNotice(notice)).toThrow("Administrator");
    actions.login("inst.svit", "Aicte@2026");
    expect(() => actions.saveNotice(notice)).toThrow("Administrator");
    expect(() => actions.deleteNotice("PN-1")).toThrow("Administrator");
    expect(() =>
      actions.saveAnnouncement({ enabled: true, text: "Update", link: "/resources" }),
    ).toThrow("Administrator");
  });
  it("saves, edits, publishes, and deletes notices through the store and persists across hydration", async () => {
    const { actions, getState } = await import("@/lib/store");
    actions.login("admin", "Aicte@2026");
    actions.saveNotice(notice);
    actions.saveNotice({ ...notice, title: "Edited guidance", published: true, pinned: true });
    expect(getState().portalNotices.find((n) => n.id === notice.id)).toMatchObject({
      title: "Edited guidance",
      published: true,
      pinned: true,
    });
    vi.resetModules();
    const reloaded = await import("@/lib/store");
    reloaded.hydrate();
    expect(reloaded.getState().portalNotices.find((n) => n.id === notice.id)?.title).toBe(
      "Edited guidance",
    );
    reloaded.actions.deleteNotice(notice.id);
    expect(reloaded.getState().portalNotices.some((n) => n.id === notice.id)).toBe(false);
    expect(
      JSON.parse(localStorage.getItem("uranium-verify-redesign-v1")!).portalNotices.some(
        (n: PortalNotice) => n.id === notice.id,
      ),
    ).toBe(false);
    expect(localStorage.getItem("uranium-verify-v1")).toBeNull();
  });
  it("hides drafts and future publications, sorts pinned notices first, and does not mutate source order", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-11-01T12:00:00"));
    try {
      const { publishedNotices } = await import("@/lib/store");
      const list = [
        { ...notice, id: "draft" },
        { ...notice, id: "future", published: true, publishedOn: "2026-12-01" },
        { ...notice, id: "recent", published: true, publishedOn: "2026-10-30" },
        { ...notice, id: "pinned", published: true, pinned: true },
      ];
      expect(publishedNotices(list).map((n) => n.id)).toEqual(["pinned", "recent"]);
      expect(list[0].id).toBe("draft");
      expect(publishedNotices([])).toEqual([]);
    } finally {
      vi.useRealTimers();
    }
  });
  it("rejects executable links and blank notice content", async () => {
    const { actions, isSafeNoticeLink } = await import("@/lib/store");
    actions.login("admin", "Aicte@2026");
    for (const link of ["javascript:alert(1)", "//evil.example", "/\\evil.example", "/bad path"])
      expect(isSafeNoticeLink(link)).toBe(false);
    expect(isSafeNoticeLink("https://example.org/guidance")).toBe(true);
    expect(isSafeNoticeLink("/resources")).toBe(true);
    expect(() => actions.saveNotice({ ...notice, link: "javascript:alert(1)" })).toThrow("HTTPS");
    expect(() => actions.saveNotice({ ...notice, title: "  " })).toThrow("required");
  });
  it("persists announcement changes and adds defaults when hydrating an older MVP store", async () => {
    localStorage.setItem("uranium-verify-redesign-v1", JSON.stringify({ session: "admin" }));
    const { actions, hydrate, getState } = await import("@/lib/store");
    hydrate();
    expect(getState().portalNotices.length).toBeGreaterThan(0);
    actions.saveAnnouncement({ enabled: false, text: "Updated announcement", link: "/notices" });
    expect(
      JSON.parse(localStorage.getItem("uranium-verify-redesign-v1")!).announcement,
    ).toMatchObject({ enabled: false, text: "Updated announcement" });
  });
});
