import { useEffect, useState, type ReactNode } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Pause,
  Play,
  FileCheck2,
  ClipboardCheck,
  CheckCircle2,
} from "lucide-react";
import { Link } from "./link";
const slides = [
  {
    title: "Prepare your institution’s next chapter",
    text: "Choose your application, save your details and follow a checklist that adapts to your request.",
  },
  {
    title: "The right documents. Clearly defined.",
    text: "Know what each certificate and declaration must contain. Upload once, follow processing and correct any issue before submission.",
  },
  {
    title: "Every review has a clear next step.",
    text: "Read officer queries, respond with supporting documents and follow the recorded progress using your application ID.",
  },
];
export function HomeCarousel({ campus }: { campus: ReactNode }) {
  const [index, setIndex] = useState(0),
    [paused, setPaused] = useState(false),
    [hover, setHover] = useState(false),
    [focus, setFocus] = useState(false),
    [reduced, setReduced] = useState(true);
  useEffect(() => {
    const m = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(m.matches);
    update();
    m.addEventListener("change", update);
    return () => m.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    if (paused || hover || focus || reduced) return;
    const timer = window.setInterval(() => setIndex((i) => (i + 1) % slides.length), 7000);
    return () => window.clearInterval(timer);
  }, [paused, hover, focus, reduced]);
  return (
    <section
      className="uv-home-carousel"
      aria-roledescription="carousel"
      aria-label="Application journey"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onFocusCapture={() => setFocus(true)}
      onBlurCapture={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setFocus(false);
      }}
    >
      <div className="uv-carousel-stage">
        {slides.map((slide, i) => (
          <div
            className={`uv-carousel-slide slide-${i}`}
            key={slide.title}
            hidden={index !== i}
            role="group"
            aria-roledescription="slide"
            aria-label={`${i + 1} of ${slides.length}`}
          >
            {i === 0 ? (
              campus
            ) : (
              <div className="uv-carousel-feature">
                <div className="uv-carousel-copy">
                  <span className="uv-eyebrow">
                    {i === 1 ? "DOCUMENTS, IN ORDER" : "REVIEW, WITH CONTEXT"}
                  </span>
                  <h2>{slide.title}</h2>
                  <p>{slide.text}</p>
                  <Link className="uv-button" to={i === 1 ? "/resources" : "/login"}>
                    {i === 1 ? "Document guidance" : "Open your workspace"}
                    <ArrowRight size={17} />
                  </Link>
                </div>
                <div className="uv-carousel-paper">
                  <div className="uv-window-dots">
                    <i />
                    <i />
                    <i />
                  </div>
                  <h3>{i === 1 ? "Your document checklist" : "Application APP-01482"}</h3>
                  {(i === 1
                    ? [
                        "Registered land deed",
                        "Building occupancy certificate",
                        "Current fire safety certificate",
                        "Applicable affidavits",
                      ]
                    : [
                        "Application received",
                        "Documents under review",
                        "Clarification requested",
                        "Response submitted",
                      ]
                  ).map((t, n) => (
                    <div className="uv-carousel-check" key={t}>
                      {i === 1 ? <FileCheck2 size={20} /> : <ClipboardCheck size={20} />}
                      <span>{t}</span>
                      {n < 2 ? <CheckCircle2 size={17} /> : <span className="uv-carousel-dot" />}
                    </div>
                  ))}
                  <small>
                    {i === 1
                      ? "Requirements follow your application details."
                      : "Read the request. Respond. Track your progress."}
                  </small>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="uv-carousel-controls">
        <p aria-live={paused || focus ? "polite" : "off"}>
          <span>0{index + 1} / 03</span>
          {slides[index].title}
        </p>
        <div>
          <button onClick={() => setIndex((i) => (i + 2) % 3)} aria-label="Previous slide">
            <ArrowLeft size={18} />
          </button>
          <div className="uv-carousel-dots">
            {slides.map((s, i) => (
              <button
                key={s.title}
                aria-label={`Show slide ${i + 1}: ${s.title}`}
                aria-pressed={i === index}
                onClick={() => setIndex(i)}
              />
            ))}
          </div>
          <button onClick={() => setIndex((i) => (i + 1) % 3)} aria-label="Next slide">
            <ArrowRight size={18} />
          </button>
          <button
            disabled={reduced}
            onClick={() => setPaused((p) => !p)}
            aria-label={
              reduced
                ? "Automatic rotation disabled by reduced-motion preference"
                : paused
                  ? "Play slides"
                  : "Pause slides"
            }
          >
            {paused || reduced ? <Play size={16} /> : <Pause size={16} />}
          </button>
        </div>
      </div>
    </section>
  );
}
