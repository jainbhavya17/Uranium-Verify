import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/institution/applications/$id/details")({ component: Page });
function Page() {
  const { id } = Route.useParams();
  return <FeaturePage routeId="I04" title="Request Details" role="institution" id={id} />;
}
