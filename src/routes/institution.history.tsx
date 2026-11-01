import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/institution/history")({ component: Page });
function Page() {
  return <FeaturePage routeId="I10" title="Approved Records" role="institution" />;
}
