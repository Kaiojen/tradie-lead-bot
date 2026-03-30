import { MarketingNav } from "@/components/marketing-nav";

export default function PricingPage() {
  return (
    <>
      <MarketingNav />
      <main className="page-shell">
        <section style={{ padding: "20px 0 12px" }}>
          <div className="eyebrow">Pricing</div>
          <h1 style={{ margin: 0, fontSize: "3.6rem", letterSpacing: "-0.06em" }}>
            Simple pricing for a reliable Inbox.
          </h1>
          <p className="lead">
            One saved job pays for a full year.
          </p>
        </section>

        <section className="pricing-grid">
          <article className="price-card">
            <div className="eyebrow">Early Adopter</div>
            <div className="price">AUD 99</div>
            <p className="pricing-note">For the first 10 customers. 14-day free trial. No card up front.</p>
          </article>
          <article className="price-card">
            <div className="eyebrow">Standard</div>
            <div className="price">AUD 149</div>
            <p className="pricing-note">Full operational Inbox with SMS alerts, Auto-Replies and account access.</p>
          </article>
        </section>
      </main>
    </>
  );
}
