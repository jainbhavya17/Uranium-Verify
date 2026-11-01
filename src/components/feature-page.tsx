import { InnerPage, AccessDenied } from "./portal";
import { Link } from "./link";
import { useCurrentUser, type PortalRole } from "@/lib/backend-session";
import { InstitutionContent, InstitutionSteps } from "@/features/institution/InstitutionPages";
import { ScrutinyContent } from "@/features/officer/ScrutinyPages";
import { GovernanceContent } from "@/features/officer/GovernancePages";
import {
  PortalDashboard,
  PortalApplications,
  PortalCasePage,
  PortalClarifications,
  PortalResponse,
  PortalVerificationQueue,
  PortalReports,
  PortalNotifications,
} from "@/features/portal/RestoredPortal";
import { AccountPage, PreferenceEffect } from "@/features/release/ReleasePages";

export function FeaturePage({
  routeId,
  id,
  title,
  role,
}: {
  routeId: string;
  id?: string;
  title: string;
  role?: PortalRole;
}) {
  const user = useCurrentUser();
  const permitted =
    !user ||
    ((!routeId.startsWith("A") ||
      user.roles.includes("admin") ||
      (routeId === "A04" && user.roles.includes("auditor"))) &&
      (!routeId.startsWith("O") ||
        user.roles.some((r) => ["officer", "supervisor"].includes(r)) ||
        (user.roles.includes("specialist") && ["O04", "O09"].includes(routeId))));
  return (
    <InnerPage
      title={title}
      role={role ?? ["institution", "officer", "admin"]}
      crumbs={[{ label: title }]}
    >
      {!permitted ? (
        <AccessDenied />
      ) : (
        user && (
          <div className="workflow-content">
            <PreferenceEffect user={user} />
            {routeId.startsWith("I") && (
              <>
                {["I03", "I04", "I05", "I06", "I07", "I08"].includes(routeId) && (
                  <InstitutionSteps routeId={routeId} caseId={id} />
                )}
                {routeId === "I01" ? (
                  <PortalDashboard />
                ) : routeId === "I02" ? (
                  <PortalApplications />
                ) : routeId === "I09" ? (
                  <PortalCasePage id={id!} user={user} />
                ) : routeId === "I06" && id?.startsWith("APP-") && id !== "APP-01603" ? (
                  <PortalCasePage id={id} user={user} section="documents" />
                ) : (
                  <InstitutionContent routeId={routeId} caseId={id} recordId={id} user={user} />
                )}
              </>
            )}
            {routeId.startsWith("O") && (
              <>
                {id && (
                  <nav className="section-nav" aria-label="Case sections">
                    {[
                      "overview",
                      "evidence",
                      "authenticity",
                      "compliance",
                      "inspection",
                      "review",
                    ].map((p) => (
                      <Link key={p} to={`/officer/cases/${id}/${p}`}>
                        {p}
                      </Link>
                    ))}
                  </nav>
                )}
                {user.roles.includes("specialist") &&
                !user.roles.some((r) => ["officer", "supervisor"].includes(r)) ? (
                  <ScrutinyContent routeId={routeId} caseId={id} user={user} />
                ) : routeId === "O01" ? (
                  <PortalDashboard officer />
                ) : routeId === "O02" ? (
                  <PortalApplications officer />
                ) : routeId === "O09" ? (
                  <PortalVerificationQueue user={user} />
                ) : routeId === "O10" ? (
                  <PortalReports user={user} />
                ) : (
                  <PortalCasePage
                    id={id!}
                    user={user}
                    section={
                      (
                        {
                          O03: "overview",
                          O04: "documents",
                          O05: "authenticity",
                          O06: "compliance",
                          O07: "inspection",
                          O08: "review",
                        } as Record<string, string>
                      )[routeId]
                    }
                  />
                )}
              </>
            )}
            {routeId.startsWith("A") && <GovernanceContent routeId={routeId} user={user} />}
            {routeId === "notifications" && <PortalNotifications />}
            {routeId === "settings" && <AccountPage user={user} />}
            {routeId === "clarifications" && <PortalClarifications />}
            {routeId === "response" && <PortalResponse id={id!} user={user} />}
          </div>
        )
      )}
    </InnerPage>
  );
}
