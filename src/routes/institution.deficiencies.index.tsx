import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/institution/deficiencies/")({ component: Page });
function Page() {
  return <FeaturePage routeId="clarifications" title="Deficiencies" role="institution" />;
}
