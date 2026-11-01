import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/institution/applications/new")({ component: Page });
function Page() {
  return <FeaturePage routeId="I03" title="New Application" role="institution" />;
}
