import { useSyncExternalStore } from "react";
import * as seed from "./data";
import type {
  Application,
  AuditEntry,
  Connector,
  Deficiency,
  Details,
  DocStatus,
  Notification,
  Role,
  Rule,
  User,
} from "./data";

export interface State {
  users: User[];
  applications: Application[];
  deficiencies: Deficiency[];
  audit: AuditEntry[];
  notifications: Notification[];
  rules: Rule[];
  connectors: Connector[];
  portalNotices: seed.PortalNotice[];
  announcement: seed.Announcement;
  reviewReports: seed.ReviewReport[];
  session: string | null;
  hydrated: boolean;
  prefs: { email: boolean; sms: boolean; language: string };
}
const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v));
const initial = (): State => ({
  users: clone(seed.users),
  applications: clone(seed.applications),
  deficiencies: clone(seed.deficiencies),
  audit: clone(seed.audit),
  notifications: clone(seed.notifications),
  rules: clone(seed.rules),
  connectors: clone(seed.connectors),
  portalNotices: clone(seed.portalNotices),
  announcement: clone(seed.announcement),
  reviewReports: clone(seed.reviewReports),
  session: null,
  hydrated: false,
  prefs: { email: true, sms: false, language: "English" },
});
const serverState = initial();
let state = initial();
const listeners = new Set<() => void>();
// Keep the redesign's demo session and data independent of the original MVP.
const KEY = "uranium-verify-redesign-v1";

function set(fn: (s: State) => void) {
  const next = clone(state);
  fn(next);
  next.hydrated = true;
  state = next;
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...state, hydrated: undefined }));
  } catch {
    /* ignore */
  }
  listeners.forEach((l) => l());
}
export function hydrate() {
  if (state.hydrated) return;
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) state = { ...initial(), ...JSON.parse(raw) };
  } catch {
    /* ignore */
  }
  state = { ...state, hydrated: true };
  listeners.forEach((l) => l());
}
export function useStore<T>(sel: (s: State) => T): T {
  return sel(
    useSyncExternalStore(
      (l) => {
        listeners.add(l);
        return () => listeners.delete(l);
      },
      () => state,
      () => serverState,
    ),
  );
}
export const getState = () => state;

