export type Role = "institution" | "officer" | "admin";
export type AppStatus =
  "Draft" | "Submitted" | "Under Scrutiny" | "Deficiency Raised" | "Approved" | "Rejected";
export type DocStatus = "Verified" | "Mismatch Found" | "Under Review" | "Not Submitted";

export interface DocumentVersion {
  number: number;
  fileName: string;
  recordedOn: string;
  actor: string;
}
export interface SavedPrecheck {
  checkedOn: string;
  fingerprint: string;
  blocking: string[];
  advisory: string[];
}
export interface ReviewReport {
  id: string;
  appId: string;
  reference: string;
  createdOn: string;
  createdBy: string;
  application: Application;
  deficiencies: Deficiency[];
  checks: { ruleId: string; title: string; clause: string; observed: string; pass: boolean }[];
}
export const reviewReports: ReviewReport[] = [];

export type NoticeCategory = "Guidance" | "Updates" | "Maintenance";
export interface PortalNotice {
  id: string;
  title: string;
  summary: string;
  body: string;
  category: NoticeCategory;
  publishedOn: string;
  pinned: boolean;
  published: boolean;
  link?: string;
}
export interface Announcement {
  enabled: boolean;
  text: string;
  link: string;
}
export const announcement: Announcement = {
  enabled: true,
  text: "A clearer application workspace is here",
  link: "/resources",
};
export const portalNotices: PortalNotice[] = [
  {
    id: "PN-1",
    title: "Your guide to a complete application",
    category: "Guidance",
    publishedOn: "2026-10-28",
    pinned: true,
    published: true,
    summary: "Application types, supporting documents, and the steps to prepare for scrutiny.",
    body: "Choose the approval type that matches your institution’s next step: a new institution, extension of approval, increase in intake, introduction of a new course, or closure.\n\nComplete institution details and review the document checklist before submitting. Mandatory documents must be present before you can proceed.\n\nThis is guidance for the prototype workflow. The sample data and rules do not replace the official AICTE Approval Process Handbook.",
    link: "/resources",
  },
  {
    id: "PN-2",
    title: "Respond to a deficiency from your workspace",
    category: "Updates",
    publishedOn: "2026-10-18",
    pinned: false,
    published: true,
    summary:
      "Keep review queries and your institution’s responses together in the same application record.",
    body: "When an officer raises a deficiency, the institution can find it in the Deficiencies section of its workspace. Read the query, review its due date, and provide a clear response.\n\nThe reviewing officer can re-verify the response and close the deficiency. The application history records each step. Sign in to explore this workflow using the sample accounts.",
    link: "/login",
  },
  {
    id: "PN-3",
    title: "About availability in this prototype",
    category: "Maintenance",
    publishedOn: "2026-10-10",
    pinned: false,
    published: true,
    summary: "Your changes stay in this browser. No scheduled service interruption is announced.",
    body: "Uranium Verify is a local prototype. Applications, notices, and session changes are stored in this browser; they do not sync between devices.\n\nThere is no live AICTE connection, email service, or operational maintenance schedule. Administrators can publish a maintenance notice here when demonstrating that scenario.",
  },
  {
    id: "PN-4",
    title: "Know the documents before you begin",
    category: "Guidance",
    publishedOn: "2026-10-04",
    pinned: false,
    published: true,
    summary: "Find the mandatory and supporting evidence used in the sample approval workflow.",
    body: "The prototype checklist includes land or lease documents, building completion, fire safety, an affidavit, faculty qualifications, audited finances, and university affiliation. Structural stability evidence is also available in the sample checklist.\n\nThe document requirements shown here are demonstration data. Always consult current official guidance for a real submission.",
    link: "/resources",
  },
];

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  designation: string;
  institutionId?: string;
  password: string;
  active: boolean;
}
export interface Institution {
  id: string;
  name: string;
  aicteId: string;
  state: string;
  city: string;
  type: string;
}
export interface Doc {
  versions?: DocumentVersion[];
  code: string;
  name: string;
  mandatory: boolean;
  status: DocStatus;
  fileName?: string;
  uploadedOn?: string;
  checkedBy?: string;
  checkedOn?: string;
  findings?: string;
}
export interface Details {
  programme: string;
  course: string;
  intake: number;
  academicYear: string;
  landArea: number;
  builtUpArea: number;
  facultyCount: number;
  principal: string;
  address: string;
}
export interface HistoryEntry {
  at: string;
  by: string;
  action: string;
  remark?: string;
}
export interface Decision {
  decision: "Approved" | "Rejected";
  officer: string;
  reason: string;
  at: string;
}
export interface Inspection {
  date: string;
  inspector: string;
  observations: string;
  recommendation: string;
}
export interface Application {
  precheck?: SavedPrecheck;
  id: string;
  ref: string;
  institutionId: string;
  type: string;
  status: AppStatus;
  details: Details;
  documents: Doc[];
  createdOn: string;
  submittedOn?: string;
  assignedOfficer?: string;
  history: HistoryEntry[];
  frozen?: { details: Details; documents: Doc[]; submittedOn: string };
  decision?: Decision;
  inspection?: Inspection;
}
export interface Deficiency {
  draftResponse?: string;
  draftAttachment?: string;
  draftSavedOn?: string;
  id: string;
  appId: string;
  category: string;
  description: string;
  raisedBy: string;
  raisedOn: string;
  dueOn: string;
  status: "Open" | "Responded" | "Closed";
  response?: string;
  respondedOn?: string;
  closedBy?: string;
  closedOn?: string;
  closeRemark?: string;
}
export interface AuditEntry {
  id: string;
  at: string;
  actor: string;
  role: Role | "system";
  action: string;
  ref: string;
}
export interface Notification {
  id: string;
  at: string;
  role: Role | "public";
  institutionId?: string;
  text: string;
  link?: string;
  read?: boolean;
}
export interface Rule {
  id: string;
  code: string;
  title: string;
  clause: string;
  description: string;
  active: boolean;
}
export interface Connector {
  id: string;
  name: string;
  purpose: string;
  endpoint: string;
  status: "Operational" | "Degraded" | "Disabled";
  lastSync: string;
}
export interface Article {
  id: string;
  title: string;
  category: string;
  updated: string;
  body: string;
}

