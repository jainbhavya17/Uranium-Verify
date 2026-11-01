import { useState } from "react";
import { ArrowRight, Menu, X, LogOut } from "lucide-react";
import { Link } from "./link";
import { roleHome, userHome, useCurrentUser, useBackendSession } from "@/lib/backend-session";

export function PublicBrand() {
  return (
    <Link to="/" className="uv-brand" aria-label="Uranium Verify home">
      <span className="uv-mark" aria-hidden="true">
        <i />
        <i />
      </span>
      Uranium Verify<span className="uv-prototype">PROTOTYPE</span>
    </Link>
  );
}
export function PublicHeader() {
  const [open, setOpen] = useState(false);
  const [logoutError, setLogoutError] = useState("");
  const user = useCurrentUser();
  const { logout } = useBackendSession();
  return (
    <>
      <a href="#main" className="skip-link">
        Skip to main content
      </a>
      <header className="uv-header">
        <PublicBrand />
        <button
          className="uv-menu"
          aria-label={open ? "Close navigation" : "Open navigation"}
          aria-expanded={open}
          aria-controls="public-nav"
          onClick={() => setOpen(!open)}
        >
          {open ? <X /> : <Menu />}
        </button>
        <nav
          id="public-nav"
          aria-label="Primary"
          className={open ? "uv-nav is-open" : "uv-nav"}
          onClick={() => setOpen(false)}
        >
          <a href="/#platform">Platform</a>
          <a href="/#process">Approval process</a>
          <Link to="/resources">Resources</Link>
          <Link to="/help">Help</Link>
          {user ? (
            <>
              <Link className="uv-button uv-button-small" to={userHome(user)}>
                My workspace <ArrowRight size={14} />
              </Link>
              <button
                className="uv-signout"
                aria-label="Sign out"
                onClick={() => {
                  setLogoutError("");
                  void logout().catch(() =>
                    setLogoutError(
                      "Sign out could not be completed. Check the connection and try again.",
                    ),
                  );
                }}
              >
                <LogOut size={17} />
              </button>
            </>
          ) : (
            <Link className="uv-button uv-button-small" to="/login">
              Sign in <ArrowRight size={14} />
            </Link>
          )}
        </nav>
      </header>
      {logoutError && (
        <p className="workspace-environment" role="alert">
          {logoutError}
        </p>
      )}
    </>
  );
}
const footerGroups = [
  {
    title: "Platform",
    links: [
      ["Applications", "/institution/applications"],
      ["Document guidance", "/resources"],
      ["Approval process", "/#process"],
    ],
  },
  {
    title: "Resources",
    links: [
      ["Help centre", "/help"],
      ["Portal notices", "/notices"],
      ["Knowledge base", "/resources"],
    ],
  },
  {
    title: "Portal access",
    links: [
      ["Institution workspace", "/institution/dashboard"],
      ["Officer workspace", "/officer/dashboard"],
      ["Administrator", "/admin/notices"],
    ],
  },
];
export function PublicFooter() {
  return (
    <footer className="uv-footer">
      <div className="uv-footer-top">
        <div>
          <PublicBrand />
          <p>
            A connected application scrutiny
            <br />
            workspace for institutions and reviewers.
          </p>
        </div>
        {footerGroups.map((g) => (
          <div key={g.title}>
            <h2>{g.title}</h2>
            {g.links.map(([label, to]) =>
              to.includes("#") ? (
                <a key={label} href={to}>
                  {label}
                </a>
              ) : (
                <Link key={label} to={to}>
                  {label}
                </Link>
              ),
            )}
          </div>
        ))}
      </div>
      <div className="uv-footer-bottom">
        <span>Uranium Verify · Prototype</span>
        <span>Local demonstration. Not an official AICTE service.</span>
        <a href="#main">Back to top ↑</a>
      </div>
    </footer>
  );
}
