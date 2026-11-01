import { describe, expect, it } from "vitest";
import { evaluateRules } from "@/lib/store";
import { applications, rules } from "@/lib/data";

const base = applications.find((a) => a.id === "APP-01588")!;
const withDetails = (p: Partial<typeof base.details>) => ({
  ...base,
  details: { ...base.details, ...p },
});
const result = (a: typeof base, id: string) =>
  evaluateRules(a, rules).find((r) => r.rule.id === id)!.pass;

describe("compliance rules", () => {
  it("requires faculty of at least intake / 20", () => {
    expect(result(withDetails({ intake: 120, facultyCount: 6 }), "R-01")).toBe(true);
    expect(result(withDetails({ intake: 120, facultyCount: 5 }), "R-01")).toBe(false);
  });
  it("requires land area of at least 2.5 acres", () => {
    expect(result(withDetails({ landArea: 2.4 }), "R-02")).toBe(false);
  });
  it("requires built-up area of 1000 sq.m plus 5 per seat", () => {
    expect(result(withDetails({ intake: 100, builtUpArea: 1499 }), "R-03")).toBe(false);
    expect(result(withDetails({ intake: 100, builtUpArea: 1500 }), "R-03")).toBe(true);
  });
});
