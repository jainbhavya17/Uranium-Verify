import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/officer/cases/$id/review")({ component: Page });
function Page() {
  const { id } = Route.useParams();
  return <FeaturePage routeId="O08" title="Review & Decision" role="officer" id={id} />;
}
