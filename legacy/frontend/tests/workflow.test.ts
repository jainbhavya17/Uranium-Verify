import { beforeEach, describe, expect, it, vi } from "vitest";
import { APP_TYPES, DOC_TEMPLATE } from "@/lib/data";

beforeEach(() => {
  vi.resetModules();
  localStorage.clear();
});
async function prepared() {
  const store = await import("@/lib/store");
  store.actions.login("inst.svit", "Aicte@2026");
  const id = store.actions.createApp(APP_TYPES[1].name);
  const a = store.getState().applications.find((a) => a.id === id)!;
  store.actions.saveDetails(id, {
    ...a.details,
    course: "B.Tech Computer Science",
    intake: 60,
    landArea: 5,
    builtUpArea: 5000,
    facultyCount: 5,
    principal: "Sample Principal",
    address: "Sample institution address",
  });
  for (const d of DOC_TEMPLATE.filter((d) => d.mandatory))
    store.actions.uploadDoc(id, d.code, `${d.code}.pdf`);
  return { ...store, id };
}
describe("Institution and officer workflow", () => {
  it("blocks incomplete submissions and prevents another institution editing an application", async () => {
    const { actions, getState, readiness } = await import("@/lib/store");
    actions.login("inst.svit", "Aicte@2026");
    const id = actions.createApp(APP_TYPES[0].name);
    const a = getState().applications.find((a) => a.id === id)!;
    expect(readiness(a, getState().rules).blocking.length).toBeGreaterThan(0);
    expect(() => actions.submit(id)).toThrow("blocking");
    actions.login("inst.gecb", "Aicte@2026");
    expect(() => actions.saveDetails(id, a.details)).toThrow("belong");
  });
  it("preserves evidence version metadata across removal/replacement and flags a stale saved readiness check", async () => {
    const { actions, getState, id, precheckFingerprint } = await prepared();
    actions.savePrecheck(id);
    const before = getState().applications.find((a) => a.id === id)!;
    expect(before.precheck?.blocking).toEqual([]);
    actions.removeDoc(id, "D01");
    actions.uploadDoc(id, "D01", "replacement.pdf");
    const after = getState().applications.find((a) => a.id === id)!;
    expect(after.documents[0].versions?.map((v) => v.fileName)).toEqual([
      "D01.pdf",
      "replacement.pdf",
    ]);
    expect(after.precheck?.fingerprint).not.toBe(precheckFingerprint(after, getState().rules));
  });
  it("completes a submission, deficiency response, re-verification, document review, and approval without changing the frozen submission", async () => {
    const { actions, getState, id } = await prepared();
    actions.submit(id);
    const frozen = JSON.stringify(getState().applications.find((a) => a.id === id)!.frozen);
    expect(() => actions.uploadDoc(id, "D01", "late.pdf")).toThrow("read-only");
    actions.login("off.sharma", "Aicte@2026");
    actions.startScrutiny(id);
    actions.raiseDeficiency(id, "Documentation", "Please clarify the building completion record.");
    const d = getState().deficiencies.find((d) => d.appId === id)!;
    expect(() => actions.closeDeficiency(d.id, "Checked")).toThrow("submitted response");
    actions.login("inst.svit", "Aicte@2026");
    actions.saveResponseDraft(
      d.id,
      "The supporting building record confirms the stated area.",
      "clarification.pdf",
    );
    vi.resetModules();
    const restored = await import("@/lib/store");
    restored.hydrate();
    expect(restored.getState().deficiencies.find((x) => x.id === d.id)?.draftAttachment).toBe(
      "clarification.pdf",
    );
    restored.actions.respondDeficiency(
      d.id,
      "The supporting building record confirms the stated area.",
    );
    restored.actions.login("off.sharma", "Aicte@2026");
    restored.actions.closeDeficiency(d.id, "Response checked against the sample record.");
    for (const doc of DOC_TEMPLATE.filter((d) => d.mandatory))
      restored.actions.setDocStatus(
        id,
        doc.code,
        "Verified",
        "Human review of synthetic demonstration record.",
      );
    restored.actions.decide(
      id,
      "Approved",
      "All mandatory sample requirements reviewed and satisfied.",
    );
    const a = restored.getState().applications.find((a) => a.id === id)!;
    expect(a.status).toBe("Approved");
    expect(JSON.stringify(a.frozen)).toBe(frozen);
    expect(
      restored
        .getState()
        .notifications.some(
          (n) => n.institutionId === a.institutionId && n.text.includes("approved"),
        ),
    ).toBe(true);
    expect(() =>
      restored.actions.decide(id, "Rejected", "A second decision should not be possible."),
    ).toThrow("already");
  });
  it("blocks premature approval and requires scrutiny before recording a decision", async () => {
    const { actions, id } = await prepared();
    actions.submit(id);
    actions.login("off.sharma", "Aicte@2026");
    expect(() =>
      actions.decide(id, "Approved", "The submitted documents are ready for review."),
    ).toThrow("Complete scrutiny");
    actions.startScrutiny(id);
    expect(() =>
      actions.decide(id, "Approved", "The submitted documents are ready for review."),
    ).toThrow("verified mandatory");
    actions.decide(
      id,
      "Rejected",
      "Mandatory documents could not be verified in this sample review.",
    );
  });
  it("captures stable review snapshots and restricts report creation and export to officers", async () => {
    const { actions, getState, id } = await prepared();
    actions.submit(id);
    expect(() => actions.createReviewReport(id)).toThrow("officer");
    actions.login("off.sharma", "Aicte@2026");
    actions.startScrutiny(id);
    const rid = actions.createReviewReport(id);
    const snapshot = JSON.stringify(getState().reviewReports[0]);
    actions.setDocStatus(id, "D01", "Verified", "Recorded after the snapshot.");
    expect(JSON.stringify(getState().reviewReports[0])).toBe(snapshot);
    expect(JSON.parse(actions.exportReviewReport(rid)).application.documents[0].status).toBe(
      "Under Review",
    );
    actions.login("admin", "Aicte@2026");
    expect(() => actions.exportReviewReport(rid)).toThrow("officer");
  });
  it("guards administrative mutations and does not simulate a connector sync", async () => {
    const { actions, getState } = await import("@/lib/store");
    actions.login("off.sharma", "Aicte@2026");
    expect(() => actions.toggleRule("R-01")).toThrow("admin");
    actions.login("admin", "Aicte@2026");
    const connector = getState().connectors[0];
    actions.toggleConnector(connector.id);
    expect(getState().connectors[0].lastSync).toBe(connector.lastSync);
    expect(() =>
      actions.addUser({
        id: "admin",
        name: "Duplicate",
        email: "duplicate@example.org",
        role: "admin",
        designation: "Sample",
      }),
    ).toThrow("already");
  });
});
