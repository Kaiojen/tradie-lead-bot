"use client";

import { useEffect, useState } from "react";

import { AppSidebar } from "@/components/app-sidebar";
import { ProtectedPage } from "@/components/protected-page";
import {
  apiFetch,
  type BillingPortalResponse,
  type SessionContext,
  type SubscriptionSummary
} from "@/lib/api";

function formatDateLabel(value?: string | null) {
  if (!value) {
    return "Not set";
  }

  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

function formatStatusLabel(status?: string | null) {
  if (!status) {
    return "Trial";
  }
  if (status === "past_due") {
    return "Payment issue";
  }
  return status.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function SubscriptionContent({ sessionContext }: { sessionContext: SessionContext }) {
  const [subscription, setSubscription] = useState<SubscriptionSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);
  const [activeAction, setActiveAction] = useState<"portal" | "cancel" | null>(null);

  useEffect(() => {
    let mounted = true;

    async function loadSubscription() {
      try {
        const payload = await apiFetch<SubscriptionSummary>("/api/subscription");
        if (!mounted) {
          return;
        }
        setSubscription(payload);
        setError(null);
      } catch (loadError) {
        if (!mounted) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Unable to load subscription.");
      }
    }

    void loadSubscription();
    return () => {
      mounted = false;
    };
  }, []);

  async function handleManageBilling() {
    setActiveAction("portal");
    setActionError(null);
    setActionFeedback(null);

    try {
      const payload = await apiFetch<BillingPortalResponse>("/api/subscription/portal", {
        method: "POST"
      });
      window.location.assign(payload.url);
    } catch (requestError) {
      setActionError(
        requestError instanceof Error ? requestError.message : "Unable to open billing portal."
      );
    } finally {
      setActiveAction(null);
    }
  }

  async function handleCancel() {
    setActiveAction("cancel");
    setActionError(null);
    setActionFeedback(null);

    try {
      const updated = await apiFetch<SubscriptionSummary>("/api/subscription/cancel", {
        method: "POST"
      });
      setSubscription(updated);
      setActionFeedback(
        updated.current_period_end
          ? `Your subscription ends on ${formatDateLabel(updated.current_period_end)}.`
          : "Cancellation scheduled for the end of the current billing period."
      );
    } catch (requestError) {
      setActionError(
        requestError instanceof Error ? requestError.message : "Unable to cancel subscription."
      );
    } finally {
      setActiveAction(null);
    }
  }

  if (sessionContext.role !== "owner") {
    return (
      <>
        <AppSidebar />
        <section className="inbox-card">
          <div className="eyebrow">Subscription</div>
          <h1 style={{ marginTop: 0 }}>Current plan and billing state</h1>
          <div className="empty-state">
            <span className="muted">Only the account owner can access Subscription.</span>
          </div>
        </section>
        <aside className="detail-card">
          <div className="eyebrow">Billing</div>
          <p className="muted">Owner-only billing controls stay separate from operational access.</p>
        </aside>
      </>
    );
  }

  return (
    <>
      <AppSidebar />
      <section className="inbox-card">
        <div className="eyebrow">Subscription</div>
        <h1 style={{ marginTop: 0 }}>Current plan and billing state</h1>
        {error ? <p className="notice danger">{error}</p> : null}
        {actionError ? <p className="notice danger">{actionError}</p> : null}
        {actionFeedback ? <p className="notice success">{actionFeedback}</p> : null}
        {subscription ? (
          <div className="stack">
            <div className="message-log">
              <strong>Plan</strong>
              <div className="muted">{subscription.plan_code ?? "Trial"}</div>
            </div>
            <div className="message-log">
              <strong>Status</strong>
              <div className="muted">{formatStatusLabel(subscription.status)}</div>
            </div>
            <div className="message-log">
              <strong>Current period end</strong>
              <div className="muted">{formatDateLabel(subscription.current_period_end)}</div>
            </div>
            <div className="message-log">
              <strong>Trial end</strong>
              <div className="muted">{formatDateLabel(subscription.trial_ends_at)}</div>
            </div>
            {subscription.cancel_at_period_end && subscription.current_period_end ? (
              <p className="notice warning">
                Your subscription ends on {formatDateLabel(subscription.current_period_end)}.
              </p>
            ) : null}
            <div className="settings-actions">
              <button
                className="button"
                type="button"
                onClick={() => void handleManageBilling()}
                disabled={!subscription.can_manage_billing || activeAction !== null}
              >
                {activeAction === "portal" ? "Opening..." : "Manage billing"}
              </button>
              {subscription.can_cancel ? (
                <button
                  className="button-secondary"
                  type="button"
                  onClick={() => void handleCancel()}
                  disabled={activeAction !== null}
                >
                  {activeAction === "cancel" ? "Cancelling..." : "Cancel"}
                </button>
              ) : null}
            </div>
          </div>
        ) : (
          <div className="loading-card">Loading subscription...</div>
        )}
      </section>

      <aside className="detail-card">
        <div className="eyebrow">Billing</div>
        <h2 style={{ marginTop: 0 }}>Paddle controls</h2>
        <p className="muted">
          Manage billing opens the live Paddle customer portal. Cancel schedules the subscription to
          end at the close of the current billing period without deleting account data.
        </p>
      </aside>
    </>
  );
}

export default function SubscriptionPage() {
  return (
    <ProtectedPage>
      {({ sessionContext }) => <SubscriptionContent sessionContext={sessionContext} />}
    </ProtectedPage>
  );
}
