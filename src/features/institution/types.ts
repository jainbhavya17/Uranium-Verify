import type { components } from "../../../packages/contracts/openapi";
export type Details = Required<components["schemas"]["DraftDetails"]>;
export type Course = components["schemas"]["CourseInput"];
export type Catalogue = Omit<components["schemas"]["CatalogueView"], "definition"> & {
  definition: {
    portal_revision?: number;
    is_mock: boolean;
    interpretation_status: string;
    eligibility: string;
    programmes: string[];
    procedural_stages: string[];
    document_package: string;
    source: { url: string; clause: string; notice_url: string };
    submission_channel: string;
    external_url: string | null;
    reference_date: string;
    window_label: string;
    depth: string;
  };
};
export type Profile = {
  name: string;
  permanent_id: string;
  address?: string;
  affiliation?: string;
  institution_type?: string;
  completion_date?: string;
  courses: { course: string; level: string; approved_intake: number }[];
  extended_eoa: boolean;
  prefill_source: string;
  prefill_source_year?: string | null;
};
export type Snapshot = Omit<components["schemas"]["SnapshotView"], "profile" | "payload"> & {
  profile: Profile;
  payload: {
    approval_reference?: string;
    changes?: string[];
    prior_findings?: { summary: string; corrective_action: string }[];
  };
};
export type Change = {
  field: string;
  approved: string | number | null;
  requested: string | number;
  interpretation: string;
  is_discrepancy: boolean;
};
export type Source = {
  url: string;
  clause: string;
  printed_page: number;
  pdf_page: number;
  interpretation_status: string;
};
export type Item = Omit<
  components["schemas"]["RequirementView"],
  "evidence" | "source" | "exception"
> & {
  source: Source;
  exception: {
    source_ref: string;
    reviewed_by: string;
    reviewed_at: number;
    is_mock: boolean;
  } | null;
  evidence: {
    id: string;
    document_id: string;
    number: number;
    name: string;
    status: string;
    sha256: string;
    is_mock: boolean;
    document_type: string;
  } | null;
};
export type Checklist = Omit<components["schemas"]["ChecklistView"], "items"> & { items: Item[] };
export type Receipt = components["schemas"]["ReceiptView"];
export type Workflow = Omit<
  components["schemas"]["DraftView"],
  "catalogue" | "baseline" | "details" | "changes" | "checklist" | "receipt"
> & {
  catalogue: Catalogue;
  baseline: Snapshot;
  details: Details;
  changes: Change[];
  checklist: Checklist;
  receipt: Receipt | null;
};
export type Readiness = Omit<components["schemas"]["ReadinessView"], "blocking" | "checklist"> & {
  checklist: Checklist;
  blocking: {
    code: string;
    message: string;
    field?: string;
    requirement_id?: string;
    source?: Source;
    version_id?: string;
    page?: number;
    bbox?: number[];
  }[];
};
