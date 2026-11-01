import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/officer/queue")({ component: Page });
function Page() {
  return <FeaturePage routeId="O02" title="Case Queue" role="officer" />;
}