export const APP_TYPES = [
  {
    code: "NEW",
    name: "Establishment of New Technical Institution",
    desc: "Grant of approval for setting up a new institution offering technical programmes.",
  },
  {
    code: "EOA",
    name: "Extension of Approval (EoA)",
    desc: "Continuation of approval for an existing institution for the next academic year.",
  },
  {
    code: "INT",
    name: "Increase in Intake",
    desc: "Enhancement of approved intake in an existing course.",
  },
  {
    code: "NCR",
    name: "Introduction of New Course",
    desc: "Addition of a new course or programme in an existing institution.",
  },
  {
    code: "CLO",
    name: "Closure of Course / Institution",
    desc: "Progressive or complete closure of programmes.",
  },
];

export const DOC_TEMPLATE: Omit<Doc, "status">[] = [
  { code: "D01", name: "Land Registration / Lease Deed", mandatory: true },
  { code: "D02", name: "Building Completion Certificate", mandatory: true },
  { code: "D03", name: "Fire Safety Certificate", mandatory: true },
  { code: "D04", name: "Affidavit on Non-Judicial Stamp Paper", mandatory: true },
  { code: "D05", name: "Faculty List with Qualifications", mandatory: true },
  { code: "D06", name: "Audited Financial Statement (FY 2025-26)", mandatory: true },
  { code: "D07", name: "University Affiliation Letter", mandatory: true },
  { code: "D08", name: "Structural Stability Certificate", mandatory: false },
];

