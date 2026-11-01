import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/institution/applications/$id/checklist")({
  component: Page,
});
function Page() {
  const { id } = Route.useParams();
  return <FeaturePage routeId="I05" title="Document Checklist" role="institution" id={id} />;
}
