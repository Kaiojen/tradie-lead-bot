"use client";

import { useEffect, useState } from "react";

import { apiFetch, type SubscriptionSummary, useProtectedSession } from "@/lib/api";

function getBillingBanner(subscription: SubscriptionSummary | null) {
  if (!subscription?.status) {
    return null;
  }

  if (subscription.status === "past_due") {
    return {
      tone: "danger" as const,
      message:
        "Payment issue detected. Fix billing before relying on the Inbox for real customers."
    };
  }

  const now = Date.now();
  const trialEndedAt = subscription.trial_ends_at
    ? new Date(subscription.trial_ends_at).getTime()
    : null;
  const currentPeriodEndsAt = subscription.current_period_end
    ? new Date(subscription.current_period_end).getTime()
    : null;

  if (subscription.status === "trialing" && trialEndedAt !== null && trialEndedAt <= now) {
    return {
      tone: "warning" as const,
      message: "Trial expired. Add billing before onboarding any real customer."
    };
  }

  if (subscription.status === "cancelled" && currentPeriodEndsAt !== null && currentPeriodEndsAt <= now) {
    return {
      tone: "warning" as const,
      message: "Billing is cancelled. Re-activate billing before relying on the Inbox."
    };
  }

  return null;
}

export function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  const { loading, sessionContext } = useProtectedSession();
  const [subscription, setSubscription] = useState<SubscriptionSummary | null>(null);

  useEffect(() => {
    if (loading || !sessionContext || sessionContext.role !== "owner") {
      setSubscription(null);
      return;
    }

    void apiFetch<SubscriptionSummary>("/api/subscription")
      .then((payload) => {
        setSubscription(payload);
      })
      .catch(() => {
        setSubscription(null);
      });
  }, [loading, sessionContext]);

  const billingBanner = sessionContext?.role === "owner" ? getBillingBanner(subscription) : null;

  return (
    <>
      {billingBanner ? (
        <div className="auth-banner-shell">
          <div className={`notice ${billingBanner.tone}`}>{billingBanner.message}</div>
        </div>
      ) : null}
      {children}
    </>
  );
}
