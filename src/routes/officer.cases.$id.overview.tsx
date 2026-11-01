import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/officer/cases/$id/overview")({ component: Page });
function Page() {
  const { id } = Route.useParams();
  return <FeaturePage routeId="O03" title="Case Overview" role="officer" id={id} />;
}
