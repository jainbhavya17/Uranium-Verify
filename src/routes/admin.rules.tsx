import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/admin/rules")({ component: Page });
function Page() {
  return <FeaturePage routeId="A02" title="Rule Library" role="admin" />;
}
