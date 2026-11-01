import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/officer/cases/$id/compliance")({ component: Page });
function Page() {
  const { id } = Route.useParams();
  return <FeaturePage routeId="O06" title="Compliance Review" role="officer" id={id} />;
}