export const institutions: Institution[] = [
  {
    id: "INS-1-4412",
    name: "Shri Venkateshwara Institute of Technology",
    aicteId: "1-4412873",
    state: "Maharashtra",
    city: "Pune",
    type: "Private Self-Financing",
  },
  {
    id: "INS-1-3301",
    name: "Government Engineering College, Bhilai",
    aicteId: "1-3301156",
    state: "Chhattisgarh",
    city: "Durg",
    type: "Government",
  },
  {
    id: "INS-1-5520",
    name: "Narmada Valley College of Engineering",
    aicteId: "1-5520934",
    state: "Madhya Pradesh",
    city: "Jabalpur",
    type: "Private Self-Financing",
  },
  {
    id: "INS-1-2087",
    name: "Coastal Institute of Management Studies",
    aicteId: "1-2087401",
    state: "Kerala",
    city: "Kochi",
    type: "Private Aided",
  },
  {
    id: "INS-1-6634",
    name: "Rajputana Polytechnic College",
    aicteId: "1-6634218",
    state: "Rajasthan",
    city: "Jaipur",
    type: "Private Self-Financing",
  },
];

export const PASSWORD = "Aicte@2026";
export const users: User[] = [
  {
    id: "inst.svit",
    name: "Dr. Meera Kulkarni",
    email: "principal@svit.edu.in",
    role: "institution",
    designation: "Principal",
    institutionId: "INS-1-4412",
    password: PASSWORD,
    active: true,
  },
  {
    id: "inst.gecb",
    name: "Dr. Ramesh Sahu",
    email: "principal@gecbhilai.ac.in",
    role: "institution",
    designation: "Principal",
    institutionId: "INS-1-3301",
    password: PASSWORD,
    active: true,
  },
  {
    id: "inst.nvce",
    name: "Prof. Anil Tiwari",
    email: "director@nvce.ac.in",
    role: "institution",
    designation: "Director",
    institutionId: "INS-1-5520",
    password: PASSWORD,
    active: true,
  },
  {
    id: "inst.cims",
    name: "Dr. Thomas Mathew",
    email: "director@cims.edu.in",
    role: "institution",
    designation: "Director",
    institutionId: "INS-1-2087",
    password: PASSWORD,
    active: true,
  },
  {
    id: "inst.rpc",
    name: "Sh. Vikram Rathore",
    email: "principal@rpcjaipur.in",
    role: "institution",
    designation: "Principal",
    institutionId: "INS-1-6634",
    password: PASSWORD,
    active: true,
  },
  {
    id: "off.sharma",
    name: "Sh. Arvind Sharma",
    email: "arvind.sharma@aicte-india.org",
    role: "officer",
    designation: "Assistant Director (Approvals)",
    password: PASSWORD,
    active: true,
  },
  {
    id: "off.iyer",
    name: "Smt. Lakshmi Iyer",
    email: "lakshmi.iyer@aicte-india.org",
    role: "officer",
    designation: "Deputy Director (Approvals)",
    password: PASSWORD,
    active: true,
  },
  {
    id: "admin",
    name: "Sh. Pradeep Menon",
    email: "pradeep.menon@aicte-india.org",
    role: "admin",
    designation: "System Administrator",
    password: PASSWORD,
    active: true,
  },
];

const docs = (states: DocStatus[], checkedBy = "Sh. Arvind Sharma"): Doc[] =>
  DOC_TEMPLATE.map((d, i) => {
    const status = states[i] ?? "Not Submitted";
    const base: Doc = { ...d, status };
    if (status !== "Not Submitted") {
      base.fileName = `${d.code}_${d.name.split(" ")[0].toLowerCase()}.pdf`;
      base.uploadedOn = "2026-09-12";
    }
    if (status === "Verified")
      Object.assign(base, {
        checkedBy,
        checkedOn: "2026-10-02",
        findings:
          "Document authenticated against issuing authority records. Seal, signature and registration number match.",
      });
    if (status === "Mismatch Found")
      Object.assign(base, {
        checkedBy,
        checkedOn: "2026-10-03",
        findings:
          "Area stated in document does not match the area declared in the application form.",
      });
    return base;
  });

const det = (p: Partial<Details>): Details => ({
  programme: "Engineering & Technology",
  course: "B.Tech Computer Science & Engineering",
  intake: 120,
  academicYear: "2026-27",
  landArea: 10,
  builtUpArea: 9500,
  facultyCount: 8,
  principal: "",
  address: "",
  ...p,
});

