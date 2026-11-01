import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/admin/knowledge")({
  component: () => <FeaturePage routeId="A05" title="Knowledge Sources" role="admin" />,
});
