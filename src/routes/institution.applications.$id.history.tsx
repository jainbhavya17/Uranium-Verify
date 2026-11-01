import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/institution/applications/$id/history")({ component: Page });
function Page() {
  const { id } = Route.useParams();
  return <FeaturePage routeId="I09" title="Application History" role="institution" id={id} />;
}
