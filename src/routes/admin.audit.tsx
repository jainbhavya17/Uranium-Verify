import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/admin/audit")({ component: Page });
function Page() {
  return <FeaturePage routeId="A04" title="Audit Trail" role="admin" />;
}
