import { DataTable } from "@/components/portal";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { InnerPage, Panel, Status, EmptyRow, Filters, instName } from "@/components/portal";
import { actions, useStore } from "@/lib/store";
import { institutions, type Role } from "@/lib/data";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/admin/users")({
  head: seo("Users & Roles", "Manage user accounts and role assignments."),
  component: Page,
});

function Page() {
  const users = useStore((s) => s.users);
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [n, setN] = useState({
    id: "",
    name: "",
    email: "",
    role: "officer" as Role,
    designation: "",
    institutionId: "",
  });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const list = users.filter(
    (u) =>
      (!role || u.role === role) &&
      `${u.id} ${u.name} ${u.email}`.toLowerCase().includes(q.toLowerCase()),
  );
  return (
    <InnerPage
      role="admin"
      crumbs={[{ label: "Administration" }, { label: "Users & Roles" }]}
      title="Users & Roles"
    >
      <Filters>
        <div className="flex-1 min-w-[12rem]">
          <label className="label" htmlFor="q">
            Search
          </label>
          <input id="q" className="field" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="r">
            Role
          </label>
          <select id="r" className="field" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="">All</option>
            <option value="institution">Institution</option>
            <option value="officer">Officer</option>
            <option value="admin">Administrator</option>
          </select>
        </div>
      </Filters>
      <DataTable className="gov-table mb-6">
        <thead>
          <tr>
            <th>User ID</th>
            <th>Name</th>
            <th>Designation</th>
            <th>Role</th>
            <th>Institution</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {list.length === 0 ? (
            <EmptyRow cols={7} />
          ) : (
            list.map((u) => (
              <tr key={u.id}>
                <td>{u.id}</td>
                <td>
                  {u.name}
                  <div className="text-xs text-muted-foreground">{u.email}</div>
                </td>
                <td>{u.designation}</td>
                <td className="capitalize">{u.role}</td>
                <td>{u.institutionId ? instName(u.institutionId) : "—"}</td>
                <td>
                  <Status s={u.active ? "Active" : "Disabled"} />
                </td>
                <td>
                  {u.role !== "admin" && (
                    <button className="link" onClick={() => actions.toggleUser(u.id)}>
                      {u.active ? "Disable" : "Enable"}
                    </button>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </DataTable>
      <Panel title="Create User Account">
        <form
          className="grid gap-3 sm:grid-cols-3"
          onSubmit={(e) => {
            e.preventDefault();
            try {
              actions.addUser({
                ...n,
                institutionId: n.role === "institution" ? n.institutionId : undefined,
              });
              setN({ ...n, id: "", name: "", email: "", designation: "" });
              setError("");
              setMessage("Sample account created. Initial password: Aicte@2026.");
            } catch (err) {
              setError((err as Error).message);
            }
          }}
        >
          {(["id", "name", "email", "designation"] as const).map((k) => (
            <div key={k}>
              <label className="label capitalize" htmlFor={`n-${k}`}>
                {k === "id" ? "User ID" : k}
              </label>
              <input
                id={`n-${k}`}
                className="field"
                type={k === "email" ? "email" : "text"}
                required
                value={n[k]}
                onChange={(e) => setN({ ...n, [k]: e.target.value })}
              />
            </div>
          ))}
          <div>
            <label className="label" htmlFor="n-role">
              Role
            </label>
            <select
              id="n-role"
              className="field"
              value={n.role}
              onChange={(e) => setN({ ...n, role: e.target.value as Role })}
            >
              <option value="institution">Institution</option>
              <option value="officer">Officer</option>
              <option value="admin">Administrator</option>
            </select>
          </div>
          {n.role === "institution" && (
            <div>
              <label className="label" htmlFor="n-inst">
                Institution
              </label>
              <select
                id="n-inst"
                className="field"
                required
                value={n.institutionId}
                onChange={(e) => setN({ ...n, institutionId: e.target.value })}
              >
                <option value="">Select</option>
                {institutions.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="sm:col-span-3">
            <button className="btn btn-primary">Create Account</button>
            <span className="text-xs text-muted-foreground ml-3">
              Local demo initial password: Aicte@2026.
            </span>
          </div>
        </form>
        {message && (
          <p role="status" className="workflow-feedback">
            {message}
          </p>
        )}
        {error && (
          <p role="alert" className="text-destructive mt-3">
            {error}
          </p>
        )}
      </Panel>
    </InnerPage>
  );
}