export const applications: Application[] = [
  {
    id: "APP-01482",
    ref: "AICTE/2026/APP/01482",
    institutionId: "INS-1-4412",
    type: "Increase in Intake",
    status: "Deficiency Raised",
    createdOn: "2026-09-01",
    submittedOn: "2026-09-14",
    assignedOfficer: "Sh. Arvind Sharma",
    details: det({
      course: "B.Tech Computer Science & Engineering",
      intake: 180,
      facultyCount: 8,
      landArea: 12.5,
      builtUpArea: 11800,
      principal: "Dr. Meera Kulkarni",
      address: "Survey No. 54, Ambegaon Bk., Pune 411046",
    }),
    documents: docs([
      "Verified",
      "Mismatch Found",
      "Verified",
      "Verified",
      "Under Review",
      "Verified",
      "Verified",
      "Not Submitted",
    ]),
    history: [
      { at: "2026-09-01 10:12", by: "Dr. Meera Kulkarni", action: "Draft created" },
      { at: "2026-09-14 16:40", by: "Dr. Meera Kulkarni", action: "Application submitted" },
      { at: "2026-09-20 11:05", by: "Sh. Arvind Sharma", action: "Scrutiny commenced" },
      {
        at: "2026-10-03 15:22",
        by: "Sh. Arvind Sharma",
        action: "Deficiency raised",
        remark: "Built-up area mismatch in Building Completion Certificate",
      },
    ],
  },
  {
    id: "APP-01377",
    ref: "AICTE/2026/APP/01377",
    institutionId: "INS-1-4412",
    type: "Extension of Approval (EoA)",
    status: "Approved",
    createdOn: "2026-07-10",
    submittedOn: "2026-07-25",
    assignedOfficer: "Smt. Lakshmi Iyer",
    details: det({
      course: "M.Tech Structural Engineering",
      programme: "Engineering & Technology",
      intake: 18,
      facultyCount: 4,
      landArea: 12.5,
      builtUpArea: 11800,
      principal: "Dr. Meera Kulkarni",
      address: "Survey No. 54, Ambegaon Bk., Pune 411046",
    }),
    documents: docs(
      [
        "Verified",
        "Verified",
        "Verified",
        "Verified",
        "Verified",
        "Verified",
        "Verified",
        "Verified",
      ],
      "Smt. Lakshmi Iyer",
    ),
    decision: {
      decision: "Approved",
      officer: "Smt. Lakshmi Iyer",
      reason:
        "All mandatory norms under APH 2026-27 Clause 4.2 satisfied. Faculty and infrastructure verified.",
      at: "2026-08-21 12:30",
    },
    history: [
      { at: "2026-07-25 09:15", by: "Dr. Meera Kulkarni", action: "Application submitted" },
      {
        at: "2026-08-21 12:30",
        by: "Smt. Lakshmi Iyer",
        action: "Approved",
        remark: "All mandatory norms satisfied",
      },
    ],
  },
  {
    id: "APP-01519",
    ref: "AICTE/2026/APP/01519",
    institutionId: "INS-1-3301",
    type: "Introduction of New Course",
    status: "Under Scrutiny",
    createdOn: "2026-09-05",
    submittedOn: "2026-09-22",
    assignedOfficer: "Sh. Arvind Sharma",
    details: det({
      course: "B.Tech Artificial Intelligence & Data Science",
      intake: 60,
      facultyCount: 4,
      landArea: 28,
      builtUpArea: 24000,
      principal: "Dr. Ramesh Sahu",
      address: "Sector 6, Bhilai Nagar, Durg 490006",
    }),
    documents: docs([
      "Verified",
      "Verified",
      "Under Review",
      "Verified",
      "Under Review",
      "Under Review",
      "Verified",
      "Verified",
    ]),
    history: [
      { at: "2026-09-22 14:02", by: "Dr. Ramesh Sahu", action: "Application submitted" },
      { at: "2026-09-29 10:40", by: "Sh. Arvind Sharma", action: "Scrutiny commenced" },
    ],
  },
  {
    id: "APP-01544",
    ref: "AICTE/2026/APP/01544",
    institutionId: "INS-1-5520",
    type: "Establishment of New Technical Institution",
    status: "Submitted",
    createdOn: "2026-09-18",
    submittedOn: "2026-10-06",
    details: det({
      course: "B.Tech Mechanical Engineering",
      intake: 60,
      facultyCount: 3,
      landArea: 5,
      builtUpArea: 5200,
      principal: "Prof. Anil Tiwari",
      address: "Village Tilwara, NH-34, Jabalpur 482003",
    }),
    documents: docs([
      "Under Review",
      "Under Review",
      "Under Review",
      "Under Review",
      "Under Review",
      "Under Review",
      "Under Review",
      "Not Submitted",
    ]),
    history: [{ at: "2026-10-06 17:55", by: "Prof. Anil Tiwari", action: "Application submitted" }],
  },
  {
    id: "APP-01291",
    ref: "AICTE/2026/APP/01291",
    institutionId: "INS-1-2087",
    type: "Increase in Intake",
    status: "Rejected",
    createdOn: "2026-06-11",
    submittedOn: "2026-06-30",
    assignedOfficer: "Smt. Lakshmi Iyer",
    details: det({
      programme: "Management",
      course: "MBA (Full Time)",
      intake: 240,
      facultyCount: 6,
      landArea: 2,
      builtUpArea: 3100,
      principal: "Dr. Thomas Mathew",
      address: "Marine Drive, Ernakulam, Kochi 682031",
    }),
    documents: docs(
      [
        "Mismatch Found",
        "Verified",
        "Verified",
        "Verified",
        "Mismatch Found",
        "Verified",
        "Verified",
        "Not Submitted",
      ],
      "Smt. Lakshmi Iyer",
    ),
    decision: {
      decision: "Rejected",
      officer: "Smt. Lakshmi Iyer",
      reason:
        "Faculty-student ratio of 1:40 against prescribed 1:20 (APH Clause 5.1). Land area below minimum norm. Deficiency not rectified within stipulated period.",
      at: "2026-08-04 16:10",
    },
    history: [
      { at: "2026-06-30 11:20", by: "Dr. Thomas Mathew", action: "Application submitted" },
      {
        at: "2026-08-04 16:10",
        by: "Smt. Lakshmi Iyer",
        action: "Rejected",
        remark: "Faculty-student ratio not met",
      },
    ],
  },
  {
    id: "APP-01603",
    ref: "AICTE/2026/APP/01603",
    institutionId: "INS-1-6634",
    type: "Extension of Approval (EoA)",
    status: "Draft",
    createdOn: "2026-10-20",
    details: det({
      programme: "Engineering & Technology",
      course: "Diploma in Civil Engineering",
      intake: 60,
      facultyCount: 2,
      landArea: 3,
      builtUpArea: 2800,
      principal: "Sh. Vikram Rathore",
      address: "Plot 17, Sitapura Industrial Area, Jaipur 302022",
    }),
    documents: docs([
      "Under Review",
      "Under Review",
      "Not Submitted",
      "Not Submitted",
      "Not Submitted",
      "Not Submitted",
      "Not Submitted",
      "Not Submitted",
    ]),
    history: [{ at: "2026-10-20 12:00", by: "Sh. Vikram Rathore", action: "Draft created" }],
  },
  {
    id: "APP-01588",
    ref: "AICTE/2026/APP/01588",
    institutionId: "INS-1-3301",
    type: "Extension of Approval (EoA)",
    status: "Approved",
    createdOn: "2026-08-02",
    submittedOn: "2026-08-12",
    assignedOfficer: "Sh. Arvind Sharma",
    details: det({
      course: "B.Tech Electrical Engineering",
      intake: 120,
      facultyCount: 7,
      landArea: 28,
      builtUpArea: 24000,
      principal: "Dr. Ramesh Sahu",
      address: "Sector 6, Bhilai Nagar, Durg 490006",
    }),
    documents: docs([
      "Verified",
      "Verified",
      "Verified",
      "Verified",
      "Verified",
      "Verified",
      "Verified",
      "Verified",
    ]),
    decision: {
      decision: "Approved",
      officer: "Sh. Arvind Sharma",
      reason: "Compliant with all applicable norms; physical verification report satisfactory.",
      at: "2026-09-10 11:45",
    },
    history: [
      { at: "2026-08-12 10:00", by: "Dr. Ramesh Sahu", action: "Application submitted" },
      {
        at: "2026-09-10 11:45",
        by: "Sh. Arvind Sharma",
        action: "Approved",
        remark: "Compliant with all applicable norms",
      },
    ],
  },
];
for (const a of applications)
  if (a.submittedOn)
    a.frozen = {
      details: { ...a.details },
      documents: a.documents.map((d) => ({ ...d })),
      submittedOn: a.submittedOn,
    };

