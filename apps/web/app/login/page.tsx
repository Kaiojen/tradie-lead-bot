"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { SupabaseClient } from "@supabase/supabase-js";

import { MarketingNav } from "@/components/marketing-nav";
import { getSupabaseBrowserClient } from "@/lib/supabase";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [loginMethod, setLoginMethod] = useState<"password" | "magic-link">("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [supabase, setSupabase] = useState<SupabaseClient | null>(null);

  useEffect(() => {
    try {
      const client = getSupabaseBrowserClient();
      setSupabase(client);
      void client.auth.getSession().then(({ data }) => {
        if (data.session) {
          router.replace("/inbox");
        }
      });
    } catch (loadError) {
      setStatus(loadError instanceof Error ? loadError.message : "Authentication is unavailable");
    }
  }, [router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) {
      setStatus("Supabase environment variables are missing");
      return;
    }
    setLoading(true);
    setStatus(null);

    try {
      if (mode === "login") {
        if (loginMethod === "magic-link") {
          const redirectTo =
            typeof window !== "undefined" ? `${window.location.origin}/inbox` : undefined;
          const { error } = await supabase.auth.signInWithOtp({
            email,
            options: {
              emailRedirectTo: redirectTo
            }
          });
          if (error) {
            throw error;
          }
          setStatus("Magic link sent. Check your email to finish signing in.");
          return;
        }

        const { error } = await supabase.auth.signInWithPassword({
          email,
          password
        });
        if (error) {
          throw error;
        }
        router.push("/inbox");
        return;
      }

      const { error } = await supabase.auth.signUp({
        email,
        password
      });
      if (error) {
        throw error;
      }
      setStatus("Account created. Continue to Setup once your session is active.");
      router.push("/setup/1");
    } catch (submitError) {
      setStatus(submitError instanceof Error ? submitError.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <MarketingNav />
      <main className="page-shell auth-layout">
        <section className="section-card">
          <div className="eyebrow">Login / Sign Up</div>
          <h1 style={{ marginTop: 0, fontSize: "3rem", letterSpacing: "-0.05em" }}>
            Get into your Inbox quickly.
          </h1>
          <p className="lead">
            Sign up with email and continue into Setup. Existing users go straight back
            to the Inbox.
          </p>
          <div className="filter-row">
            <button
              className={`pill${mode === "login" ? " active" : ""}`}
              type="button"
              onClick={() => setMode("login")}
            >
              Login
            </button>
            <button
              className={`pill${mode === "signup" ? " active" : ""}`}
              type="button"
              onClick={() => {
                setMode("signup");
                setLoginMethod("password");
              }}
            >
              Sign Up
            </button>
          </div>
          <p className="muted">
            Choose password login or a passwordless magic link. Sign up still creates the account
            with email and password before Setup.
          </p>
        </section>

        <section className="auth-card">
          <form className="form-grid" onSubmit={handleSubmit}>
            {mode === "login" ? (
              <div className="filter-row" style={{ marginTop: 0 }}>
                <button
                  className={`pill${loginMethod === "password" ? " active" : ""}`}
                  type="button"
                  onClick={() => setLoginMethod("password")}
                >
                  Password
                </button>
                <button
                  className={`pill${loginMethod === "magic-link" ? " active" : ""}`}
                  type="button"
                  onClick={() => setLoginMethod("magic-link")}
                >
                  Magic link
                </button>
              </div>
            ) : null}
            <div className="field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                placeholder="you@business.com.au"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>
            {mode === "signup" || loginMethod === "password" ? (
              <div className="field">
                <label htmlFor="password">Password</label>
                <input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </div>
            ) : null}
            <button className="button" type="submit" disabled={loading}>
              {loading
                ? "Working..."
                : mode === "signup"
                  ? "Create account"
                  : loginMethod === "magic-link"
                    ? "Send magic link"
                    : "Login"}
            </button>
            <Link href="/pricing" className="button-secondary">
              View pricing
            </Link>
            {status ? <p className="notice">{status}</p> : null}
          </form>
        </section>
      </main>
    </>
  );
}
