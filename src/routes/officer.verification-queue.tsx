import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/officer/verification-queue")({ component: Page });
function Page() {
  return <FeaturePage routeId="O09" title="Document Verification" role="officer" />;
}
