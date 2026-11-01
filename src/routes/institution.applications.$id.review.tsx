import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/institution/applications/$id/review")({ component: Page });
function Page() {
  const { id } = Route.useParams();
  return <FeaturePage routeId="I08" title="Review & Submit" role="institution" id={id} />;
}
