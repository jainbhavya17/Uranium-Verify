import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/institution/deficiencies/$id/respond")({ component: Page });
function Page() {
  const { id } = Route.useParams();
  return (
    <FeaturePage routeId="response" title="Respond to Deficiency" role="institution" id={id} />
  );
}
