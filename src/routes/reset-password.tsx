import { createFileRoute } from "@tanstack/react-router";
import { PublicShell } from "@/components/portal";
import { RecoveryPage } from "@/features/release/ReleasePages";
export const Route = createFileRoute("/reset-password")({
  component: () => (
    <PublicShell>
      <div className="workflow-content">
        <RecoveryPage />
      </div>
    </PublicShell>
  ),
});
