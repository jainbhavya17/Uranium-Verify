import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/officer/cases/$id/inspection")({ component: Page });
function Page() {
  const { id } = Route.useParams();
  return <FeaturePage routeId="O07" title="Infrastructure & Inspection" role="officer" id={id} />;
}
