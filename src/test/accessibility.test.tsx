import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/react";
import axe from "axe-core";
import { Fields } from "@/features/officer/common";
import { EvidenceTrail } from "@/features/officer/EvidenceTrail";
afterEach(cleanup);
describe("Accessible evidence components", () => {
  it("exposes structured findings and source navigation without axe violations", async () => {
    const { container } = render(
      <main>
        <h1>Evidence review</h1>
        <Fields
          data={{
            status: "MANUAL_REVIEW",
            reason: "Certificate expiry date is unclear",
            source: { page: 2 },
          }}
        />
        <section>
          <h2>Evidence links</h2>
          <EvidenceTrail
            nodes={[
              { id: "n", kind: "EXTRACTED_FIELD", reference: { version_id: "v", field_id: "f" } },
            ]}
            edges={[]}
            versions={[{ id: "v", name: "Certificate.pdf", number: 1 }]}
            fields={[{ id: "f", key: "expiry_date", page: 2 }]}
            openSource={() => {}}
          />
        </section>
      </main>,
    );
    const result = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(result.violations).toEqual([]);
  });
});
