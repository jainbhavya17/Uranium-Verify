import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import {
  ArrowRight,
  Plus,
  Files,
  Clock3,
  CircleCheck,
  AlertCircle,
  FileText,
  BookOpen,
  Building2,
} from "lucide-react";
import { InnerPage, Panel, Status, EmptyRow, instName, MetricCard } from "@/components/portal";
import { Link } from "@/components/link";
import { useCurrentUser, useStore } from "@/lib/store";
import { seo } from "@/lib/seo";
export const Route = createFileRoute("/institution/dashboard")({
  head: seo(
    "Institution Dashboard",
    "Summary of applications and deficiency notices for your institution.",
  ),
  component: Dash,
});
function Dash() {
  const user = useCurrentUser();
  const apps = useStore((s) =>
    s.applications.filter((a) => a.institutionId === user?.institutionId),
  );
  const defs = useStore((s) =>
    s.deficiencies.filter((d) => d.status === "Open" && apps.some((a) => a.id === d.appId)),
  );
  const drafts = apps.filter((a) => a.status === "Draft");
  const pending = apps.filter((a) =>
    ["Submitted", "Under Scrutiny", "Deficiency Raised"].includes(a.status),
  );
  return (
    <InnerPage
      role="institution"
      crumbs={[{ label: "Overview" }]}
      title="Institution Dashboard"
      actions={
        <Link to="/institution/applications/new" className="btn btn-primary">
          <Plus size={15} /> New application
        </Link>
      }
    >
      {user && (
        <>
          <div className="flex items-center gap-2 text-[11px] text-muted-foreground mb-5">
            <Building2 size={15} />
            <span>{instName(user.institutionId!)}</span>
            <span className="ml-auto hidden lg:inline">Welcome back, {user.name}</span>
          </div>
          <div className="metrics-grid">
            <MetricCard
              label="Total applications"
              value={apps.length}
              hint="View all applications"
              icon={Files}
              to="/institution/applications"
            />
            <MetricCard
              label="In review"
              value={pending.length}
              hint="Follow your progress"
              icon={Clock3}
              to="/institution/applications"
              tone="blue"
            />
            <MetricCard
              label="Approved"
              value={apps.filter((a) => a.status === "Approved").length}
              hint="View approval decisions"
              icon={CircleCheck}
              to="/institution/applications"
              search={{ status: "Approved" }}
            />
            <MetricCard
              label="Needs your attention"
              value={defs.length}
              hint="Respond to deficiencies"
              icon={AlertCircle}
              to="/institution/deficiencies"
              tone="amber"
            />
          </div>
          {defs.length > 0 && (
            <div className="action-banner">
              <AlertCircle size={20} className="shrink-0" />
              <div>
                <b>
                  You have {defs.length} pending deficiency{" "}
                  {defs.length === 1 ? "notice" : "notices"}
                </b>
                <p>Review the officer’s feedback and submit your response before the due date.</p>
              </div>
              <Link to="/institution/deficiencies">
                Review notices <ArrowRight size={14} />
              </Link>
            </div>
          )}
          <div className="dashboard-split">
            <div className="space-y-6">
              <Panel title="Recent applications">
                <div className="overflow-x-auto">
                  <DataTable className="gov-table">
                    <thead>
                      <tr>
                        <th>Application / course</th>
                        <th>Type</th>
                        <th>Status</th>
                        <th className="text-right">Next step</th>
                      </tr>
                    </thead>
                    <tbody>
                      {apps.length === 0 ? (
                        <EmptyRow cols={4} />
                      ) : (
                        apps.slice(0, 5).map((a) => (
                          <tr key={a.id}>
                            <td>
                              <span className="font-semibold text-navy">{a.id}</span>
                              <div className="text-[10px] text-muted-foreground mt-1 max-w-[220px]">
                                {a.details.course || "Course details pending"}
                              </div>
                            </td>
                            <td>{a.type}</td>
                            <td>
                              <Status s={a.status} />
                            </td>
                            <td>
                              <Link
                                className="link flex gap-2 items-center whitespace-nowrap"
                                to={
                                  a.status === "Draft"
                                    ? `/institution/applications/${a.id}/details`
                                    : `/institution/applications/${a.id}/status`
                                }
                              >
                                {a.status === "Draft" ? "Continue" : "View details"}
                                <ArrowRight size={13} />
                              </Link>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </DataTable>
                </div>
                <div className="flex items-center justify-between mt-4 pt-4 border-t border-border text-[10px] text-muted-foreground">
                  <span>{apps.length} applications in your workspace</span>
                  <Link to="/institution/applications" className="link flex gap-1 items-center">
                    View all applications <ArrowRight size={12} />
                  </Link>
                </div>
              </Panel>
              <Panel title="Your next steps">
                {drafts.length > 0 ? (
                  drafts.map((a) => (
                    <div key={a.id} className="deadline-item">
                      <span className="metric-icon">
                        <FileText size={17} />
                      </span>
                      <div className="flex-1">
                        <b>Complete your draft · {a.id}</b>
                        <p>
                          {a.documents.filter((d) => !!d.fileName).length} of {a.documents.length}{" "}
                          documents added
                        </p>
                      </div>
                      <Link
                        to={`/institution/applications/${a.id}/details`}
                        className="link text-[11px] self-center"
                      >
                        Continue <ArrowRight size={13} className="inline" />
                      </Link>
                    </div>
                  ))
                ) : (
                  <div className="flex items-center gap-3 text-[12px] text-muted-foreground py-2">
                    <CircleCheck size={21} className="text-teal" /> You’re all caught up. Track
                    existing applications or start a new one.
                  </div>
                )}
              </Panel>
            </div>
            <div className="space-y-6">
              <Panel title="Dates & reminders">
                <p className="workspace-note mb-3">
                  The dates below are sample MVP fixtures, not live AICTE deadlines.
                </p>
                <div className="deadline-item">
                  <span className="date-block">
                    15<small>Nov</small>
                  </span>
                  <div>
                    <b>Extension of approval</b>
                    <p>Submit by 15 November 2026</p>
                  </div>
                </div>
                <div className="deadline-item">
                  <span className="date-block">
                    30<small>Nov</small>
                  </span>
                  <div>
                    <b>New institution approval</b>
                    <p>Submit by 30 November 2026</p>
                  </div>
                </div>
                {defs.map((d) => (
                  <div className="deadline-item" key={d.id}>
                    <span className="metric-icon">
                      <AlertCircle size={17} />
                    </span>
                    <div>
                      <b>{d.id} response</b>
                      <p>Due {d.dueOn}</p>
                      <Link
                        to={`/institution/deficiencies/${d.id}/respond`}
                        className="link text-[10px]"
                      >
                        Prepare response →
                      </Link>
                    </div>
                  </div>
                ))}
              </Panel>
              <Panel title="Application essentials">
                <BookOpen size={25} strokeWidth={1.5} className="text-teal mb-3" />
                <p className="text-[12px] text-navy font-medium">
                  A little preparation goes a long way.
                </p>
                <p className="text-[11px] text-muted-foreground leading-relaxed my-3">
                  Check the document requirements and approval guidelines before submitting.
                </p>
                <Link to="/admin/knowledge" className="link text-[11px] flex items-center gap-2">
                  Explore the knowledge base <ArrowRight size={13} />
                </Link>
              </Panel>
            </div>
          </div>
        </>
      )}
    </InnerPage>
  );
}
