"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { apiFetch, type SubscriptionSummary, useProtectedSession } from "@/lib/api";

const links = [
  { href: "/inbox", label: "Inbox" },
  { href: "/auto-replies", label: "Auto-Replies" },
  { href: "/settings", label: "Settings" },
  { href: "/subscription", label: "Subscription" },
  { href: "/support", label: "Support" }
];

export function AppSidebar() {
  const pathname = usePathname();
  const { sessionContext } = useProtectedSession();
  const [subscription, setSubscription] = useState<SubscriptionSummary | null>(null);

  useEffect(() => {
    let mounted = true;

    if (!sessionContext || sessionContext.role !== "owner") {
      setSubscription(null);
      return () => {
        mounted = false;
      };
    }

    void apiFetch<SubscriptionSummary>("/api/subscription")
      .then((payload) => {
        if (mounted) {
          setSubscription(payload);
        }
      })
      .catch(() => {
        if (mounted) {
          setSubscription(null);
        }
      });

    return () => {
      mounted = false;
    };
  }, [sessionContext]);

  const trialEndsAt = subscription?.trial_ends_at ? new Date(subscription.trial_ends_at) : null;
  const trialDaysLeft =
    subscription?.status === "trialing" && trialEndsAt
      ? Math.max(0, Math.ceil((trialEndsAt.getTime() - Date.now()) / 86_400_000))
      : null;

  return (
    <aside className="sidebar">
      <div className="brand">Tradie Lead Bot</div>
      {trialDaysLeft !== null ? (
        <div className="sidebar-trial-badge">Trial: {trialDaysLeft} days left</div>
      ) : null}
      <p className="muted">Operational inbox for new enquiries.</p>
      <nav>
        {links.map((link) => (
          <Link
            key={link.label}
            href={link.href}
            className={`sidebar-link${pathname === link.href ? " active" : ""}`}
          >
            {link.label}
          </Link>
        ))}
      </nav>
      <div className="sidebar-footer">
        <Link href="/setup/1" className="button-secondary compact-button">
          Setup
        </Link>
      </div>
    </aside>
  );
}
