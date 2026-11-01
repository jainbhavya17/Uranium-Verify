import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/institution/dashboard")({ component: Page });
function Page() {
  return <FeaturePage routeId="I01" title="Institution Dashboard" role="institution" />;
}
