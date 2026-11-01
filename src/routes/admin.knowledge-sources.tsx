import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/admin/knowledge-sources")({ component: Page });
function Page() {
  return <FeaturePage routeId="A05" title="Knowledge Sources" role="admin" />;
}
