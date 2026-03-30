"use client";

import { FormEvent, useState } from "react";
import { useParams } from "next/navigation";

export default function PublicEnquiryFormPage() {
  const params = useParams<{ token: string }>();
  const [status, setStatus] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/api/leads/ingest`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        form_token: params.token,
        customer_name: formData.get("customer_name"),
        customer_phone: formData.get("customer_phone"),
        customer_email: formData.get("customer_email"),
        suburb: formData.get("suburb"),
        service_requested: formData.get("service_requested"),
        raw_message: formData.get("raw_message"),
        consent_to_sms: formData.get("consent_to_sms") === "on"
      })
    });

    if (!response.ok) {
      setStatus("We couldn't send your enquiry right now. Please try again.");
      return;
    }

    setStatus("Thanks. Your enquiry has been received.");
    event.currentTarget.reset();
  }

  return (
    <main className="page-shell" style={{ padding: "48px 0 64px" }}>
      <section className="auth-card">
        <div className="eyebrow">Quote Request</div>
        <h1 style={{ marginTop: 0 }}>Tell us about the job.</h1>
        <form className="form-grid" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="customer-name">Your name</label>
            <input id="customer-name" name="customer_name" required />
          </div>
          <div className="field">
            <label htmlFor="customer-phone">Mobile number</label>
            <input id="customer-phone" name="customer_phone" placeholder="0412 345 678" required />
          </div>
          <div className="field">
            <label htmlFor="customer-email">Email</label>
            <input id="customer-email" name="customer_email" type="email" />
          </div>
          <div className="field">
            <label htmlFor="suburb">Suburb</label>
            <input id="suburb" name="suburb" required />
          </div>
          <div className="field">
            <label htmlFor="service-requested">What do you need help with?</label>
            <input id="service-requested" name="service_requested" required />
          </div>
          <div className="field">
            <label htmlFor="raw-message">Extra details</label>
            <textarea id="raw-message" name="raw_message" />
          </div>
          <label className="checkbox-row">
            <input type="checkbox" name="consent_to_sms" defaultChecked />
            I consent to receive SMS updates about this enquiry.
          </label>
          <p className="muted">
            Privacy notice: we collect only the details needed to respond to your enquiry.
          </p>
          <button className="button" type="submit">
            Send enquiry
          </button>
          {status ? <p className="notice">{status}</p> : null}
        </form>
      </section>
    </main>
  );
}