const now = () => {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
};
const today = () => now().slice(0, 10);
const me = (s: State) => s.users.find((u) => u.id === s.session)!;
function log(s: State, action: string, ref: string) {
  const u = me(s);
  s.audit.unshift({
    id: `AU-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    at: now(),
    actor: u?.name ?? "System",
    role: u?.role ?? "system",
    action,
    ref,
  });
}
const app = (s: State, id: string) => s.applications.find((a) => a.id === id)!;

function requireRole(s: State, role: Role) {
  const user = me(s);
  if (!user?.active || user.role !== role)
    throw new Error(`This action requires the ${role} role.`);
  return user;
}
function institutionApp(s: State, id: string, draftOnly = true) {
  const user = requireRole(s, "institution");
  const a = app(s, id);
  if (!a || a.institutionId !== user.institutionId)
    throw new Error("This application does not belong to your institution.");
  if (draftOnly && a.status !== "Draft") throw new Error("Submitted applications are read-only.");
  return a;
}
function officerApp(s: State, id: string, editable = true) {
  requireRole(s, "officer");
  const a = app(s, id);
  if (!a || a.status === "Draft") throw new Error("This case is not available for scrutiny.");
  if (editable && a.decision) throw new Error("A final decision has already been recorded.");
  return a;
}
export function readiness(a: Application, rules: Rule[]) {
  const blocking: { text: string; step: string }[] = [];
  if (!a.details.course.trim() || !a.details.principal.trim() || !a.details.address.trim())
    blocking.push({ text: "Complete course, head of institution, and address.", step: "details" });
  if (
    ![a.details.intake, a.details.landArea, a.details.builtUpArea, a.details.facultyCount].every(
      Number.isFinite,
    ) ||
    a.details.intake <= 0 ||
    Math.min(a.details.landArea, a.details.builtUpArea, a.details.facultyCount) < 0
  )
    blocking.push({
      text: "Enter valid non-negative infrastructure figures and a positive intake.",
      step: "details",
    });
  const missing = a.documents.filter((d) => d.mandatory && !d.fileName);
  if (missing.length)
    blocking.push({
      text: `Add ${missing.length} missing mandatory document${missing.length === 1 ? "" : "s"}.`,
      step: "documents",
    });
  if (a.details.academicYear !== "2026-27")
    blocking.push({ text: "Select the supported academic year 2026–27.", step: "details" });
  const advisory = evaluateRules(a, rules)
    .filter((r) => !r.pass && !["R-04", "R-05"].includes(r.rule.id))
    .map((r) => `${r.rule.title}: ${r.observed}`);
  return { blocking, advisory };
}
export const precheckFingerprint = (a: Application, rules: Rule[]) =>
  JSON.stringify({
    details: a.details,
    documents: a.documents.map((d) => [d.code, d.fileName, d.status]),
    rules: rules.map((r) => [r.id, r.active]),
  });

export const useCurrentUser = () =>
  useStore((s) => s.users.find((u) => u.id === s.session) ?? null);

export const actions = {
  savePrecheck(id: string) {
    set((s) => {
      const a = institutionApp(s, id);
      const result = readiness(a, s.rules);
      a.precheck = {
        checkedOn: now(),
        fingerprint: precheckFingerprint(a, s.rules),
        blocking: result.blocking.map((b) => b.text),
        advisory: result.advisory,
      };
      log(s, "Readiness check saved", a.ref);
    });
  },
  saveResponseDraft(id: string, response: string, attachment: string) {
    set((s) => {
      const d = s.deficiencies.find((d) => d.id === id);
      if (!d) throw new Error("Notice not found.");
      institutionApp(s, d.appId, false);
      if (d.status !== "Open") throw new Error("This notice is no longer open.");
      d.draftResponse = response;
      d.draftAttachment = attachment;
      d.draftSavedOn = now();
      log(s, "Clarification draft saved", id);
    });
  },
  createReviewReport(id: string) {
    let reportId = "";
    set((s) => {
      const a = officerApp(s, id, false);
      reportId = `REP-${crypto.randomUUID()}`;
      s.reviewReports.unshift({
        id: reportId,
        appId: id,
        reference: a.ref,
        createdOn: now(),
        createdBy: me(s).name,
        application: clone(a),
        deficiencies: clone(s.deficiencies.filter((d) => d.appId === id)),
        checks: evaluateRules(a, s.rules).map((r) => ({
          ruleId: r.rule.id,
          title: r.rule.title,
          clause: r.rule.clause,
          observed: r.observed,
          pass: r.pass,
        })),
      });
      log(s, "Review snapshot created", a.ref);
    });
    return reportId;
  },
  exportReviewReport(id: string) {
    requireRole(state, "officer");
    const report = state.reviewReports.find((r) => r.id === id);
    if (!report) throw new Error("Report not found.");
    set((s) => {
      log(s, "Review snapshot exported", report.reference);
    });
    return JSON.stringify(
      { prototype: true, scope: "Local review snapshot; not an official AICTE report", ...report },
      null,
      2,
    );
  },
  saveNotice(notice: seed.PortalNotice) {
    if (me(state)?.role !== "admin") throw new Error("Administrator access required.");
    const cleaned = {
      ...notice,
      title: notice.title.trim(),
      summary: notice.summary.trim(),
      body: notice.body.trim(),
      link: notice.link?.trim() || undefined,
    };
    if (
      !cleaned.title ||
      !cleaned.summary ||
      !cleaned.body ||
      !/^\d{4}-\d{2}-\d{2}$/.test(cleaned.publishedOn) ||
      !["Guidance", "Updates", "Maintenance"].includes(cleaned.category)
    )
      throw new Error("Complete the required notice fields.");
    if (cleaned.link && !isSafeNoticeLink(cleaned.link))
      throw new Error("Use a portal path or an HTTPS link.");
    set((s) => {
      const i = s.portalNotices.findIndex((n) => n.id === notice.id);
      if (i < 0) s.portalNotices.push(cleaned);
      else s.portalNotices[i] = cleaned;
      log(s, "Notice saved", cleaned.title);
    });
  },
  deleteNotice(id: string) {
    if (me(state)?.role !== "admin") throw new Error("Administrator access required.");
    set((s) => {
      s.portalNotices = s.portalNotices.filter((n) => n.id !== id);
      log(s, "Notice deleted", id);
    });
  },
  saveAnnouncement(value: seed.Announcement) {
    if (me(state)?.role !== "admin") throw new Error("Administrator access required.");
    if (!value.text.trim() || !isSafeNoticeLink(value.link))
      throw new Error("Enter announcement text and a safe link.");
    set((s) => {
      s.announcement = { ...value, text: value.text.trim() };
      log(s, "Announcement updated", "Portal");
    });
  },
  login(id: string, pw: string): User | null {
    const u = state.users.find(
      (x) => (x.id === id.trim() || x.email === id.trim()) && x.password === pw,
    );
    if (!u || !u.active) return null;
    set((s) => {
      s.session = u.id;
      log(s, "Signed in", "Session");
    });
    return u;
  },
  logout() {
    set((s) => {
      log(s, "Signed out", "Session");
      s.session = null;
    });
  },
  createApp(type: string): string {
    requireRole(state, "institution");
    if (!seed.APP_TYPES.some((t) => t.name === type))
      throw new Error("Choose a supported approval type.");
    let id = "";
    set((s) => {
      const u = me(s);
      const n =
        Math.max(1600, ...s.applications.map((a) => Number(a.id.replace("APP-", "")) || 0)) + 1;
      id = `APP-0${n}`;
      const inst = seed.institutions.find((i) => i.id === u.institutionId)!;
      s.applications.unshift({
        id,
        ref: `AICTE/2026/APP/0${n}`,
        institutionId: inst.id,
        type,
        status: "Draft",
        createdOn: today(),
        details: {
          programme: "Engineering & Technology",
          course: "",
          intake: 60,
          academicYear: "2026-27",
          landArea: 0,
          builtUpArea: 0,
          facultyCount: 0,
          principal: u.name,
          address: "",
        },
        documents: seed.DOC_TEMPLATE.map((d) => ({ ...d, status: "Not Submitted" as DocStatus })),
        history: [{ at: now(), by: u.name, action: "Draft created" }],
      });
      log(s, "Draft application created", `AICTE/2026/APP/0${n}`);
    });
    return id;
  },
  saveDetails(id: string, d: Details) {
    institutionApp(state, id);
    set((s) => {
      const a = app(s, id);
      a.details = d;
      a.history.push({ at: now(), by: me(s).name, action: "Draft saved" });
      log(s, "Draft saved", a.ref);
    });
  },
  uploadDoc(id: string, code: string, fileName: string) {
    institutionApp(state, id);
    if (!fileName.toLowerCase().endsWith(".pdf")) throw new Error("Choose a PDF file.");
    set((s) => {
      const a = app(s, id);
      const d = a.documents.find((x) => x.code === code)!;
      d.versions ??= d.fileName
        ? [
            {
              number: 1,
              fileName: d.fileName,
              recordedOn: d.uploadedOn ?? a.createdOn,
              actor: "Existing MVP record",
            },
          ]
        : [];
      d.versions.push({
        number: d.versions.length + 1,
        fileName,
        recordedOn: now(),
        actor: me(s).name,
      });
      d.fileName = fileName;
      d.uploadedOn = today();
      d.status = "Under Review";
      log(s, `Document ${code} uploaded`, a.ref);
    });
  },
  removeDoc(id: string, code: string) {
    institutionApp(state, id);
    set((s) => {
      const a = app(s, id);
      const d = a.documents.find((x) => x.code === code)!;
      d.versions ??= d.fileName
        ? [
            {
              number: 1,
              fileName: d.fileName,
              recordedOn: d.uploadedOn ?? a.createdOn,
              actor: "Existing MVP record",
            },
          ]
        : [];
      d.fileName = undefined;
      d.uploadedOn = undefined;
      d.status = "Not Submitted";
      log(s, `Document ${code} removed`, a.ref);
    });
  },
  submit(id: string) {
    const candidate = institutionApp(state, id);
    if (readiness(candidate, state.rules).blocking.length)
      throw new Error("Resolve the blocking readiness issues before submission.");
    set((s) => {
      const a = app(s, id);
      a.status = "Submitted";
      a.submittedOn = today();
      a.frozen = {
        details: clone(a.details),
        documents: clone(a.documents),
        submittedOn: a.submittedOn,
      };
      a.history.push({ at: now(), by: me(s).name, action: "Application submitted" });
      log(s, "Application submitted", a.ref);
      s.notifications.unshift({
        id: `N-${Date.now()}`,
        at: today(),
        role: "officer",
        text: `New application ${a.ref} received in case queue.`,
        link: `/officer/cases/${a.id}/overview`,
      });
    });
  },
  startScrutiny(id: string) {
    officerApp(state, id);
    set((s) => {
      const a = app(s, id);
      if (a.status !== "Submitted") return;
      a.status = "Under Scrutiny";
      a.assignedOfficer = me(s).name;
      a.history.push({ at: now(), by: me(s).name, action: "Scrutiny commenced" });
      log(s, "Scrutiny commenced", a.ref);
    });
  },
  setDocStatus(id: string, code: string, status: DocStatus, findings: string) {
    officerApp(state, id);
    if (!findings.trim()) throw new Error("Record the findings for this document.");
    set((s) => {
      const a = app(s, id);
      const d = a.documents.find((x) => x.code === code)!;
      d.status = status;
      d.findings = findings;
      d.checkedBy = me(s).name;
      d.checkedOn = today();
      log(s, `Document ${code} marked ${status}`, a.ref);
    });
  },
  saveInspection(id: string, ins: seed.Inspection) {
    officerApp(state, id);
    set((s) => {
      const a = app(s, id);
      a.inspection = ins;
      a.history.push({ at: now(), by: me(s).name, action: "Inspection report recorded" });
      log(s, "Inspection report recorded", a.ref);
    });
  },
  raiseDeficiency(id: string, category: string, description: string) {
    const candidate = officerApp(state, id);
    if (candidate.status === "Submitted" || description.trim().length < 15)
      throw new Error("Start scrutiny and enter a clear deficiency description first.");
    set((s) => {
      const a = app(s, id);
      const dId = `DEF-0${Math.max(913, ...s.deficiencies.map((d) => Number(d.id.replace("DEF-", "")) || 0)) + 1}`;
      const due = new Date();
      due.setDate(due.getDate() + 30);
      s.deficiencies.unshift({
        id: dId,
        appId: id,
        category,
        description,
        raisedBy: me(s).name,
        raisedOn: today(),
        dueOn: due.toISOString().slice(0, 10),
        status: "Open",
      });
      a.status = "Deficiency Raised";
      a.history.push({
        at: now(),
        by: me(s).name,
        action: "Deficiency raised",
        remark: description.slice(0, 120),
      });
      log(s, `Deficiency ${dId} raised`, a.ref);
      s.notifications.unshift({
        id: `N-${Date.now()}`,
        at: today(),
        role: "institution",
        institutionId: a.institutionId,
        text: `Deficiency Notice ${dId} issued against ${a.ref}.`,
        link: `/institution/deficiencies/${dId}/respond`,
      });
    });
  },
  respondDeficiency(dId: string, response: string) {
    const notice = state.deficiencies.find((d) => d.id === dId);
    if (!notice) throw new Error("Notice not found.");
    institutionApp(state, notice.appId, false);
    if (notice.status !== "Open" || response.trim().length < 20)
      throw new Error("An open notice and a response of at least 20 characters are required.");
    set((s) => {
      const d = s.deficiencies.find((x) => x.id === dId)!;
      d.status = "Responded";
      d.response = response;
      d.respondedOn = today();
      delete d.draftResponse;
      delete d.draftAttachment;
      delete d.draftSavedOn;
      const a = app(s, d.appId);
      a.history.push({ at: now(), by: me(s).name, action: `Response to ${dId} submitted` });
      log(s, `Response to ${dId} submitted`, a.ref);
      s.notifications.unshift({
        id: `N-${Date.now()}`,
        at: today(),
        role: "officer",
        text: `Institution responded to ${dId} (${a.ref}).`,
        link: `/officer/cases/${a.id}/review`,
      });
    });
  },
  closeDeficiency(dId: string, remark: string) {
    const notice = state.deficiencies.find((d) => d.id === dId);
    if (!notice) throw new Error("Notice not found.");
    officerApp(state, notice.appId);
    if (notice.status !== "Responded" || !remark?.trim())
      throw new Error("Review a submitted response and record your closure remark.");
    set((s) => {
      const d = s.deficiencies.find((x) => x.id === dId)!;
      d.status = "Closed";
      d.closedBy = me(s).name;
      d.closedOn = today();
      d.closeRemark = remark;
      const a = app(s, d.appId);
      if (
        !s.deficiencies.some((x) => x.appId === a.id && x.status !== "Closed") &&
        a.status === "Deficiency Raised"
      )
        a.status = "Under Scrutiny";
      a.history.push({
        at: now(),
        by: me(s).name,
        action: `Deficiency ${dId} re-verified and closed`,
        remark,
      });
      log(s, `Deficiency ${dId} closed`, a.ref);
    });
  },
  decide(id: string, decision: "Approved" | "Rejected", reason: string) {
    const candidate = officerApp(state, id);
    if (
      candidate.status !== "Under Scrutiny" ||
      state.deficiencies.some((d) => d.appId === id && d.status !== "Closed") ||
      reason.trim().length < 20
    )
      throw new Error(
        "Complete scrutiny, close deficiencies, and record a reason before deciding.",
      );
    if (
      decision === "Approved" &&
      (evaluateRules(candidate, state.rules).some((r) => !r.pass) ||
        candidate.documents.some((d) => d.mandatory && d.status !== "Verified"))
    )
      throw new Error("Approval requires passing active rules and verified mandatory documents.");
    set((s) => {
      const a = app(s, id);
      a.status = decision;
      a.decision = { decision, officer: me(s).name, reason, at: now() };
      a.history.push({ at: now(), by: me(s).name, action: decision, remark: reason });
      log(s, `Application ${decision.toLowerCase()}`, a.ref);
      s.notifications.unshift({
        id: `N-${Date.now()}`,
        at: today(),
        role: "institution",
        institutionId: a.institutionId,
        text: `Application ${a.ref} has been ${decision.toLowerCase()}.`,
        link: `/institution/applications/${a.id}/status`,
      });
    });
  },
  toggleRule(rid: string) {
    requireRole(state, "admin");
    set((s) => {
      const r = s.rules.find((x) => x.id === rid)!;
      r.active = !r.active;
      log(s, `Rule ${r.id} ${r.active ? "activated" : "deactivated"}`, "Rule Library");
    });
  },
  toggleUser(uid: string) {
    requireRole(state, "admin");
    set((s) => {
      const u = s.users.find((x) => x.id === uid)!;
      u.active = !u.active;
      log(s, `User ${u.id} ${u.active ? "enabled" : "disabled"}`, "Users & Roles");
    });
  },
  addUser(u: Omit<User, "password" | "active">) {
    requireRole(state, "admin");
    if (
      !u.id.trim() ||
      state.users.some(
        (x) => x.id === u.id.trim() || x.email.toLowerCase() === u.email.toLowerCase(),
      )
    )
      throw new Error("This user ID or email already exists.");
    set((s) => {
      s.users.push({ ...u, password: seed.PASSWORD, active: true });
      log(s, `User ${u.id} created`, "Users & Roles");
    });
  },
  toggleConnector(cid: string) {
    requireRole(state, "admin");
    set((s) => {
      const c = s.connectors.find((x) => x.id === cid)!;
      c.status = c.status === "Disabled" ? "Operational" : "Disabled";
      // This only changes the local demonstration configuration; no synchronization occurs.
      log(
        s,
        `Connector ${c.name} ${c.status === "Disabled" ? "disabled" : "enabled"}`,
        "Connectors",
      );
    });
  },
  markRead(nid: string) {
    set((s) => {
      const n = s.notifications.find((x) => x.id === nid);
      if (n) n.read = true;
    });
  },
  setPrefs(p: State["prefs"]) {
    set((s) => {
      s.prefs = p;
      if (s.session) log(s, "Preferences updated", "Settings");
    });
  },
  changePassword(oldPw: string, pw: string) {
    let ok = false;
    set((s) => {
      const u = me(s);
      if (u.password === oldPw) {
        u.password = pw;
        ok = true;
        log(s, "Password changed", "Settings");
      }
    });
    return ok;
  },
};

export function isSafeNoticeLink(link: string) {
  if (/\s/.test(link) || [...link].some((char) => char.charCodeAt(0) < 32)) return false;
  if (link.startsWith("/") && !link.startsWith("//") && !link.includes("\\")) return true;
  try {
    return new URL(link).protocol === "https:";
  } catch {
    return false;
  }
}
export function publishedNotices(notices: seed.PortalNotice[]) {
  const date = new Date();
  const localDay = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  return notices
    .filter((n) => n.published && n.publishedOn <= localDay)
    .sort(
      (a, b) =>
        Number(b.pinned) - Number(a.pinned) ||
        b.publishedOn.localeCompare(a.publishedOn) ||
        a.id.localeCompare(b.id),
    );
}

export function evaluateRules(a: Application, rules: Rule[]) {
  const d = a.details;
  const checks: Record<string, { pass: boolean; observed: string }> = {
    "R-01": {
      pass: d.facultyCount >= Math.ceil(d.intake / 20),
      observed: `${d.facultyCount} faculty for intake ${d.intake} (required ${Math.ceil(d.intake / 20)})`,
    },
    "R-02": { pass: d.landArea >= 2.5, observed: `${d.landArea} acres` },
    "R-03": {
      pass: d.builtUpArea >= 1000 + d.intake * 5,
      observed: `${d.builtUpArea} sq.m (required ${1000 + d.intake * 5})`,
    },
    "R-04": {
      pass: a.documents.every((x) => !x.mandatory || x.status !== "Not Submitted"),
      observed: `${a.documents.filter((x) => x.mandatory && x.status === "Not Submitted").length} mandatory document(s) pending`,
    },
    "R-05": { pass: d.academicYear === "2026-27", observed: d.academicYear },
  };
  return rules
    .filter((r) => r.active)
    .map((r) => ({ rule: r, ...(checks[r.id] ?? { pass: true, observed: "Not applicable" }) }));
}
export const roleHome: Record<Role, string> = {
  institution: "/institution/dashboard",
  officer: "/officer/dashboard",
  admin: "/admin/notices",
};
