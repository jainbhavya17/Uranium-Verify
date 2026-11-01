import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/settings")({ component: Page });
function Page() {
  return <FeaturePage routeId="settings" title="Settings" />;
}
