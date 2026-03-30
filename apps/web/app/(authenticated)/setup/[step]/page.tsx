"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { AppSidebar } from "@/components/app-sidebar";
import { ProtectedPage } from "@/components/protected-page";
import { apiFetch, type SetupState } from "@/lib/api";

const STEP_TITLES = {
  "1": "Business Basics",
  "2": "Your Number",
  "3": "Your Auto-Reply",
  "4": "Test Drive",
  "5": "Connect"
} as const;

const TEMPLATE_VARIANTS = {
  plumber: {
    title: "Plumber",
    variants: [
      {
        key: "professional",
        label: "Professional",
        content:
          "Thanks for contacting [Business Name]. We have received your plumbing enquiry and will review the details shortly."
      },
      {
        key: "friendly",
        label: "Friendly",
        content:
          "Hi, thanks for reaching out to [Business Name]. We are on the tools right now but we will get back to you soon."
      },
      {
        key: "direct",
        label: "Direct",
        content:
          "[Business Name] here. Thanks for the job details. We will check the request and reply shortly."
      }
    ]
  },
  electrician: {
    title: "Electrician",
    variants: [
      {
        key: "professional",
        label: "Professional",
        content:
          "Thanks for contacting [Business Name]. Your electrical enquiry has been received and we will get back to you shortly."
      },
      {
        key: "friendly",
        label: "Friendly",
        content:
          "Hi, thanks for the message to [Business Name]. We are out on a job and will reply as soon as we can."
      },
      {
        key: "direct",
        label: "Direct",
        content:
          "[Business Name] received your enquiry. We will review it and respond shortly."
      }
    ]
  },
  general: {
    title: "General",
    variants: [
      {
        key: "professional",
        label: "Professional",
        content:
          "Thanks for reaching out to [Business Name]. We have received your enquiry and will respond shortly."
      },
      {
        key: "friendly",
        label: "Friendly",
        content:
          "Hi, thanks for contacting [Business Name]. We are away from the desk and will be back to you soon."
      },
      {
        key: "direct",
        label: "Direct",
        content: "[Business Name] here. Thanks for the message. We will reply shortly."
      }
    ]
  }
} as const;

type TemplateVariantKey = "professional" | "friendly" | "direct";

function normalizeTradeType(value: string) {
  if (value === "plumber") {
    return "plumber" as const;
  }
  if (value === "electrician") {
    return "electrician" as const;
  }
  return "general" as const;
}

