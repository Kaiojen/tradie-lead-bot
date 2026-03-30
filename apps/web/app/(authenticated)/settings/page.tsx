"use client";

import { useEffect, useState } from "react";

import { AppSidebar } from "@/components/app-sidebar";
import { ProtectedPage } from "@/components/protected-page";
import {
  apiFetch,
  type AccountSettings,
  type ActionResponse,
  type SessionContext,
  type SetupState,
  type TeamMember,
  type TeamMembersResponse
} from "@/lib/api";

type SettingsTab = "business" | "team" | "integrations";

function formatDateLabel(value?: string | null) {
  if (!value) {
    return "Pending";
  }
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

function SettingsContent({ sessionContext }: { sessionContext: SessionContext }) {
  const [activeTab, setActiveTab] = useState<SettingsTab>("business");
  const [account, setAccount] = useState<AccountSettings | null>(null);
  const [setupState, setSetupState] = useState<SetupState | null>(null);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [pageError, setPageError] = useState<string | null>(null);
  const [businessFeedback, setBusinessFeedback] = useState<string | null>(null);
  const [teamFeedback, setTeamFeedback] = useState<string | null>(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [savingBusiness, setSavingBusiness] = useState(false);
  const [inviting, setInviting] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [copiedField, setCopiedField] = useState<"embed" | "google" | null>(null);

  useEffect(() => {
    let mounted = true;

    async function loadPage() {
      try {
        const [accountPayload, setupPayload, teamPayload] = await Promise.all([
          apiFetch<AccountSettings>("/api/account"),
          apiFetch<SetupState>("/api/setup"),
          apiFetch<TeamMembersResponse>("/api/team")
        ]);
        if (!mounted) {
          return;
        }
        setAccount(accountPayload);
        setSetupState(setupPayload);
        setTeamMembers(teamPayload.data);
        setPageError(null);
      } catch (loadError) {
        if (!mounted) {
          return;
        }
        setPageError(loadError instanceof Error ? loadError.message : "Unable to load settings.");
      }
    }

    void loadPage();
    return () => {
      mounted = false;
    };
  }, []);

  async function refreshTeam() {
    const payload = await apiFetch<TeamMembersResponse>("/api/team");
    setTeamMembers(payload.data);
  }

  async function saveBusiness() {
    if (!account) {
      return;
    }

    setSavingBusiness(true);
    setBusinessFeedback(null);
    setPageError(null);

    try {
      const updated = await apiFetch<AccountSettings>("/api/account", {
        method: "PATCH",
        body: {
          business_name: account.business_name,
          business_type: account.business_type,
          primary_phone: account.primary_phone,
          timezone: account.timezone,
          business_hours_start: account.business_hours_start,
          business_hours_end: account.business_hours_end,
          business_hours_tz: account.business_hours_tz
        }
      });
      setAccount(updated);
      setBusinessFeedback("Settings saved.");
    } catch (saveError) {
      setPageError(saveError instanceof Error ? saveError.message : "Unable to save settings.");
    } finally {
      setSavingBusiness(false);
    }
  }

  async function inviteTeamMember() {
    if (!inviteEmail.trim()) {
      setTeamFeedback("Enter an email address first.");
      return;
    }

    setInviting(true);
    setTeamFeedback(null);
    setPageError(null);

    try {
      await apiFetch<ActionResponse>("/api/team/invite", {
        method: "POST",
        body: { email: inviteEmail.trim() }
      });
      await refreshTeam();
      setInviteEmail("");
      setTeamFeedback("Invite sent. The team member can use the magic link email to sign in.");
    } catch (inviteError) {
      setTeamFeedback(
        inviteError instanceof Error ? inviteError.message : "Unable to send invite."
      );
    } finally {
      setInviting(false);
    }
  }

  async function removeTeamMember(membershipId: string) {
    setRemovingId(membershipId);
    setTeamFeedback(null);
    setPageError(null);

    try {
      await apiFetch<ActionResponse>(`/api/team/${membershipId}`, {
        method: "DELETE"
      });
      await refreshTeam();
      setTeamFeedback("Team member removed.");
    } catch (removeError) {
      setTeamFeedback(
        removeError instanceof Error ? removeError.message : "Unable to remove team member."
      );
    } finally {
      setRemovingId(null);
    }
  }

  async function copyValue(field: "embed" | "google", value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedField(field);
      setTimeout(() => setCopiedField((current) => (current === field ? null : current)), 1800);
    } catch {
      setPageError("Clipboard access is unavailable in this browser.");
    }
  }

  if (!account || !setupState) {
    return (
      <>
        <AppSidebar />
        <section className="inbox-card">
          <div className="eyebrow">Settings</div>
          <div className="loading-card">Loading settings...</div>
        </section>
        <aside className="detail-card">
          <div className="eyebrow">Workspace</div>
          <p className="muted">Loading account, team and integration settings.</p>
        </aside>
      </>
    );
  }

  return (
    <>
      <AppSidebar />
      <section className="inbox-card">
        <div className="eyebrow">Settings</div>
        <h1 style={{ marginTop: 0 }}>Business profile, team and integrations</h1>
        {pageError ? <p className="notice danger">{pageError}</p> : null}
        <div className="filter-row">
          <button
            className={`pill${activeTab === "business" ? " active" : ""}`}
            type="button"
            onClick={() => setActiveTab("business")}
          >
            Business
          </button>
          <button
            className={`pill${activeTab === "team" ? " active" : ""}`}
            type="button"
            onClick={() => setActiveTab("team")}
          >
            Team
          </button>
          <button
            className={`pill${activeTab === "integrations" ? " active" : ""}`}
            type="button"
            onClick={() => setActiveTab("integrations")}
          >
            Integrations
          </button>
        </div>

        {activeTab === "business" ? (
          <div className="settings-panel">
            {businessFeedback ? <p className="notice">{businessFeedback}</p> : null}
            <div className="form-grid">
              <div className="field">
                <label htmlFor="business-name">Business name</label>
                <input
                  id="business-name"
                  value={account.business_name}
                  onChange={(event) => setAccount({ ...account, business_name: event.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor="business-type">Trade type</label>
                <input
                  id="business-type"
                  value={account.business_type ?? ""}
                  onChange={(event) => setAccount({ ...account, business_type: event.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor="primary-phone">Alert number</label>
                <input
                  id="primary-phone"
                  value={account.primary_phone ?? ""}
                  onChange={(event) => setAccount({ ...account, primary_phone: event.target.value })}
                />
              </div>
              <div className="two-column">
                <div className="field">
                  <label htmlFor="hours-start">Business hours start</label>
                  <input
                    id="hours-start"
                    type="time"
                    value={account.business_hours_start}
                    onChange={(event) =>
                      setAccount({ ...account, business_hours_start: event.target.value })
                    }
                  />
                </div>
                <div className="field">
                  <label htmlFor="hours-end">Business hours end</label>
                  <input
                    id="hours-end"
                    type="time"
                    value={account.business_hours_end}
                    onChange={(event) =>
                      setAccount({ ...account, business_hours_end: event.target.value })
                    }
                  />
                </div>
              </div>
              <div className="field">
                <label htmlFor="hours-tz">Business hours timezone</label>
                <input
                  id="hours-tz"
                  value={account.business_hours_tz}
                  onChange={(event) =>
                    setAccount({ ...account, business_hours_tz: event.target.value })
                  }
                />
              </div>
              <div className="settings-actions">
                <button
                  className="button"
                  type="button"
                  onClick={() => void saveBusiness()}
                  disabled={savingBusiness}
                >
                  {savingBusiness ? "Saving..." : "Save"}
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {activeTab === "team" ? (
          <div className="settings-panel">
            {teamFeedback ? <p className="notice">{teamFeedback}</p> : null}
            {sessionContext.role === "owner" ? (
              <div className="settings-section">
                <div className="field">
                  <label htmlFor="team-email">Invite team member</label>
                  <input
                    id="team-email"
                    type="email"
                    placeholder="teammate@business.com.au"
                    value={inviteEmail}
                    onChange={(event) => setInviteEmail(event.target.value)}
                  />
                </div>
                <div className="settings-actions">
                  <button
                    className="button"
                    type="button"
                    onClick={() => void inviteTeamMember()}
                    disabled={inviting}
                  >
                    {inviting ? "Sending..." : "Send invite"}
                  </button>
                </div>
              </div>
            ) : (
              <p className="notice warning">Only the account owner can invite or remove members.</p>
            )}

            <div className="team-list">
              {teamMembers.map((member) => (
                <div className="team-row" key={member.id}>
                  <div className="team-member-copy">
                    <strong>{member.email}</strong>
                    <div className="muted">
                      {member.accepted_at
                        ? `Joined ${formatDateLabel(member.joined_at)}`
                        : `Invite sent ${formatDateLabel(member.invited_at)}`}
                    </div>
                  </div>
                  <div className="team-member-actions">
                    <span className={`tag${member.role === "owner" ? " success" : ""}`}>
                      {member.role}
                    </span>
                    {!member.accepted_at ? <span className="tag">Pending</span> : null}
                    {sessionContext.role === "owner" && !member.is_current_user ? (
                      <button
                        className="button-secondary inline-button"
                        type="button"
                        onClick={() => void removeTeamMember(member.id)}
                        disabled={removingId === member.id}
                      >
                        {removingId === member.id ? "Removing..." : "Remove"}
                      </button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {activeTab === "integrations" ? (
          <div className="settings-panel">
            <div className="settings-section">
              <div className="field">
                <label htmlFor="embed-code">Embed code</label>
                <textarea id="embed-code" readOnly value={setupState.connect.embed_code} rows={4} />
              </div>
              <div className="settings-actions">
                <button
                  className="button-secondary"
                  type="button"
                  onClick={() => void copyValue("embed", setupState.connect.embed_code)}
                >
                  {copiedField === "embed" ? "Copied!" : "Copy"}
                </button>
              </div>
            </div>

            <div className="settings-section">
              <div className="field">
                <label htmlFor="google-link">Google Business link</label>
                <input id="google-link" readOnly value={setupState.connect.google_business_link} />
              </div>
              <div className="settings-actions">
                <button
                  className="button-secondary"
                  type="button"
                  onClick={() => void copyValue("google", setupState.connect.google_business_link)}
                >
                  {copiedField === "google" ? "Copied!" : "Copy"}
                </button>
              </div>
            </div>

            <div className="guide-grid">
              <div className="guide-card">
                <strong>WordPress</strong>
                <p className="muted">Paste the script tag into a Custom HTML block or footer injection.</p>
              </div>
              <div className="guide-card">
                <strong>Squarespace</strong>
                <p className="muted">Drop the embed into Code Injection or a page-level code block.</p>
              </div>
              <div className="guide-card">
                <strong>Wix</strong>
                <p className="muted">Use the Custom Code area and publish once to push the form live.</p>
              </div>
            </div>
          </div>
        ) : null}
      </section>

      <aside className="detail-card">
        <div className="eyebrow">Workspace</div>
        {activeTab === "business" ? (
          <>
            <h2 style={{ marginTop: 0 }}>Business hours</h2>
            <p className="muted">
              These hours define the after-hours Auto-Reply context and the contact window shown
              across the app.
            </p>
          </>
        ) : null}
        {activeTab === "team" ? (
          <>
            <h2 style={{ marginTop: 0 }}>Team access</h2>
            <p className="muted">
              Invites are sent by Supabase Auth. New members can sign in with the emailed magic link
              and land directly in the shared Inbox.
            </p>
          </>
        ) : null}
        {activeTab === "integrations" ? (
          <>
            <h2 style={{ marginTop: 0 }}>Embed and lead links</h2>
            <p className="muted">
              The embed code and Google Business link reuse the same form token generated during
              setup, so your onboarding and ongoing settings stay in sync.
            </p>
          </>
        ) : null}
      </aside>
    </>
  );
}

export default function SettingsPage() {
  return (
    <ProtectedPage>
      {({ sessionContext }) => <SettingsContent sessionContext={sessionContext} />}
    </ProtectedPage>
  );
}
