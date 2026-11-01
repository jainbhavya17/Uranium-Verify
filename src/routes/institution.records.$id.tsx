import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/institution/records/$id")({ component: Page });
function Page() {
  const { id } = Route.useParams();
  return <FeaturePage routeId="I11" title="Approved Record" role="institution" id={id} />;
}
