import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/institution/applications/$id/validation")({
  component: Page,
});
function Page() {
  const { id } = Route.useParams();
  return <FeaturePage routeId="I07" title="Pre-Validation" role="institution" id={id} />;
}
