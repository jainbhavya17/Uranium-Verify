import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/officer/cases/$id/authenticity")({ component: Page });
function Page() {
  const { id } = Route.useParams();
  return <FeaturePage routeId="O05" title="Document Authenticity" role="officer" id={id} />;
}
