import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/officer/dashboard")({ component: Page });
function Page() {
  return <FeaturePage routeId="O01" title="Officer Dashboard" role="officer" />;
}
