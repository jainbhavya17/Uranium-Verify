import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/officer/reports")({ component: Page });
function Page() {
  return <FeaturePage routeId="O10" title="Reports" role="officer" />;
}
