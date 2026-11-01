import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { PublicShell, Panel } from "@/components/portal";
import { Link } from "@/components/link";
import { getState } from "@/lib/store";
import { seo } from "@/lib/seo";

export const Route = createFileRoute("/reset-password")({
  head: seo(
    "Password Recovery",
    "Recover access to your URANIUM VERIFY account through your registered email.",
  ),
  component: Reset,
});

function Reset() {
  const [id, setId] = useState("");
  const [email, setEmail] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const u = getState().users.find(
      (x) => x.id === id.trim() && x.email.toLowerCase() === email.trim().toLowerCase(),
    );
    if (!u) {
      setErr("The User ID and registered email do not match our records.");
      return;
    }
    setDone(u.email.replace(/^(.{2}).*(@.*)$/, "$1****$2"));
  };
  return (
    <PublicShell>
      <div className="max-w-md mx-auto">
        <Panel title="Password Recovery">
          {done ? (
            <div className="space-y-3 text-sm">
              <div className="notice">
                A matching sample account was found for {done}. This local prototype does not send
                email or password reset links. Return to Sign in and choose a sample account to
                continue.
              </div>
              <Link to="/login" className="btn btn-primary">
                Return to Login
              </Link>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <div>
                <label className="label" htmlFor="rid">
                  User ID
                </label>
                <input
                  id="rid"
                  className="field"
                  value={id}
                  onChange={(e) => {
                    setId(e.target.value);
                    setErr("");
                  }}
                  required
                />
              </div>
              <div>
                <label className="label" htmlFor="rem">
                  Registered Email
                </label>
                <input
                  id="rem"
                  type="email"
                  className="field"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setErr("");
                  }}
                  required
                />
              </div>
              {err && (
                <p className="text-sm text-destructive" role="alert">
                  {err}
                </p>
              )}
              <button className="btn btn-primary w-full justify-center">
                Check Sample Account
              </button>
              <Link to="/login" className="link text-sm">
                Back to Login
              </Link>
            </form>
          )}
        </Panel>
      </div>
    </PublicShell>
  );
}
