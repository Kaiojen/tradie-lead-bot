"use client";

import { useState } from "react";

import { AppSidebar } from "@/components/app-sidebar";
import { ProtectedPage } from "@/components/protected-page";
import { apiFetch } from "@/lib/api";

const FAQ_ITEMS = [
  {
    question: "How do I update my business details?",
    answer:
      "Open Settings, adjust the business profile fields and save. The changes apply to the account immediately."
  },
  {
    question: "Where do I find the embed code?",
    answer:
      "The embed code is in Settings under Integrations. Copy it into your website platform and publish the page."
  },
  {
    question: "What if a customer SMS fails?",
    answer:
      "The Inbox shows failed SMS in red with retry actions so you can resend without losing context."
  },
  {
    question: "Can I invite my team?",
    answer:
      "Yes. The Team section in Settings sends an invite email with a magic link for each teammate."
  }
] as const;

export default function SupportPage() {
  const [message, setMessage] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);

  async function submit() {
    await apiFetch("/api/support", {
      method: "POST",
      body: { message }
    });
    setMessage("");
    setFeedback("Support request received.");
  }

  return (
    <ProtectedPage>
      {() => (
        <>
          <AppSidebar />
          <section className="inbox-card">
            <div className="eyebrow">Support</div>
            <h1 style={{ marginTop: 0 }}>We respond within 24 hours.</h1>
            <div className="form-grid">
              <textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Tell us what you need help with."
              />
              <button className="button" type="button" onClick={() => void submit()}>
                Send
              </button>
              {feedback ? <p className="notice">{feedback}</p> : null}
            </div>
          </section>

          <aside className="detail-card">
            <div className="eyebrow">Support</div>
            <div className="stack">
              {FAQ_ITEMS.map((item) => (
                <article className="faq-card compact" key={item.question}>
                  <h3>{item.question}</h3>
                  <p className="muted">{item.answer}</p>
                </article>
              ))}
              <p className="muted">Direct support email can be added once the first real questions settle.</p>
            </div>
          </aside>
        </>
      )}
    </ProtectedPage>
  );
}
