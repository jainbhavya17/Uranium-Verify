import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { InstitutionAppPage, WizardNav, DetailsDL } from "@/components/app-flow";
import { Panel } from "@/components/portal";
import { actions } from "@/lib/store";
import type { Application, Details } from "@/lib/data";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/institution/applications/$id/details")({
  head: seo(
    "Application Details",
    "Enter programme, intake and infrastructure details for the application.",
  ),
  component: Page,
});

function Page() {
  const { id } = Route.useParams();
  return (
    <InstitutionAppPage id={id} step="details" title="Application Details">
      {(a) =>
        a.status === "Draft" ? (
          <Form a={a} />
        ) : (
          <Panel title="Submitted Details">
            <DetailsDL a={a} d={a.frozen?.details} />
          </Panel>
        )
      }
    </InstitutionAppPage>
  );
}

function Form({ a }: { a: Application }) {
  const [d, setD] = useState<Details>(a.details);
  const [msg, setMsg] = useState("");
  const f = (k: keyof Details, label: string, type = "text") => (
    <div>
      <label className="label" htmlFor={k}>
        {label}
      </label>
      <input
        id={k}
        type={type}
        className="field"
        value={d[k]}
        onChange={(e) =>
          setD({ ...d, [k]: type === "number" ? Number(e.target.value) : e.target.value })
        }
      />
    </div>
  );
  return (
    <Panel title="Programme & Infrastructure Particulars">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="label" htmlFor="programme">
            Programme
          </label>
          <select
            id="programme"
            className="field"
            value={d.programme}
            onChange={(e) => setD({ ...d, programme: e.target.value })}
          >
            {[
              "Engineering & Technology",
              "Management",
              "Pharmacy",
              "Architecture",
              "Computer Applications",
            ].map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </div>
        {f("course", "Course Name")}
        {f("intake", "Proposed Intake", "number")}
        <div>
          <label className="label" htmlFor="ay">
            Academic Year
          </label>
          <select
            id="ay"
            className="field"
            value={d.academicYear}
            onChange={(e) => setD({ ...d, academicYear: e.target.value })}
          >
            <option>2026-27</option>
            <option>2025-26</option>
          </select>
        </div>
        {f("landArea", "Land Area (acres)", "number")}
        {f("builtUpArea", "Built-up Area (sq.m)", "number")}
        {f("facultyCount", "Full-time Faculty (numbers)", "number")}
        {f("principal", "Head of Institution")}
        <div className="sm:col-span-2">{f("address", "Address of Institution")}</div>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <button
          className="btn btn-outline"
          onClick={() => {
            actions.saveDetails(a.id, d);
            setMsg("Draft saved.");
          }}
        >
          Save Draft
        </button>
        {msg && (
          <span className="text-sm text-success" role="status">
            {msg}
          </span>
        )}
      </div>
      <WizardNav
        id={a.id}
        step="details"
        nextDisabled={!d.course}
        onNext={() => actions.saveDetails(a.id, d)}
      />
    </Panel>
  );
}
