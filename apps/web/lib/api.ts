"use client";

import { useEffect, useState } from "react";
import type { SupabaseClient } from "@supabase/supabase-js";

import { getSupabaseBrowserClient } from "@/lib/supabase";

const ACCOUNT_STORAGE_KEY = "tradie.account_id";

export interface MembershipSummary {
  account_id: string;
  role: "owner" | "staff";
}

export interface SessionContext {
  token: string;
  accountId: string;
  userId: string;
  email: string | null;
  memberships: MembershipSummary[];
  role: "owner" | "staff";
}

export interface EnquiryListItem {
  id: string;
  customer_name: string;
  suburb: string;
  service_requested: string;
  status: "new" | "follow_up" | "done";
  ai_status: "pending" | "completed" | "failed";
  urgency_level?: "low" | "medium" | "high" | "emergency" | null;
  qualification_summary?: string | null;
  needs_review: boolean;
  has_failed_sms: boolean;
  has_failed_customer_sms: boolean;
  has_failed_tradie_sms: boolean;
  received_at: string;
}

export interface MessageSummary {
  id: string;
  recipient_type: "lead" | "tradie";
  status: string;
  body: string;
  created_at: string;
}

export interface TimelineEvent {
  id: string;
  event_type: string;
  created_at: string;
  payload_json?: Record<string, unknown> | null;
}

export interface LeadNoteSummary {
  id: string;
  user_id: string;
  content: string;
  created_at: string;
}

export interface EnquiryDetail extends EnquiryListItem {
  customer_phone: string;
  customer_email?: string | null;
  messages: MessageSummary[];
  timeline: TimelineEvent[];
  notes: LeadNoteSummary[];
  is_possible_duplicate: boolean;
  duplicate_of_lead_id?: string | null;
  updated_at: string;
}

export interface AccountSettings {
  id: string;
  business_name: string;
  business_type?: string | null;
  primary_phone?: string | null;
  timezone: string;
  country: string;
  business_hours_start: string;
  business_hours_end: string;
  business_hours_tz: string;
  onboarding_step: number;
  onboarding_completed_at?: string | null;
}

export interface SetupState {
  account: AccountSettings;
  connect: {
    form_token: string;
    embed_code: string;
    google_business_link: string;
  };
}

export interface TemplateSummary {
  id: string;
  template_type: string;
  content: string;
  is_active: boolean;
  locale: string;
}

export interface SubscriptionSummary {
  plan_code?: string | null;
  status?: string | null;
  trial_ends_at?: string | null;
  current_period_end?: string | null;
  cancel_at_period_end: boolean;
  can_manage_billing: boolean;
  can_cancel: boolean;
}

export interface BillingPortalResponse {
  url: string;
}

export interface ActionResponse {
  status: string;
  lead_id?: string | null;
  job_id?: string | null;
}

export interface TeamMember {
  id: string;
  user_id: string;
  email: string;
  role: "owner" | "staff";
  invited_at?: string | null;
  accepted_at?: string | null;
  joined_at?: string | null;
  is_current_user: boolean;
}

export interface TeamMembersResponse {
  data: TeamMember[];
}

export function getStoredAccountId() {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(ACCOUNT_STORAGE_KEY);
}

function setStoredAccountId(accountId: string) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(ACCOUNT_STORAGE_KEY, accountId);
}

async function getAccessToken() {
  const supabase = getSupabaseBrowserClient();
  const {
    data: { session }
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

export async function resolveSessionContext(): Promise<SessionContext | null> {
  const token = await getAccessToken();
  if (!token) {
    return null;
  }

  const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/api/me`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });

  if (!response.ok) {
    throw new Error("Unable to load session context");
  }

  const payload = (await response.json()) as {
    user_id: string;
    email?: string | null;
    memberships: MembershipSummary[];
  };
  if (!payload.memberships.length) {
    throw new Error("No account membership found for this user");
  }

  const storedAccountId = getStoredAccountId();
  const selectedMembership =
    payload.memberships.find((membership) => membership.account_id === storedAccountId) ??
    payload.memberships[0];

  setStoredAccountId(selectedMembership.account_id);
  return {
    token,
    accountId: selectedMembership.account_id,
    userId: payload.user_id,
    email: payload.email ?? null,
    memberships: payload.memberships,
    role: selectedMembership.role
  };
}

export async function apiFetch<T>(
  path: string,
  options?: {
    method?: string;
    body?: unknown;
    accountId?: string;
  }
): Promise<T> {
  const context = await resolveSessionContext();
  if (!context) {
    throw new Error("Not authenticated");
  }

  const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}${path}`, {
    method: options?.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${context.token}`,
      "X-Account-Id": options?.accountId ?? context.accountId
    },
    body: options?.body ? JSON.stringify(options.body) : undefined
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as
      | { error?: string; detail?: string }
      | null;
    throw new Error(errorBody?.detail ?? errorBody?.error ?? "Request failed");
  }

  return (await response.json()) as T;
}

export function useProtectedSession() {
  const [supabase, setSupabase] = useState<SupabaseClient | null>(null);
  const [sessionContext, setSessionContext] = useState<SessionContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    let subscription: { unsubscribe: () => void } | null = null;

    let client: SupabaseClient;
    try {
      client = getSupabaseBrowserClient();
      if (mounted) {
        setSupabase(client);
      }
    } catch (loadError) {
      if (mounted) {
        setError(loadError instanceof Error ? loadError.message : "Unknown error");
        setSessionContext(null);
        setLoading(false);
      }
      return () => {
        mounted = false;
      };
    }

    async function load() {
      try {
        const context = await resolveSessionContext();
        if (!mounted) {
          return;
        }
        setSessionContext(context);
        setError(null);
      } catch (loadError) {
        if (!mounted) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Unknown error");
        setSessionContext(null);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    void load();
    ({
      data: { subscription }
    } = client.auth.onAuthStateChange(() => {
      void load();
    }));

    return () => {
      mounted = false;
      subscription?.unsubscribe();
    };
  }, []);

  return {
    loading,
    error,
    sessionContext,
    signOut: async () => {
      const client = supabase ?? getSupabaseBrowserClient();
      await client.auth.signOut();
      window.localStorage.removeItem(ACCOUNT_STORAGE_KEY);
      window.location.href = "/login";
    }
  };
}
