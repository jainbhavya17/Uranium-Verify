import { useQuery } from "@tanstack/react-query";
import { api } from "@/features/api";
import { label } from "@/features/presentation";
import { useRouterState } from "@tanstack/react-router";
import { Link, useGo } from "./link";
import { useState, type ReactNode, type TableHTMLAttributes } from "react";
import {
  Accessibility,
  ArrowRight,
  Bell,
  BookOpen,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  FileCheck2,
  FilePlus2,
  Files,
  LayoutDashboard,
  LogOut,
  Menu,
  Network,
  Search,
  Settings,
  ShieldCheck,
  Users,
  X,
  ChartNoAxesCombined,
  ScrollText,
  AlertCircle,
  type LucideIcon,
} from "lucide-react";
import { roleHome, userHome, useCurrentUser, useBackendSession } from "@/lib/backend-session";
import type { Role } from "@/lib/data";
import { institutions } from "@/lib/data";
import { PublicHeader, PublicFooter, PublicBrand } from "./public-chrome";

export function Brand() {
  return <PublicBrand />;
}
function setFont(delta: number) {
  const el = document.documentElement;
  const size = parseFloat(getComputedStyle(el).fontSize);
  el.style.fontSize = delta === 0 ? "16px" : `${Math.min(20, Math.max(13, size + delta))}px`;
}
export function Header() {
  const user = useCurrentUser();
  const [logoutError, setLogoutError] = useState("");
  const go = useGo();
  const { logout } = useBackendSession();
  const notifications = useQuery({
    queryKey: ["notification-count", user?.id],
    queryFn: () => api<unknown[]>("/notifications?state=unread&page_size=1"),
    enabled: !!user,
    refetchInterval: 10000,
  });
  const unread = notifications.data?.meta.total;
  return (
    <>
      <a href="#main" className="skip-link">
        Skip to main content
      </a>
      <header className="site-header">
        <Brand />
        <nav aria-label="Primary" className="header-links">
          <Link to="/" activeOptions={{ exact: true }} activeProps={{ className: "is-current" }}>
            Overview
          </Link>
          <Link to="/notices">Portal notices</Link>
          <Link to="/resources">Resources</Link>
        </nav>
        <div className="flex items-center gap-3">
          <span className="year-chip">AY 2026–27</span>
          <details className="accessibility-menu">
            <summary className="icon-button" aria-label="Text size and accessibility">
              <Accessibility size={18} />
            </summary>
            <div>
              <span>Text size</span>
              <button type="button" onClick={() => setFont(-1)} aria-label="Decrease font size">
                A−
              </button>
              <button type="button" onClick={() => setFont(0)} aria-label="Reset font size">
                A
              </button>
              <button type="button" onClick={() => setFont(1)} aria-label="Increase font size">
                A+
              </button>
            </div>
          </details>
          {user ? (
            <>
              <Link
                to="/notifications"
                className="icon-button relative"
                aria-label={
                  unread === undefined ? "Notifications" : `Notifications, ${unread} unread`
                }
              >
                <Bell size={19} />
                {unread !== undefined && unread > 0 && <span className="notification-dot" />}
              </Link>
              <div className="header-profile">
                <span className="avatar">
                  {user.name
                    .split(" ")
                    .slice(-2)
                    .map((n) => n[0])
                    .join("")}
                </span>
                <span className="hidden lg:block">
                  <b>{user.name}</b>
                  <small>{user.roles.map((r) => label(r)).join(", ")}</small>
                </span>
              </div>
              <button
                className="icon-button"
                aria-label="Sign out"
                onClick={() => {
                  setLogoutError("");
                  void logout()
                    .then(() => go("/login"))
                    .catch(() =>
                      setLogoutError(
                        "Sign out could not be completed. Check the connection and try again.",
                      ),
                    );
                }}
              >
                <LogOut size={18} />
              </button>
            </>
          ) : (
            <Link to="/login" className="btn btn-navy">
              Sign in <ArrowRight size={15} />
            </Link>
          )}
        </div>
      </header>
      {logoutError && (
        <p className="workspace-environment" role="alert">
          {logoutError}
        </p>
      )}
      <div className="workspace-environment" role="note">
        Prototype workspace · Sample institutional records{" "}
        <Link to="/help">About verification limits</Link>
      </div>
    </>
  );
}
export function Footer() {
  return (
    <footer className="site-footer">
      <span>Uranium Verify · Development prototype</span>
      <div className="flex flex-wrap gap-5">
        <Link to="/help">Help centre</Link>
        <Link to="/resources">Application guidance</Link>
        <span>No live AICTE connection</span>
      </div>
    </footer>
  );
}
export function PublicShell({
  children,
  landing = false,
}: {
  children: ReactNode;
  landing?: boolean;
}) {
  return (
    <div className="uv-public min-h-screen flex flex-col">
      <PublicHeader />
      <main id="main" className={landing ? "uv-landing" : "public-main uv-content"}>
        {children}
      </main>
      <PublicFooter />
    </div>
  );
}
const NAV: Record<Role, { to: string; label: string; icon: LucideIcon }[]> = {
  institution: [
    { to: "/institution/dashboard", label: "Overview", icon: LayoutDashboard },
    { to: "/institution/applications", label: "My applications", icon: Files },
    { to: "/institution/applications/new", label: "New application", icon: FilePlus2 },
    { to: "/institution/history", label: "Approved records", icon: BookOpen },
    { to: "/institution/deficiencies", label: "Deficiencies", icon: AlertCircle },
    { to: "/notifications", label: "Notifications", icon: Bell },
    { to: "/settings", label: "Settings", icon: Settings },
  ],
  officer: [
    { to: "/officer/dashboard", label: "Overview", icon: LayoutDashboard },
    { to: "/officer/queue", label: "Case queue", icon: Files },
    { to: "/officer/verification-queue", label: "Document verification", icon: FileCheck2 },
    { to: "/officer/reports", label: "Reports & insights", icon: ChartNoAxesCombined },
    { to: "/resources", label: "Knowledge base", icon: BookOpen },
    { to: "/notifications", label: "Notifications", icon: Bell },
    { to: "/settings", label: "Settings", icon: Settings },
  ],
  admin: [
    { to: "/admin/notices", label: "Portal notices", icon: Bell },
    { to: "/admin/users", label: "Users & roles", icon: Users },
    { to: "/admin/rules", label: "Rule library", icon: ClipboardCheck },
    { to: "/admin/connectors", label: "Connectors", icon: Network },
    { to: "/admin/audit", label: "Audit trail", icon: ScrollText },
    { to: "/admin/knowledge-sources", label: "Knowledge sources", icon: BookOpen },
    { to: "/notifications", label: "Notifications", icon: Bell },
    { to: "/settings", label: "Settings", icon: Settings },
  ],
};
export type Crumb = { label: string; to?: string };
export function InnerPage({
  role,
  crumbs,
  title,
  children,
  allowPublic,
  actions: act,
}: {
  role?: Role | Role[];
  crumbs: Crumb[];
  title: string;
  children: ReactNode;
  allowPublic?: boolean;
  actions?: ReactNode;
}) {
  const user = useCurrentUser();
  const session = useBackendSession();
  const hydrated = !session.pending;
  const [open, setOpen] = useState(false);
  const path = useRouterState({ select: (s) => s.location.pathname });
  const roles = role ? (Array.isArray(role) ? role : [role]) : null;
  const descriptions: Record<string, string> = {
    "Respond to Deficiency":
      "Read the officer’s request, prepare your explanation and attach the required documents.",
    "Institution Dashboard": "Your applications, progress, and next steps at a glance.",
    "Officer Dashboard": "A clear view of your review workload and what needs attention.",
    "My Applications": "Manage submissions and follow every stage of your approval journey.",
    "Case Queue": "Find, prioritise, and review institution applications.",
    "Users & Roles": "Manage access to your approval workspace.",
    "Pre-Validation": "Find the gaps, understand the rules, and prepare a complete submission.",
    Reports: "Download saved reports and share permitted summaries with institutions.",
    "Request Details":
      "Confirm your institution’s details and explain the changes you are requesting.",
    "Document Checklist":
      "See what is required, what is conditional, and which alternatives you can provide.",
    Documents: "Upload original documents and follow their safety and readability checks.",
    "Review & Submit": "Check your saved information before confirming submission.",
    "Application Status": "Follow your submission and see the next action needed.",
    "Case Overview":
      "Understand the request, review key findings, and open the supporting evidence.",
    "Evidence Viewer":
      "Compare extracted information with the original document and record corrections.",
    "Document Authenticity": "Review issuer responses, signatures and provenance separately.",
    "Compliance Review": "Run applicable rules and review the evidence behind each result.",
    "Infrastructure & Inspection":
      "Compare declared measurements with supporting evidence and identify inspection needs.",
    "Review & Decision":
      "Record your assessment, request clarification, or route further verification.",
    "Document Verification": "Review assigned verification tasks and record a sourced response.",
    "Approved Records": "Compare previous approvals with the changes currently requested.",
    "Knowledge Sources": "Review and publish source versions used in regulatory explanations.",
    "New Application": "Choose the institution, academic year, and application category.",
    "Portal notices": "Keep institutions informed with clear, timely updates.",
    "Rule Library": "Review, test, and publish versioned compliance rules.",
    "Audit Trail": "Review who changed a record, when it changed, and why.",
    Connectors: "Explore demonstration configurations for external sources.",
    Settings: "Your profile, preferences, and account settings.",
  };
  let body: ReactNode;
  if (!hydrated)
    body = (
      <div className="loading-state" role="status">
        <span className="loading-dot" /> Preparing your workspace…
      </div>
    );
  else if (session.error)
    body = (
      <div role="alert">
        <p>The service is unavailable. Your saved work has not been changed.</p>
        <button className="btn btn-navy" onClick={session.retry}>
          Retry connection
        </button>
      </div>
    );
  else if (!user && !allowPublic && roles) body = <AuthRequired />;
  else if (user && roles && !roles.includes(user.role)) body = <AccessDenied />;
  else
    body = (
      <>
        <div className="page-heading">
          <div>
            <span className="eyebrow">
              {user ? `${user.role} workspace` : "Application portal"}
            </span>
            <h1>
              {title === "Institution Dashboard" || title === "Officer Dashboard"
                ? "Workspace overview"
                : title}
            </h1>
            <p>{descriptions[title] ?? "Review information and manage your next steps."}</p>
          </div>
          {act}
        </div>
        <div className="page-content">{children}</div>
      </>
    );
  const nav = user
    ? NAV[user.role].filter((n) => {
        if (user.roles.includes("auditor") && !user.roles.includes("admin"))
          return ["/admin/audit", "/notifications", "/settings"].includes(n.to);
        if (
          user.roles.includes("specialist") &&
          !user.roles.some((r) => ["officer", "supervisor"].includes(r))
        )
          return [
            "/officer/verification-queue",
            "/resources",
            "/notifications",
            "/settings",
          ].includes(n.to);
        return true;
      })
    : null;
  return (
    <div className="uv-workspace min-h-screen flex flex-col">
      <Header />
      <div className={`workspace ${nav ? "has-sidebar" : ""}`}>
        {nav && (
          <>
            <button
              className="mobile-menu btn btn-outline"
              aria-expanded={open}
              aria-controls="workspace-sidebar"
              onClick={() => setOpen(!open)}
            >
              {open ? <X size={17} /> : <Menu size={17} />} Workspace menu
            </button>
            <aside
              id="workspace-sidebar"
              className={`workspace-sidebar ${open ? "is-open" : ""}`}
              aria-label="Section navigation"
            >
              <div className="workspace-label">
                YOUR WORKSPACE
                <span>
                  {user?.role === "officer"
                    ? "Review & scrutiny"
                    : user?.role === "admin"
                      ? "Portal administration"
                      : "Institution"}
                </span>
              </div>
              <nav>
                {nav.map((n) => {
                  const active =
                    path.replace(/\/$/, "") === n.to ||
                    (n.to === "/institution/applications" &&
                      path.startsWith(n.to + "/") &&
                      !path.endsWith("/new")) ||
                    (n.to === "/institution/deficiencies" && path.startsWith(n.to + "/")) ||
                    (n.to === "/officer/queue" && path.startsWith("/officer/cases/"));
                  return (
                    <Link
                      key={n.to}
                      to={n.to}
                      aria-current={active ? "page" : undefined}
                      onClick={() => setOpen(false)}
                      className={`sidebar-link ${active ? "active" : ""}`}
                    >
                      <n.icon size={18} strokeWidth={1.8} />
                      {n.label}
                      {active && <span className="active-dot" />}
                    </Link>
                  );
                })}
              </nav>
              <div className="sidebar-help">
                <span className="help-icon">
                  <CircleHelp size={21} />
                </span>
                <b>A little guidance?</b>
                <p>A clear next step starts with the right guidance.</p>
                <Link to="/help">
                  Visit the help centre <ArrowRight size={14} />
                </Link>
              </div>
              <div className="sidebar-bottom">
                <span className="status-led" />
                Academic year 2026–27
              </div>
            </aside>
          </>
        )}
        <main id="main" className="workspace-main">
          <nav aria-label="Breadcrumb" className="breadcrumb">
            <Link to="/">Portal</Link>
            {crumbs.map((c, i) => (
              <span key={i}>
                <ChevronRight size={12} />
                {c.to ? <Link to={c.to}>{c.label}</Link> : <span>{c.label}</span>}
              </span>
            ))}
          </nav>
          {body}
          <Footer />
        </main>
      </div>
    </div>
  );
}
function AuthRequired() {
  return (
    <div className="empty-state">
      <ShieldCheck size={36} />
      <h2>Sign in to your workspace</h2>
      <p>Access your applications and continue where you left off.</p>
      <Link to="/login" className="btn btn-primary">
        Sign in <ArrowRight size={16} />
      </Link>
    </div>
  );
}
export function AccessDenied() {
  const user = useCurrentUser();
  return (
    <div className="empty-state">
      <ShieldCheck size={36} />
      <h2>This workspace is restricted</h2>
      <p>You’re signed in as {user?.name}. This page requires a different user role.</p>
      {user && (
        <Link to={userHome(user)} className="btn btn-primary">
          Return to my workspace <ArrowRight size={16} />
        </Link>
      )}
    </div>
  );
}
const statusTone: Record<string, string> = {
  Approved: "positive",
  Verified: "positive",
  Closed: "positive",
  Operational: "positive",
  Pass: "positive",
  Active: "positive",
  Rejected: "negative",
  "Mismatch Found": "negative",
  Open: "negative",
  Disabled: "neutral",
  Fail: "negative",
  "Deficiency Raised": "attention",
  "Under Scrutiny": "info",
  "Under Review": "attention",
  Responded: "info",
  Degraded: "attention",
  Submitted: "info",
};
export function Status({ s }: { s: string }) {
  return (
    <span className={`status-badge ${statusTone[s] ?? "neutral"}`}>
      <span />
      {s}
    </span>
  );
}
export function EmptyRow({ cols }: { cols: number }) {
  return (
    <tr>
      <td colSpan={cols}>
        <div className="table-empty">
          <Search size={24} />
          <b>No records to show</b>
          <span>Try adjusting your filters or check back later.</span>
        </div>
      </td>
    </tr>
  );
}
export const instName = (id: string) => institutions.find((i) => i.id === id)?.name ?? id;
export function Panel({
  title,
  children,
  className = "",
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <h2 className="panel-head">{title}</h2>
      <div className="panel-body">{children}</div>
    </section>
  );
}
export function DataTable({ children, ...props }: TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Scrollable records">
      <table {...props}>{children}</table>
    </div>
  );
}
export function Filters({ children }: { children: ReactNode }) {
  return <div className="filter-bar">{children}</div>;
}
export function useFilter() {
  return useState("");
}
export function MetricCard({
  label,
  value,
  hint,
  icon: Icon,
  to,
  tone = "teal",
  search,
}: {
  label: string;
  value: number;
  hint: string;
  icon: LucideIcon;
  to: string;
  tone?: string;
  search?: Record<string, string>;
}) {
  return (
    <Link to={to} search={search} className={`metric-card ${tone}`}>
      <div className="flex items-center justify-between gap-2">
        <span>{label}</span>
        <span className="metric-icon">
          <Icon size={19} />
        </span>
      </div>
      <strong>{value.toString().padStart(2, "0")}</strong>
      <div className="metric-hint">
        {hint}
        <ArrowRight size={14} />
      </div>
    </Link>
  );
}
