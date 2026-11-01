import { QueryClient } from "@tanstack/react-query";
import { createRouter, rootRouteId } from "@tanstack/react-router";
import { describe, expect, it } from "vitest";
import { routeTree } from "@/routeTree.gen";
import contracts from "../../packages/contracts/routes.json";
import { portalPath } from "@/features/navigation";

describe("SRS route navigation", () => {
  const router = createRouter({ routeTree, context: { queryClient: new QueryClient() } });
  for (const route of contracts)
    it(`resolves ${route.id}: ${route.title}`, () => {
      const path = portalPath(route.path.replace(/:(id|recordId|requestId)/g, "test-record"));
      const matches = router.matchRoutes(path);
      expect(matches.at(-1)?.routeId).not.toBe(rootRouteId);
      expect(matches.at(-1)?.pathname.replace(/\/$/, "")).toBe(path.replace(/\/$/, ""));
    });
  it("preserves evidence deep links while translating routes", () => {
    expect(portalPath("/officer/applications/case-1/evidence?version=v2&page=3&field=name")).toBe(
      "/officer/cases/case-1/evidence?version=v2&page=3&field=name",
    );
  });
});
