import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/admin/connectors")({ component: Page });
function Page() {
  return <FeaturePage routeId="A03" title="Connectors" role="admin" />;
}
