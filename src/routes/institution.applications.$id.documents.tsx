import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/institution/applications/$id/documents")({
  component: Page,
});
function Page() {
  const { id } = Route.useParams();
  return <FeaturePage routeId="I06" title="Documents" role="institution" id={id} />;
}
