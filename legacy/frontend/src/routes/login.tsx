import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowRight, Check, Eye, EyeOff, ShieldCheck } from "lucide-react";
import { PublicShell } from "@/components/portal";
import { Link, useGo } from "@/components/link";
import { actions, roleHome } from "@/lib/store";
import { seo } from "@/lib/seo";
import { PASSWORD } from "@/lib/data";
export const Route = createFileRoute("/login")({
  head: seo(
    "Login",
    "Sign in to URANIUM VERIFY as an institution, AICTE officer or administrator.",
  ),
  component: Login,
});
function Login() {
  const go = useGo();
  const [id, setId] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [show, setShow] = useState(false);
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const u = actions.login(id, pw);
    if (!u) {
      setErr(
        "We couldn’t sign you in. Check your credentials or contact your administrator if your account is disabled.",
      );
      return;
    }
    go(roleHome[u.role]);
  };
  return (
    <PublicShell>
      <div className="login-layout">
        <section className="login-intro">
          <ShieldCheck size={34} strokeWidth={1.4} className="text-teal" />
          <span className="eyebrow mt-7">Your approval workspace</span>
          <h1>
            Progress starts
            <br />
            with a clear view.
          </h1>
          <p>
            Manage your AICTE approval journey with the information, guidance, and next steps you
            need in one place.
          </p>
          {[
            "Every application, organised",
            "Clear feedback at every stage",
            "A complete history of your progress",
          ].map((text) => (
            <div className="login-feature" key={text}>
              <Check size={16} />
              {text}
            </div>
          ))}
        </section>
        <section className="login-form">
          <h2>Welcome back</h2>
          <div className="uv-demo-accounts">
            <span>Explore a sample account</span>
            {[
              { label: "Institution", id: "inst.svit" },
              { label: "Officer", id: "off.sharma" },
              { label: "Administrator", id: "admin" },
            ].map((a) => (
              <button
                type="button"
                key={a.id}
                onClick={() => {
                  setId(a.id);
                  setPw(PASSWORD);
                  setErr("");
                }}
              >
                {a.label}
              </button>
            ))}
            <small>Fills sample credentials. Choose Sign in to continue.</small>
          </div>
          <p>Sign in with the credentials issued to you.</p>
          <form onSubmit={submit} className="space-y-5">
            <div>
              <label className="label" htmlFor="uid">
                User ID or registered email
              </label>
              <input
                id="uid"
                className="field"
                placeholder="Enter your user ID or email"
                value={id}
                onChange={(e) => {
                  setId(e.target.value);
                  setErr("");
                }}
                autoComplete="username"
                required
                aria-describedby={err ? "login-error" : undefined}
              />
            </div>
            <div>
              <div className="flex justify-between items-start">
                <label className="label" htmlFor="pw">
                  Password
                </label>
                <Link to="/reset-password" className="link text-[10px]">
                  Forgot password?
                </Link>
              </div>
              <div className="password-wrap">
                <input
                  id="pw"
                  type={show ? "text" : "password"}
                  className="field"
                  placeholder="Enter your password"
                  value={pw}
                  onChange={(e) => {
                    setPw(e.target.value);
                    setErr("");
                  }}
                  autoComplete="current-password"
                  required
                  aria-describedby={err ? "login-error" : undefined}
                />
                <button
                  type="button"
                  className="icon-button"
                  aria-label={show ? "Hide password" : "Show password"}
                  aria-pressed={show}
                  onClick={() => setShow(!show)}
                >
                  {show ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
            {err && (
              <p
                id="login-error"
                className="text-[11px] text-destructive leading-relaxed"
                role="alert"
              >
                {err}
              </p>
            )}
            <button className="btn btn-primary w-full">
              Sign in to workspace <ArrowRight size={15} />
            </button>
          </form>
          <div className="text-[10px] text-muted-foreground text-center mt-7 pt-6 border-t border-border leading-relaxed">
            Need help accessing your account?
            <br />
            <a href="tel:01129581000" className="link">
              Contact helpdesk · 011-29581000
            </a>
          </div>
          <Link to="/" className="text-[10px] text-muted-foreground mt-6 text-center">
            ← Back to portal overview
          </Link>
        </section>
      </div>
    </PublicShell>
  );
}