export const deficiencies: Deficiency[] = [
  {
    id: "DEF-0912",
    appId: "APP-01482",
    category: "Infrastructure",
    description:
      "Built-up area stated in the Building Completion Certificate (9,850 sq.m) does not match the area declared in the application (11,800 sq.m). Submit a corrected certificate issued by the competent authority.",
    raisedBy: "Sh. Arvind Sharma",
    raisedOn: "2026-10-03",
    dueOn: "2026-11-02",
    status: "Open",
  },
  {
    id: "DEF-0874",
    appId: "APP-01291",
    category: "Faculty",
    description:
      "Faculty list indicates 6 full-time faculty against a requirement of 12 for the proposed intake of 240.",
    raisedBy: "Smt. Lakshmi Iyer",
    raisedOn: "2026-07-12",
    dueOn: "2026-08-01",
    status: "Closed",
    response: "Recruitment of additional faculty is in process.",
    respondedOn: "2026-07-30",
    closedBy: "Smt. Lakshmi Iyer",
    closedOn: "2026-08-04",
    closeRemark: "Response not satisfactory; considered in final decision.",
  },
];

export const audit: AuditEntry[] = [
  {
    id: "AU-1",
    at: "2026-10-06 17:55",
    actor: "Prof. Anil Tiwari",
    role: "institution",
    action: "Application submitted",
    ref: "AICTE/2026/APP/01544",
  },
  {
    id: "AU-2",
    at: "2026-10-03 15:22",
    actor: "Sh. Arvind Sharma",
    role: "officer",
    action: "Deficiency DEF-0912 raised",
    ref: "AICTE/2026/APP/01482",
  },
  {
    id: "AU-3",
    at: "2026-10-03 15:10",
    actor: "Sh. Arvind Sharma",
    role: "officer",
    action: "Document D02 marked Mismatch Found",
    ref: "AICTE/2026/APP/01482",
  },
  {
    id: "AU-4",
    at: "2026-09-29 10:40",
    actor: "Sh. Arvind Sharma",
    role: "officer",
    action: "Scrutiny commenced",
    ref: "AICTE/2026/APP/01519",
  },
  {
    id: "AU-5",
    at: "2026-09-10 11:45",
    actor: "Sh. Arvind Sharma",
    role: "officer",
    action: "Application approved",
    ref: "AICTE/2026/APP/01588",
  },
  {
    id: "AU-6",
    at: "2026-09-02 09:30",
    actor: "Sh. Pradeep Menon",
    role: "admin",
    action: "Rule R-05 updated",
    ref: "Rule Library",
  },
  {
    id: "AU-7",
    at: "2026-08-04 16:10",
    actor: "Smt. Lakshmi Iyer",
    role: "officer",
    action: "Application rejected",
    ref: "AICTE/2026/APP/01291",
  },
];

