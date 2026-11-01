import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/notifications")({ component: Page });
function Page() {
  return <FeaturePage routeId="notifications" title="Notifications" />;
}
