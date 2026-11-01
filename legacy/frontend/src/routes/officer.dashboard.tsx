import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import {
  ArrowRight,
  Files,
  Clock3,
  FileCheck2,
  MessageSquare,
  CircleCheck,
  BookOpen,
} from "lucide-react";
import { InnerPage, Panel, Status, EmptyRow, instName, MetricCard } from "@/components/portal";
import { Link } from "@/components/link";
import { useCurrentUser, useStore } from "@/lib/store";
import { seo } from "@/lib/seo";
export const Route = createFileRoute("/officer/dashboard")({
  head: seo("Officer Dashboard", "Assigned cases, pending verifications and deficiency responses."),
  component: Page,
});
function Page() {
  const user = useCurrentUser();
  const apps = useStore((s) => s.applications.filter((a) => a.status !== "Draft"));
  const defs = useStore((s) => s.deficiencies.filter((d) => d.status === "Responded"));
  const pendingDocs = apps.flatMap((a) =>
    a.documents.filter((d) => d.status === "Under Review"),
  ).length;
  const mine = apps.filter((a) => a.assignedOfficer === user?.name && !a.decision);
  return (
    <InnerPage
      role="officer"
      crumbs={[{ label: "Overview" }]}
      title="Officer Dashboard"
      actions={
        <Link to="/officer/queue" className="btn btn-primary">
          Open case queue <ArrowRight size={15} />
        </Link>
      }
    >
      <div className="metrics-grid">
        <MetricCard
          label="New submissions"
          value={apps.filter((a) => a.status === "Submitted").length}
          hint="Ready to take up"
          icon={Files}
          to="/officer/queue"
          search={{ status: "Submitted" }}
        />
        <MetricCard
          label="Under scrutiny"
          value={apps.filter((a) => a.status === "Under Scrutiny").length}
          hint="Continue case review"
          icon={Clock3}
          to="/officer/queue"
          search={{ status: "Under Scrutiny" }}
          tone="blue"
        />
        <MetricCard
          label="Documents pending"
          value={pendingDocs}
          hint="Verify supporting evidence"
          icon={FileCheck2}
          to="/officer/verification-queue"
          tone="amber"
        />
        <MetricCard
          label="Responses received"
          value={defs.length}
          hint="Ready for re-verification"
          icon={MessageSquare}
          to="/officer/queue"
          search={{ status: "Deficiency Raised" }}
          tone="purple"
        />
      </div>
      <div className="dashboard-split">
        <div className="space-y-6">
          <Panel title="Cases assigned to you">
            <div className="overflow-x-auto">
              <DataTable className="gov-table">
                <thead>
                  <tr>
                    <th>Application / institution</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {mine.length === 0 ? (
                    <EmptyRow cols={4} />
                  ) : (
                    mine.map((a) => (
                      <tr key={a.id}>
                        <td>
                          <b className="font-semibold">{a.id}</b>
                          <div className="text-[10px] text-muted-foreground mt-1 max-w-[230px]">
                            {instName(a.institutionId)}
                          </div>
                        </td>
                        <td>{a.type}</td>
                        <td>
                          <Status s={a.status} />
                        </td>
                        <td>
                          <Link
                            to={`/officer/cases/${a.id}/overview`}
                            className="link flex gap-2 items-center whitespace-nowrap"
                          >
                            Review case <ArrowRight size={13} />
                          </Link>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </DataTable>
            </div>
            <div className="mt-4 pt-4 border-t border-border flex justify-between text-[10px] text-muted-foreground">
              <span>{mine.length} active cases assigned to you</span>
              <Link to="/officer/queue" className="link">
                View all cases →
              </Link>
            </div>
          </Panel>
          <Panel title="Responses awaiting re-verification">
            <DataTable className="gov-table">
              <thead>
                <tr>
                  <th>Notice</th>
                  <th>Application</th>
                  <th>Received</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {defs.length === 0 ? (
                  <EmptyRow cols={4} />
                ) : (
                  defs.map((d) => (
                    <tr key={d.id}>
                      <td>{d.id}</td>
                      <td>{apps.find((a) => a.id === d.appId)?.ref}</td>
                      <td>{d.respondedOn}</td>
                      <td>
                        <Link to={`/officer/cases/${d.appId}/review`} className="link">
                          Re-verify →
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </DataTable>
          </Panel>
        </div>
        <div className="space-y-6">
          <Panel title="Review pipeline">
            {["Submitted", "Under Scrutiny", "Deficiency Raised", "Approved", "Rejected"].map(
              (s) => {
                const count = apps.filter((a) => a.status === s).length;
                return (
                  <Link
                    to="/officer/queue"
                    search={{ status: s }}
                    key={s}
                    className="block py-3 border-b border-border last:border-0"
                  >
                    <div className="flex justify-between text-[11px] mb-2">
                      <span className="text-muted-foreground">{s}</span>
                      <span className="font-semibold text-navy">{count}</span>
                    </div>
                    <div className="h-1 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-teal/60"
                        style={{ width: `${apps.length ? (count / apps.length) * 100 : 0}%` }}
                      />
                    </div>
                  </Link>
                );
              },
            )}
            <Link to="/officer/reports" className="link text-[11px] flex items-center gap-2 mt-5">
              Explore reports <ArrowRight size={13} />
            </Link>
          </Panel>
          <Panel title="Review with confidence">
            <BookOpen size={25} className="text-teal mb-3" strokeWidth={1.5} />
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              Refer to the approval handbook and verification procedures as you review each case.
            </p>
            <Link to="/admin/knowledge" className="link text-[11px] flex items-center gap-2 mt-4">
              Open knowledge base <ArrowRight size={13} />
            </Link>
          </Panel>
          <div className="flex gap-2 text-[10px] text-muted-foreground px-2">
            <CircleCheck size={14} className="text-teal shrink-0" /> Every recorded outcome is added
            to the audit trail.
          </div>
        </div>
      </div>
    </InnerPage>
  );
}