export const notifications: Notification[] = [
  {
    id: "N-1",
    at: "2026-10-25",
    role: "public",
    text: "Approval Process Handbook 2026-27 (Revised) published. Institutions are advised to refer to the revised Clause 5.1 on faculty norms.",
    link: "/admin/knowledge",
  },
  {
    id: "N-2",
    at: "2026-10-18",
    role: "public",
    text: "Last date for submission of applications for Extension of Approval extended to 15 November 2026.",
  },
  {
    id: "N-3",
    at: "2026-10-10",
    role: "public",
    text: "Scheduled maintenance of the portal on 2 November 2026 between 22:00 and 02:00 hrs IST.",
  },
  {
    id: "N-4",
    at: "2026-10-03",
    role: "institution",
    institutionId: "INS-1-4412",
    text: "Deficiency Notice DEF-0912 issued against AICTE/2026/APP/01482. Respond by 02 Nov 2026.",
    link: "/institution/deficiencies/DEF-0912/respond",
  },
  {
    id: "N-5",
    at: "2026-10-06",
    role: "officer",
    text: "New application AICTE/2026/APP/01544 received in case queue.",
    link: "/officer/cases/APP-01544/overview",
  },
];

export const rules: Rule[] = [
  {
    id: "R-01",
    code: "APH-5.1",
    title: "Faculty-Student Ratio",
    clause: "APH 2026-27, Clause 5.1",
    description: "Full-time faculty shall be not less than intake / 20.",
    active: true,
  },
  {
    id: "R-02",
    code: "APH-3.2",
    title: "Minimum Land Area",
    clause: "APH 2026-27, Clause 3.2",
    description: "Land area shall be not less than 2.5 acres.",
    active: true,
  },
  {
    id: "R-03",
    code: "APH-3.4",
    title: "Minimum Built-up Area",
    clause: "APH 2026-27, Clause 3.4",
    description: "Built-up area shall be not less than 1,000 sq.m plus 5 sq.m per sanctioned seat.",
    active: true,
  },
  {
    id: "R-04",
    code: "APH-2.6",
    title: "Mandatory Documents",
    clause: "APH 2026-27, Clause 2.6",
    description: "All mandatory documents in the checklist shall be uploaded.",
    active: true,
  },
  {
    id: "R-05",
    code: "APH-1.3",
    title: "Academic Year",
    clause: "APH 2026-27, Clause 1.3",
    description: "Application shall pertain to academic year 2026-27.",
    active: true,
  },
];

