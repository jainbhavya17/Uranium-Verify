import { createFileRoute } from "@tanstack/react-router";
import { FeaturePage } from "@/components/feature-page";
export const Route = createFileRoute("/admin/users")({ component: Page });
function Page() {
  return <FeaturePage routeId="A01" title="Users & Roles" role="admin" />;
}
