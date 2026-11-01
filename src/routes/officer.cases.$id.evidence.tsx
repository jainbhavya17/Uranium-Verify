import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/officer/cases/$id/evidence")({ component: Page });
function Page() {
  const { id } = Route.useParams();
  return <FeaturePage routeId="O04" title="Evidence Viewer" role="officer" id={id} />;
}
