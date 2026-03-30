"use client";

import { useEffect } from "react";
import type { ReactNode } from "react";
import { useRouter } from "next/navigation";

import { AppSidebar } from "@/components/app-sidebar";
import { type SessionContext, useProtectedSession } from "@/lib/api";

interface ProtectedSessionContext {
  loading: false;
  error: string | null;
  sessionContext: SessionContext;
  signOut: () => Promise<void>;
}

export function ProtectedPage({
  children
}: {
  children: (context: ProtectedSessionContext) => ReactNode;
}) {
  const context = useProtectedSession();
  const router = useRouter();

  useEffect(() => {
    if (!context.loading && !context.sessionContext) {
      router.replace("/login");
    }
  }, [context.loading, context.sessionContext, router]);

  if (context.loading) {
    return (
      <main className="app-layout">
        <AppSidebar />
        <section className="inbox-card loading-card">Loading your Inbox...</section>
        <aside className="detail-card loading-card">Checking account access...</aside>
      </main>
    );
  }

  if (!context.sessionContext) {
    return null;
  }

  return (
    <main className="app-layout">
      {children({
        loading: false,
        error: context.error,
        sessionContext: context.sessionContext,
        signOut: context.signOut
      })}
    </main>
  );
}
