import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowRight, Check, Eye, EyeOff, LoaderCircle, ShieldCheck } from "lucide-react";
import { PublicShell } from "@/components/portal";
import { Link, useGo } from "@/components/link";
import { useBackendSession, userHome } from "@/lib/backend-session";
import { seo } from "@/lib/seo";
import demoAccounts from "../../config/demo-accounts.json";

export const Route = createFileRoute("/login")({
  head: seo(
    "Login",
    "Sign in to URANIUM VERIFY as an institution, AICTE officer or administrator.",
  ),
  component: Login,
});
function Login() {
  const go = useGo();
  const { login, pending, waking, error: sessionError, retry } = useBackendSession();
  const [busy, setBusy] = useState(false);
  const [id, setId] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [show, setShow] = useState(false);
  const waiting = busy || pending || waking;
  const displayError = waiting ? "" : err || sessionError?.message || "";
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (waiting) return;
    setBusy(true);
    setErr("");
    try {
      const user = await login(id.trim(), pw);
      await go(userHome(user));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
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
            {demoAccounts.accounts.map((a) => (
              <button
                type="button"
                key={a.email}
                disabled={waiting}
                onClick={() => {
                  setId(a.email);
                  setPw(demoAccounts.password);
                  setShow(false);
                  setErr("");
                }}
              >
                {a.label}
              </button>
            ))}
            <small>Fills both email and password. Select Sign in to continue.</small>
            <small>
              Sample password: <code>{demoAccounts.password}</code>
            </small>
          </div>
          <p>Sign in with the credentials issued to you.</p>
          <form onSubmit={submit} className="space-y-5" aria-busy={waiting}>
            <div>
              <label className="label" htmlFor="uid">
                User ID or registered email
              </label>
              <input
                id="uid"
                type="email"
                className="field"
                placeholder="Enter your user ID or email"
                value={id}
                onChange={(e) => {
                  setId(e.target.value);
                  setErr("");
                }}
                autoComplete="username"
                required
                aria-describedby={displayError ? "login-error" : undefined}
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
                  aria-describedby={displayError ? "login-error" : undefined}
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
            {waiting && (
              <p
                role="status"
                aria-live="polite"
                className="flex items-center gap-2 text-sm text-muted-foreground"
              >
                <LoaderCircle
                  size={16}
                  aria-hidden="true"
                  className="animate-spin motion-reduce:animate-none shrink-0"
                />
                {waking
                  ? "Server is waking up, please wait. This can take a minute or longer…"
                  : busy
                    ? "Signing in…"
                    : "Connecting to the server…"}
              </p>
            )}
            {displayError && (
              <p
                id="login-error"
                className="text-[11px] text-destructive leading-relaxed"
                role="alert"
              >
                {displayError}
              </p>
            )}
            {displayError && (
              <button
                type="button"
                className="btn btn-outline w-full"
                onClick={() => {
                  setErr("");
                  retry();
                }}
              >
                Try again
              </button>
            )}
            <button disabled={waiting} className="btn btn-primary w-full">
              Sign in to workspace <ArrowRight size={15} />
            </button>
          </form>
          <div className="text-[10px] text-muted-foreground text-center mt-7 pt-6 border-t border-border leading-relaxed">
            Need help accessing your account?
            <br />
            <Link to="/help" className="link">
              Contact your portal administrator
            </Link>
          </div>
          <Link to="/" className="text-[10px] text-muted-foreground mt-6 text-center">
            ← Back to portal overview
          </Link>
        </section>
      </div>
    </PublicShell>
  );
}
