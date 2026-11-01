import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/institution/applications/$id/status")({ component: Page });
function Page() {
  const { id } = Route.useParams();
  return <FeaturePage routeId="I09" title="Application Status" role="institution" id={id} />;
}
