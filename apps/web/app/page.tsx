import Link from "next/link";

import { MarketingNav } from "@/components/marketing-nav";

const FAQ_ITEMS = [
  {
    question: "How fast does it reply to a new enquiry?",
    answer:
      "The system sends the first SMS straight after the enquiry is received, then surfaces the job in the Inbox."
  },
  {
    question: "Can I see failed messages?",
    answer:
      "Yes. Failed SMS, retry actions and review flags stay visible in the Inbox so nothing disappears silently."
  },
  {
    question: "Does it work after hours?",
    answer:
      "Yes. The after-hours auto-reply uses your business hours and keeps the customer informed while you are on site."
  },
  {
    question: "Is this built for Aussie trades?",
    answer:
      "Yes. The copy, phone formatting and onboarding flow are tuned for Australian tradies."
  },
  {
    question: "Can I change the message style?",
    answer:
      "Yes. The Auto-Replies editor lets you adjust the template copy for different jobs and tones."
  },
  {
    question: "What happens during the trial?",
    answer:
      "You can connect the inbox, test the workflow and validate the fit before billing becomes active."
  }
] as const;

export default function LandingPage() {
  return (
    <>
      <MarketingNav />
      <main className="page-shell">
        <section className="hero">
          <div className="hero-copy">
            <div className="eyebrow">Built for Australian tradies</div>
            <h1>Never miss a job while you're on the tools.</h1>
            <p className="lead">
              Instantly reply to new enquiries and get SMS alerts for urgent jobs,
              automatically.
            </p>
            <p className="lead">
              The automated inbox that replies to customers while you're busy, so you
              win the quote before your competitors even call back.
            </p>
            <div className="hero-actions">
              <Link href="/login" className="button">
                Start free trial
              </Link>
              <Link href="/pricing" className="button-secondary">
                View pricing
              </Link>
            </div>
          </div>

          <div className="hero-card">
            <div className="hero-stat">
              <strong>14 days</strong>
              <span className="muted">Free trial with no card upfront.</span>
            </div>
            <div className="hero-stat">
              <strong>2 SMS</strong>
              <span className="muted">One Auto-Reply for the customer. One New Job Alert for you.</span>
            </div>
            <div className="hero-stat">
              <strong>1 saved job</strong>
              <span className="muted">Pays for a whole year if you stop missing quotes.</span>
            </div>
          </div>
        </section>

        <section className="section-grid">
          <article className="section-card">
            <h3>Every missed call is a missed job</h3>
            <p>
              New enquiries hit the web form, land in the database first, and stay visible
              in your Inbox even if SMS or AI has a bad day.
            </p>
          </article>
          <article className="section-card">
            <h3>How it works</h3>
            <p>
              Enquiry comes in. Our system replies by SMS. You get a concise alert with the
              suburb, service and urgency.
            </p>
          </article>
          <article className="section-card">
            <h3>Operational, not analytical</h3>
            <p>
              The Inbox is designed to clear work. New, Follow Up and Done keep the screen
              focused on action instead of dashboards.
            </p>
          </article>
        </section>

        <section className="faq-section">
          <div className="eyebrow">FAQ</div>
          <div className="faq-grid">
            {FAQ_ITEMS.map((item) => (
              <article className="faq-card" key={item.question}>
                <h3>{item.question}</h3>
                <p className="muted">{item.answer}</p>
              </article>
            ))}
          </div>
        </section>
      </main>
    </>
  );
}
