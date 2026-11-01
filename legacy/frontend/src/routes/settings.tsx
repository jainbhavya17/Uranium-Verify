import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { InnerPage, Panel, instName } from "@/components/portal";
import { actions, useCurrentUser, useStore } from "@/lib/store";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/settings")({
  head: seo("Settings", "Profile, password and notification preferences."),
  component: Settings,
});

function Settings() {
  const user = useCurrentUser();
  const prefs = useStore((s) => s.prefs);
  const [p, setP] = useState(prefs);
  const [saved, setSaved] = useState("");
  useEffect(() => {
    setP(prefs);
  }, [prefs]);
  const [oldPw, setOld] = useState("");
  const [pw, setPw] = useState("");
  const [pwMsg, setPwMsg] = useState("");
  return (
    <InnerPage
      role={["institution", "officer", "admin"]}
      crumbs={[{ label: "Settings" }]}
      title="Settings"
    >
      {user && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Panel title="Profile">
            <dl className="dl">
              <dt>Name</dt>
              <dd>{user.name}</dd>
              <dt>User ID</dt>
              <dd>{user.id}</dd>
              <dt>Designation</dt>
              <dd>{user.designation}</dd>
              <dt>Email</dt>
              <dd>{user.email}</dd>
              {user.institutionId && (
                <>
                  <dt>Institution</dt>
                  <dd>{instName(user.institutionId)}</dd>
                </>
              )}
            </dl>
          </Panel>
          <Panel title="Preferences & Accessibility">
            <p className="workspace-note mb-4">
              Email and SMS options are saved preferences only; no messages are sent. Interface
              translation is not connected.
            </p>
            <form
              className="space-y-3 text-sm"
              onSubmit={(e) => {
                e.preventDefault();
                actions.setPrefs(p);
                setSaved("Preferences saved.");
              }}
            >
              <label className="flex gap-2">
                <input
                  type="checkbox"
                  checked={p.email}
                  onChange={(e) => setP({ ...p, email: e.target.checked })}
                />{" "}
                Email alerts for status changes
              </label>
              <label className="flex gap-2">
                <input
                  type="checkbox"
                  checked={p.sms}
                  onChange={(e) => setP({ ...p, sms: e.target.checked })}
                />{" "}
                SMS alerts to registered mobile
              </label>
              <div>
                <label className="label" htmlFor="lang">
                  Display language (prototype)
                </label>
                <select
                  id="lang"
                  className="field"
                  value={p.language}
                  onChange={(e) => setP({ ...p, language: e.target.value })}
                >
                  <option>English</option>
                  <option disabled>Hindi — unavailable in prototype</option>
                </select>
              </div>
              <p className="text-xs text-muted-foreground">
                Screen reader users may use the "Skip to Main Content" link. Text size can be
                adjusted using A- / A / A+ in the top strip.
              </p>
              <button className="btn btn-primary">Save Preferences</button>
              {saved && <span className="ml-3 text-success">{saved}</span>}
            </form>
          </Panel>
          <Panel title="Change Password">
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                if (pw.length < 8) {
                  setPwMsg("New password must be at least 8 characters.");
                  return;
                }
                setPwMsg(
                  actions.changePassword(oldPw, pw)
                    ? "Password changed successfully."
                    : "Current password is incorrect.",
                );
                setOld("");
                setPw("");
              }}
            >
              <div>
                <label className="label" htmlFor="op">
                  Current Password
                </label>
                <input
                  id="op"
                  type="password"
                  className="field"
                  value={oldPw}
                  onChange={(e) => setOld(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="label" htmlFor="np">
                  New Password
                </label>
                <input
                  id="np"
                  type="password"
                  className="field"
                  value={pw}
                  onChange={(e) => setPw(e.target.value)}
                  required
                />
              </div>
              <button className="btn btn-primary">Update Password</button>
              {pwMsg && (
                <p className="text-sm mt-2" role="status">
                  {pwMsg}
                </p>
              )}
            </form>
          </Panel>
        </div>
      )}
    </InnerPage>
  );
}
