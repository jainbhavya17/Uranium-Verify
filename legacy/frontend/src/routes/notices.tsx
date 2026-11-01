import { createFileRoute } from "@tanstack/react-router";
import { PublicShell } from "@/components/portal";
import { NoticesSection } from "@/components/notices";
import { seo } from "@/lib/seo";
export const Route = createFileRoute("/notices")({
  head: seo("Portal notices", "Published guidance and updates from the Uranium Verify prototype."),
  component: () => (
    <PublicShell landing>
      <NoticesSection full />
    </PublicShell>
  ),
});
