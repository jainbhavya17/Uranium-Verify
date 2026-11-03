import { HomeCarousel } from "@/components/home-carousel";
import { api } from "@/features/api";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import {
  ArrowRight,
  Check,
  FileText,
  Files,
  MessageSquare,
  MousePointer2,
  Plus,
  Minus,
  Search,
  ShieldCheck,
  Landmark,
  CheckCircle2,
} from "lucide-react";
import { PublicShell } from "@/components/portal";
import { Link } from "@/components/link";
import { NoticesSection } from "@/components/notices";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { userHome, useCurrentUser } from "@/lib/backend-session";
import { usePortalContent } from "@/lib/portal-content";
import { seo, SITE_DESCRIPTION } from "@/lib/seo";
export const Route = createFileRoute("/")({
  head: seo("Uranium Verify", SITE_DESCRIPTION),
  component: Home,
});
const benefits = [
  {
    title: "One connected approval journey",
    text: "Your application, documents, queries, and review findings stay connected in one place, so everyone has the complete context from preparation through officer review.",
  },
  {
    title: "Clear queries. Better responses.",
    text: "Institutions can read each deficiency, check its due date, and record a response. Reviewing officers can re-verify and close the query in the same workspace.",
  },
  {
    title: "Every action, traceable.",
    text: "Follow the application history from the first draft to the recorded review. Officers and administrators can review the actions that brought a case to its current stage.",
  },
];
const features = [
  {
    title: "Applications",
    text: "Prepare and submit your institution’s application.",
    type: "application",
    tone: "mint",
    to: "/institution/applications",
  },
  {
    title: "Documents",
    text: "Keep every required document in one place.",
    type: "documents",
    tone: "pink",
    to: "/resources",
  },
  {
    title: "Review & respond",
    text: "Resolve queries with clear, recorded responses.",
    type: "review",
    tone: "blue",
    to: "/institution/deficiencies",
  },
  {
    title: "Track your application",
    text: "See your status and the next action to take.",
    type: "track",
    tone: "yellow",
    to: "track",
  },
];
export function TrackApplication({ card = false }: { card?: boolean }) {
  const [reference, setReference] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [result, setResult] = useState<{
      id: string;
      reference: string;
      type: string;
      academicYear: string;
      status: string;
    } | null>(null);
  return (
    <Dialog>
      <DialogTrigger asChild>
        {card ? (
          <button className="uv-feature uv-yellow">
            <h3>Track your application</h3>
            <FeatureIllustration type="track" />
            <span className="uv-feature-bottom">
              <span>See your status and the next action to take.</span>
              <ArrowRight size={21} />
            </span>
          </button>
        ) : (
          <button className="uv-text-button">
            Track your application <ArrowRight size={17} />
          </button>
        )}
      </DialogTrigger>
      <DialogContent className="uv-dialog">
        <DialogTitle>Where does your application stand?</DialogTitle>
        <DialogDescription>
          Enter the application ID or acknowledgment reference from your submission. Sign in for
          documents and detailed review history.
        </DialogDescription>
        <form
          className="uv-tracking-form"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            setResult(null);
            try {
              const r = await api<typeof result>(
                `/portal/track/${encodeURIComponent(reference.trim())}`,
              );
              setResult(r.data);
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label htmlFor="tracking-reference">Application ID / acknowledgment reference</label>
          <input
            id="tracking-reference"
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            required
            maxLength={100}
            placeholder="e.g. APP-01482"
            autoComplete="off"
          />
          <button className="uv-button uv-coral" disabled={busy}>
            {busy ? "Checking…" : "Check application status"}
            <Search size={16} />
          </button>
        </form>
        {error && <p role="alert">{error}</p>}
        {result && (
          <div className="uv-tracking-result" role="status">
            <span className="uv-eyebrow">{result.reference}</span>
            <h3>{result.status}</h3>
            <p>
              {result.type} · Academic year {result.academicYear}
            </p>
          </div>
        )}
        <Link className="uv-button" to="/institution/applications">
          Open my applications <ArrowRight size={16} />
        </Link>
      </DialogContent>
    </Dialog>
  );
}
function FeatureIllustration({ type }: { type: string }) {
  return (
    <div className={`uv-feature-art uv-art-${type}`} aria-hidden="true">
      {type === "application" ? (
        <>
          <div className="uv-paper">
            <FileText size={64} strokeWidth={1.15} />
          </div>
          <div className="uv-paper-offset" />
          <MousePointer2 className="uv-cursor" size={35} fill="currentColor" />
        </>
      ) : type === "documents" ? (
        <>
          <Files size={83} strokeWidth={1.15} />
          <div className="uv-mini-check">
            <Check size={24} />
          </div>
        </>
      ) : type === "review" ? (
        <>
          <MessageSquare className="uv-chat-one" size={67} strokeWidth={1.2} />
          <MessageSquare className="uv-chat-two" size={65} strokeWidth={1.2} fill="#2658ab" />
        </>
      ) : (
        <div className="uv-progress-art">
          <i />
          <i />
          <i>
            <Check size={22} />
          </i>
        </div>
      )}
    </div>
  );
}
function HeroArtwork() {
  return (
    <div
      className="uv-hero-art"
      aria-label="Illustration of an institution application and document checklist"
    >
      <div className="uv-pink-grid" />
      <div className="uv-lemon-square" />
      <div className="uv-collage-label">
        From submission
        <br />
        to scrutiny <ArrowRight size={19} />
      </div>
      <img
        className="uv-campus"
        src="/campus.svg"
        alt="Architectural illustration of a technical institution"
      />
      <div className="uv-application-sheet">
        <div className="uv-window-dots">
          <i />
          <i />
          <i />
        </div>
        <span className="uv-eyebrow">ACADEMIC YEAR 2026–27</span>
        <h3>
          Application for
          <br />
          AICTE approval
        </h3>
        <div className="uv-form-lines">
          <i />
          <i />
          <i />
          <i />
          <i />
        </div>
        <span className="uv-submitted">
          <CheckCircle2 size={15} /> Submitted
        </span>
      </div>
      <div className="uv-document-sheet">
        <div className="uv-mini-caption">EVERY DOCUMENT, IN VIEW</div>
        <h3>Documents checklist</h3>
        {[
          "Registered land deed",
          "Building occupancy certificate",
          "Faculty qualifications",
          "Applicable affidavits",
        ].map((s, i) => (
          <div key={s}>
            <FileText size={16} />
            <span>{s}</span>
            {i < 2 ? (
              <CheckCircle2 size={15} className="uv-verified" />
            ) : (
              <i className="uv-pending" />
            )}
          </div>
        ))}
        <span className="uv-sheet-footnote">A complete record. A clearer review.</span>
      </div>
      <span className="uv-hero-art-caption">ILLUSTRATIVE WORKSPACE · SAMPLE DATA</span>
    </div>
  );
}
function Home() {
  const user = useCurrentUser();
  const content = usePortalContent();
  const announcement = content.data?.data.announcement ?? {
    enabled: false,
    text: "",
    link: "/notices",
  };
  const [active, setActive] = useState<number | null>(0);
  const workspace = user ? userHome(user) : "/login";
  const newApp =
    user?.role === "institution" ? "/institution/applications/new" : user ? workspace : "/login";
  return (
    <PublicShell landing>
      <section className="uv-hero">
        <img className="uv-mandala uv-mandala-left" src="/mandala.png" alt="" aria-hidden="true" />
        <div className="uv-hero-intro">
          {announcement.enabled &&
            (announcement.link.startsWith("https:") ? (
              <a className="uv-announcement" href={announcement.link}>
                <b>NEW</b>
                {announcement.text}
                <ArrowRight size={14} />
              </a>
            ) : (
              <Link className="uv-announcement" to={announcement.link}>
                <b>NEW</b>
                {announcement.text}
                <ArrowRight size={14} />
              </Link>
            ))}
          <h1>Platform built for AICTE</h1>
          <p>
            One workspace for institutions and AICTE to submit applications,
            <br className="uv-desktop-break" /> review documents, and move approvals forward.
          </p>
          <div className="uv-hero-actions">
            <Link to="/sign-up" className="uv-button">
              Sign up
            </Link>
            <Link to={newApp} className="uv-button uv-coral">
              {user && user.role !== "institution"
                ? "Open your workspace"
                : "Start your application"}
              <ArrowRight size={16} />
            </Link>
          </div>
        </div>
        <HomeCarousel campus={<HeroArtwork />} />
      </section>
      <section id="platform" className="uv-section uv-platform">
        <div className="uv-section-heading">
          <span className="uv-eyebrow">THE URANIUM VERIFY PLATFORM</span>
          <h2>
            A platform that transforms
            <br className="uv-desktop-break" /> application scrutiny.
          </h2>
          <p>
            Keep applications, supporting documents, queries, and decisions connected
            <br className="uv-desktop-break" /> from the first submission to the final outcome.
          </p>
        </div>
        <div className="uv-feature-grid">
          {features.map((f) =>
            f.to === "track" ? (
              <TrackApplication key={f.title} card />
            ) : (
              <Link
                key={f.title}
                className={`uv-feature uv-${f.tone}`}
                to={user?.role === "officer" && f.type === "review" ? "/officer/queue" : f.to}
              >
                <h3>{f.title}</h3>
                <FeatureIllustration type={f.type} />
                <span className="uv-feature-bottom">
                  <span>{f.text}</span>
                  <ArrowRight size={21} />
                </span>
              </Link>
            ),
          )}
        </div>
      </section>
      <section className="uv-section uv-why" aria-labelledby="why-title">
        <div>
          <span className="uv-eyebrow">BUILT AROUND YOUR NEXT STEP</span>
          <h2 id="why-title">Why Uranium Verify?</h2>
          <p className="uv-why-intro">
            Clarity for institutions.
            <br />
            Context for reviewers.
          </p>
          <div className="uv-accordion">
            {benefits.map((b, i) => (
              <div className={active === i ? "is-open" : ""} key={b.title}>
                <h3>
                  <button
                    aria-expanded={active === i}
                    aria-controls={`benefit-${i}`}
                    id={`benefit-trigger-${i}`}
                    onClick={() => setActive(active === i ? null : i)}
                  >
                    {b.title}
                    {active === i ? <Minus size={18} /> : <Plus size={18} />}
                  </button>
                </h3>
                <div
                  id={`benefit-${i}`}
                  role="region"
                  aria-labelledby={`benefit-trigger-${i}`}
                  hidden={active !== i}
                >
                  <p>{b.text}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div
          className="uv-workflow"
          aria-label="Institution submits an application and AICTE reviews and responds"
        >
          <div className="uv-flow-window">
            <div className="uv-window-dots">
              <i />
              <i />
              <i />
            </div>
            <h3>Application</h3>
            <div className="uv-form-lines">
              <i />
              <i />
              <i />
            </div>
            <span className="uv-submitted">
              <CheckCircle2 size={14} />
              Submitted
            </span>
            <span className="uv-role-tag">INSTITUTION</span>
          </div>
          <div className="uv-flow-connector">
            ↓<span>Shared context</span>
          </div>
          <div className="uv-flow-window uv-flow-review">
            <div className="uv-window-dots">
              <i />
              <i />
              <i />
            </div>
            <h3>Review & respond</h3>
            <div className="uv-query-lines">
              <i />
              <i />
              <i />
            </div>
            <span className="uv-role-tag">AICTE OFFICER</span>
          </div>
          <span className="uv-workflow-caption">
            <ShieldCheck size={14} /> One record. Every step accounted for.
          </span>
        </div>
      </section>
      <NoticesSection />
      <section id="process" className="uv-section uv-process">
        <div>
          <span className="uv-eyebrow">A CLEAR PATH FORWARD</span>
          <h2>Know what comes next.</h2>
          <p>
            Follow the application journey from submission
            <br className="uv-desktop-break" /> to final decision, with clear steps for
            institutions.
          </p>
          <Link to="/resources" className="uv-button">
            Explore the approval process <ArrowRight size={16} />
          </Link>
        </div>
        <ol>
          {[
            {
              title: "Submit application",
              text: "Complete the form and submit the required documents.",
            },
            {
              title: "Scrutiny by AICTE",
              text: "An officer reviews the application and its evidence.",
            },
            {
              title: "Respond to queries",
              text: "Address deficiencies if clarification is required.",
            },
            { title: "Final decision", text: "View the recorded outcome and application history." },
          ].map((s, i) => (
            <li key={s.title}>
              <span>{i + 1}</span>
              <div>
                <h3>{s.title}</h3>
                <p>{s.text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
      <section className="uv-section uv-cta">
        <img className="uv-mandala uv-mandala-right" src="/mandala.png" alt="" aria-hidden="true" />
        <Landmark size={95} strokeWidth={0.8} aria-hidden="true" />
        <div>
          <h2>Ready for your next chapter?</h2>
          <p>Start your application and keep every step in view.</p>
        </div>
        <Link to={workspace} className="uv-button uv-navy">
          Go to your workspace <ArrowRight size={18} />
        </Link>
      </section>
      <div className="uv-track-strip">
        <TrackApplication />
        <span>Local prototype · No live AICTE connection</span>
      </div>
    </PublicShell>
  );
}
