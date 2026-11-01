import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/institution/applications/")({ component: Page });
function Page() {
  return <FeaturePage routeId="I02" title="My Applications" role="institution" />;
}