export const connectors: Connector[] = [
  {
    id: "C-1",
    name: "DigiLocker Issued Documents",
    purpose: "Fetch and verify government-issued certificates",
    endpoint: "api.digitallocker.gov.in",
    status: "Operational",
    lastSync: "2026-10-28 13:30",
  },
  {
    id: "C-2",
    name: "State Land Records (Bhulekh)",
    purpose: "Verify land ownership and area",
    endpoint: "landrecords.state.gov.in",
    status: "Degraded",
    lastSync: "2026-10-28 09:12",
  },
  {
    id: "C-3",
    name: "AISHE Institution Registry",
    purpose: "Cross-check institution identity",
    endpoint: "aishe.gov.in/api",
    status: "Operational",
    lastSync: "2026-10-28 12:55",
  },
  {
    id: "C-4",
    name: "Faculty Registry (AICTE)",
    purpose: "Validate faculty PAN and qualification",
    endpoint: "facultyregistry.aicte-india.org",
    status: "Operational",
    lastSync: "2026-10-28 13:02",
  },
  {
    id: "C-5",
    name: "Fire Services NOC Portal",
    purpose: "Verify fire safety certificates",
    endpoint: "firenoc.state.gov.in",
    status: "Disabled",
    lastSync: "2026-10-14 18:20",
  },
];

export const articles: Article[] = [
  {
    id: "K-1",
    title: "Approval Process Handbook 2026-27: Summary of Changes",
    category: "Regulations",
    updated: "2026-10-25",
    body: "The revised handbook amends Clause 5.1 (faculty norms), introduces online physical verification for Extension of Approval, and prescribes timelines for deficiency rectification (30 days from date of issue).",
  },
  {
    id: "K-2",
    title: "Procedure for Responding to a Deficiency Notice",
    category: "Procedure",
    updated: "2026-09-12",
    body: "Institutions shall submit a written response with supporting documents through the Deficiencies section before the due date. The concerned officer will re-verify and record closure with remarks.",
  },
  {
    id: "K-3",
    title: "Document Authenticity Verification Method",
    category: "Officer Manual",
    updated: "2026-08-30",
    body: "Each document is checked for digital signature validity, issuer registry match through connected services, and consistency of declared values with the application form.",
  },
  {
    id: "K-4",
    title: "Grounds for Rejection of Applications",
    category: "Regulations",
    updated: "2026-07-18",
    body: "Applications may be rejected for non-compliance with mandatory norms, submission of false information, or failure to rectify deficiencies within the stipulated period. Every decision must record the officer's name and reason.",
  },
];