export default function SetupStepPage() {
  const router = useRouter();
  const params = useParams<{ step: string }>();
  const step = useMemo(() => params.step ?? "1", [params.step]);
  const [setupState, setSetupState] = useState<SetupState | null>(null);
  const [businessName, setBusinessName] = useState("");
  const [businessType, setBusinessType] = useState("plumber");
  const [primaryPhone, setPrimaryPhone] = useState("");
  const [autoReply, setAutoReply] = useState("");
  const [selectedVariant, setSelectedVariant] = useState<TemplateVariantKey>("professional");
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    void apiFetch<SetupState>("/api/setup").then((payload) => {
      setSetupState(payload);
      setBusinessName(payload.account.business_name ?? "");
      setBusinessType(payload.account.business_type ?? "plumber");
      setPrimaryPhone(payload.account.primary_phone ?? "");
      const tradeType = normalizeTradeType(payload.account.business_type ?? "plumber");
      setAutoReply(TEMPLATE_VARIANTS[tradeType].variants[0].content);
    });
  }, []);

  const tradeType = normalizeTradeType(businessType);
  const currentTemplateSet = TEMPLATE_VARIANTS[tradeType];

  async function nextStep() {
    router.push(`/setup/${Math.min(Number(step) + 1, 5)}`);
  }

  async function handleStepAction() {
    if (step === "1") {
      await apiFetch("/api/setup/business-basics", {
        method: "POST",
        body: { business_name: businessName, business_type: businessType }
      });
      await nextStep();
      return;
    }

    if (step === "2") {
      await apiFetch("/api/setup/your-number", {
        method: "POST",
        body: { primary_phone: primaryPhone }
      });
      await nextStep();
      return;
    }

    if (step === "3") {
      await apiFetch("/api/setup/auto-reply", {
        method: "POST",
        body: { content: autoReply, is_active: true }
      });
      await nextStep();
      return;
    }

    if (step === "4") {
      await apiFetch("/api/setup/test-drive", {
        method: "POST",
        body: { phone_number: primaryPhone }
      });
      setFeedback("Test SMS queued. Check your phone, then continue.");
      return;
    }

    await apiFetch("/api/setup/complete", {
      method: "POST"
    });
    router.push("/inbox");
  }

  return (
    <ProtectedPage>
      {() => (
        <>
          <AppSidebar />
          <section className="inbox-card">
            <div className="eyebrow">Setup</div>
            <h1 style={{ marginTop: 0 }}>{STEP_TITLES[step as keyof typeof STEP_TITLES] ?? "Setup"}</h1>
            <div className="progress-row">
              {[1, 2, 3, 4, 5].map((stepNumber) => (
                <div
                  key={stepNumber}
                  className={`progress-dot${stepNumber <= Number(step) ? " active" : ""}`}
                />
              ))}
            </div>

            {step === "1" ? (
              <div className="form-grid">
                <div className="field">
                  <label htmlFor="business-name">Business name</label>
                  <input
                    id="business-name"
                    value={businessName}
                    onChange={(event) => setBusinessName(event.target.value)}
                  />
                </div>
                <div className="field">
                  <label htmlFor="business-type">Trade type</label>
                  <select
                    id="business-type"
                    value={businessType}
                    onChange={(event) => setBusinessType(event.target.value)}
                  >
                    <option value="plumber">Plumber</option>
                    <option value="electrician">Electrician</option>
                    <option value="cleaner">Cleaner</option>
                    <option value="locksmith">Locksmith</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>
            ) : null}

            {step === "2" ? (
              <div className="form-grid">
                <div className="field">
                  <label htmlFor="alert-number">Mobile number</label>
                  <input
                    id="alert-number"
                    placeholder="0412 345 678"
                    value={primaryPhone}
                    onChange={(event) => setPrimaryPhone(event.target.value)}
                  />
                </div>
                <p className="muted">We'll send you an SMS whenever a new enquiry comes in.</p>
              </div>
            ) : null}

            {step === "3" ? (
              <div className="form-grid">
                <p className="muted">
                  Choose a starter for {currentTemplateSet.title}. These are placeholders until the
                  final Gemini copy lands.
                </p>
                <div className="variant-grid">
                  {currentTemplateSet.variants.map((variant) => (
                    <button
                      key={variant.key}
                      type="button"
                      className={`variant-card${selectedVariant === variant.key ? " selected" : ""}`}
                      onClick={() => {
                        setSelectedVariant(variant.key);
                        setAutoReply(variant.content);
                      }}
                    >
                      <strong>{variant.label}</strong>
                      <p className="muted">{variant.content}</p>
                    </button>
                  ))}
                </div>
                <div className="field">
                  <label htmlFor="auto-reply">Selected auto-reply</label>
                  <textarea
                    id="auto-reply"
                    value={autoReply}
                    onChange={(event) => setAutoReply(event.target.value)}
                  />
                </div>
              </div>
            ) : null}

            {step === "4" ? (
              <div className="form-grid">
                <p className="muted">
                  We'll send a real SMS to {primaryPhone || "your alert number"}.
                </p>
                {feedback ? <p className="notice">{feedback}</p> : null}
              </div>
            ) : null}

            {step === "5" && setupState ? (
              <div className="form-grid">
                <div className="field">
                  <label>Website form token</label>
                  <input readOnly value={setupState.connect.form_token} />
                </div>
                <div className="field">
                  <label>Embed code</label>
                  <textarea readOnly value={setupState.connect.embed_code} />
                </div>
                <div className="field">
                  <label>Google Business link</label>
                  <input readOnly value={setupState.connect.google_business_link} />
                </div>
              </div>
            ) : null}

            <div className="filter-row">
              <button className="button" type="button" onClick={() => void handleStepAction()}>
                {step === "5" ? "Go to my Inbox" : step === "4" ? "Send test SMS" : "Next"}
              </button>
              {step === "4" ? (
                <button className="button-secondary" type="button" onClick={() => router.push("/setup/5")}>
                  Looks good, continue
                </button>
              ) : null}
            </div>
          </section>

          <aside className="detail-card">
            <div className="eyebrow">Progress</div>
            <h2 style={{ marginTop: 0 }}>Five short steps</h2>
            <p className="muted">
              Business Basics, Your Number, Your Auto-Reply, Test Drive and Connect.
            </p>
          </aside>
        </>
      )}
    </ProtectedPage>
  );
}
