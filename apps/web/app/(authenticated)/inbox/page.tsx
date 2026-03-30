"use client";

import { useEffect, useState } from "react";

import { AppSidebar } from "@/components/app-sidebar";
import { ProtectedPage } from "@/components/protected-page";
import {
  apiFetch,
  type EnquiryDetail,
  type EnquiryListItem,
  type LeadNoteSummary,
  type SessionContext
} from "@/lib/api";

const FILTERS = [
  { label: "New", value: "new" },
  { label: "Follow Up", value: "follow_up" },
  { label: "Done", value: "done" }
] as const;

const FAILED_SMS_STATUSES = new Set(["failed", "undelivered"]);

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("en-AU");
}

function formatMessageStatus(status: string) {
  return status.replaceAll("_", " ");
}

function InboxContent({ sessionContext }: { sessionContext: SessionContext }) {
  const [activeFilter, setActiveFilter] = useState<(typeof FILTERS)[number]["value"]>("new");
  const [enquiries, setEnquiries] = useState<EnquiryListItem[]>([]);
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [selectedEnquiry, setSelectedEnquiry] = useState<EnquiryDetail | null>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);

  async function loadEnquiries(filterValue: string) {
    const payload = await apiFetch<{ data: EnquiryListItem[] }>(
      `/api/enquiries?status=${filterValue}&page=1&limit=20`
    );
    setEnquiries(payload.data);
    if (!payload.data.length) {
      setSelectedLeadId(null);
      setSelectedEnquiry(null);
      return;
    }

    setSelectedLeadId((currentLeadId) => {
      if (currentLeadId && payload.data.some((enquiry) => enquiry.id === currentLeadId)) {
        return currentLeadId;
      }
      return payload.data[0].id;
    });
  }

  async function loadDetail(leadId: string) {
    const detail = await apiFetch<EnquiryDetail>(`/api/enquiries/${leadId}`);
    setSelectedEnquiry(detail);
  }

  async function retryLead(leadId: string) {
    await apiFetch(`/api/enquiries/${leadId}/retry`, {
      method: "POST"
    });
    setFeedback("Retry queued.");
    await loadEnquiries(activeFilter);
    if (selectedLeadId === leadId) {
      await loadDetail(leadId);
    }
  }

  useEffect(() => {
    void loadEnquiries(activeFilter);
  }, [activeFilter]);

  useEffect(() => {
    if (!selectedLeadId) {
      return;
    }
    void loadDetail(selectedLeadId);
  }, [selectedLeadId]);

  async function updateStatus(status: "new" | "follow_up" | "done") {
    if (!selectedEnquiry) {
      return;
    }
    await apiFetch(`/api/enquiries/${selectedEnquiry.id}/status`, {
      method: "PATCH",
      body: { status }
    });
    setFeedback(`Enquiry moved to ${status}.`);
    await loadEnquiries(activeFilter);
    await loadDetail(selectedEnquiry.id);
  }

  async function reprocessSelectedLead() {
    if (!selectedEnquiry) {
      return;
    }
    await apiFetch(`/api/enquiries/${selectedEnquiry.id}/reprocess`, {
      method: "POST"
    });
    setFeedback("Reprocess queued.");
    await loadDetail(selectedEnquiry.id);
  }

  async function createNote() {
    if (!selectedEnquiry || !noteDraft.trim()) {
      return;
    }
    const note = await apiFetch<LeadNoteSummary>(`/api/enquiries/${selectedEnquiry.id}/notes`, {
      method: "POST",
      body: { content: noteDraft }
    });
    setSelectedEnquiry({
      ...selectedEnquiry,
      notes: [note, ...selectedEnquiry.notes]
    });
    setNoteDraft("");
    setFeedback("Note saved.");
  }
  const tradieFailureEnquiry =
    enquiries.find((enquiry) => enquiry.has_failed_tradie_sms) ?? selectedEnquiry;

  return (
    <>
      <AppSidebar />

      <section className="inbox-card">
        <div className="inbox-header">
          <div>
            <div className="eyebrow">Inbox</div>
            <h1 style={{ margin: 0, fontSize: "2.6rem", letterSpacing: "-0.05em" }}>
              New enquiries stay visible.
            </h1>
          </div>
          <span className="tag success">{sessionContext.role === "owner" ? "Owner" : "Staff"}</span>
        </div>

        <div className="banner-stack">
          {tradieFailureEnquiry?.has_failed_tradie_sms ? (
            <p className="notice warning">
              Tradie SMS failed for {tradieFailureEnquiry.customer_name}. Retry inline to resend the
              job alert.
            </p>
          ) : null}
          {feedback ? <p className="notice">{feedback}</p> : null}
        </div>

        <div className="filter-row">
          {FILTERS.map((filterItem) => (
            <button
              key={filterItem.value}
              className={`pill${activeFilter === filterItem.value ? " active" : ""}`}
              type="button"
              onClick={() => setActiveFilter(filterItem.value)}
            >
              {filterItem.label}
            </button>
          ))}
        </div>

        {enquiries.length ? (
          <div className="stack">
            {enquiries.map((enquiry) => (
              <div
                key={enquiry.id}
                className={`list-row${selectedLeadId === enquiry.id ? " selected" : ""}`}
              >
                <button
                  type="button"
                  className="list-select"
                  onClick={() => setSelectedLeadId(enquiry.id)}
                >
                  <div className="list-summary">
                    <div className="list-title-row">
                      <strong>{enquiry.customer_name}</strong>
                      <div className="list-badges">
                        {enquiry.needs_review ? <span className="tag">Needs review</span> : null}
                        {enquiry.has_failed_sms ? <span className="tag danger">SMS failed</span> : null}
                      </div>
                    </div>
                    <div className="muted">
                      {enquiry.service_requested} · {enquiry.suburb}
                    </div>
                  </div>
                </button>

                <div className="list-meta">
                  {enquiry.urgency_level ? <span className="tag">{enquiry.urgency_level}</span> : null}
                  <span className="muted">{formatDateTime(enquiry.received_at)}</span>
                  {enquiry.has_failed_sms ? (
                    <button
                      className="button-secondary inline-button"
                      type="button"
                      onClick={() => void retryLead(enquiry.id)}
                    >
                      Retry SMS
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <div className="stack">
              <strong style={{ fontSize: "1.25rem" }}>You're all caught up.</strong>
              <span className="muted">New enquiries will appear here.</span>
            </div>
          </div>
        )}
      </section>

      <aside className="detail-card">
        {selectedEnquiry ? (
          <>
            <div className="detail-header">
              <div>
                <div className="eyebrow">Enquiry Details</div>
                <h2 style={{ marginTop: 0 }}>{selectedEnquiry.customer_name}</h2>
                <p className="muted">
                  {selectedEnquiry.customer_phone} · {selectedEnquiry.suburb}
                </p>
              </div>
              <div className="detail-badges">
                {selectedEnquiry.needs_review ? <span className="tag">Needs review</span> : null}
                {selectedEnquiry.has_failed_sms ? <span className="tag danger">SMS failed</span> : null}
              </div>
            </div>

            {selectedEnquiry.needs_review ? (
              <p className="notice warning">
                AI qualification failed. Review the raw lead details and reprocess when ready.
              </p>
            ) : null}
            {selectedEnquiry.has_failed_tradie_sms ? (
              <p className="notice warning">
                The SMS alert to the tradie failed. Retry failed SMS now so the lead stays actionable.
              </p>
            ) : null}

            <p>{selectedEnquiry.qualification_summary ?? selectedEnquiry.service_requested}</p>
            <div className="stack" style={{ marginBottom: "18px" }}>
              <button className="button" type="button" onClick={() => void updateStatus("done")}>
                Mark as Done
              </button>
              <button
                className="button-secondary"
                type="button"
                onClick={() => void updateStatus("follow_up")}
              >
                Move to Follow Up
              </button>
              <button
                className="button-secondary"
                type="button"
                onClick={() => void retryLead(selectedEnquiry.id)}
              >
                {selectedEnquiry.has_failed_sms ? "Retry failed SMS" : "Retry"}
              </button>
              {sessionContext.role === "owner" ? (
                <button className="button-secondary" type="button" onClick={() => void reprocessSelectedLead()}>
                  Reprocess
                </button>
              ) : null}
            </div>

            <div className="stack">
              <strong>Timeline</strong>
              <div className="timeline">
                {selectedEnquiry.timeline.map((eventItem) => (
                  <div key={eventItem.id} className="timeline-item">
                    <strong>{eventItem.event_type}</strong>
                    <div className="muted">{formatDateTime(eventItem.created_at)}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="stack" style={{ marginTop: "18px" }}>
              <strong>SMS log</strong>
              {selectedEnquiry.messages.map((message) => (
                <div key={message.id} className="message-log">
                  <div className="message-log-header">
                    <strong>{message.recipient_type === "lead" ? "Auto-Reply" : "New Job Alert"}</strong>
                    {FAILED_SMS_STATUSES.has(message.status) ? (
                      <span className="tag danger">Failed</span>
                    ) : null}
                  </div>
                  <div className="muted">{formatMessageStatus(message.status)}</div>
                  <p>{message.body}</p>
                </div>
              ))}
            </div>

            <div className="stack" style={{ marginTop: "18px" }}>
              <strong>Notes</strong>
              <textarea
                placeholder="Add a note for the team"
                value={noteDraft}
                onChange={(event) => setNoteDraft(event.target.value)}
              />
              <button className="button-secondary" type="button" onClick={() => void createNote()}>
                Save Note
              </button>
              {selectedEnquiry.notes.map((note) => (
                <div key={note.id} className="message-log">
                  <p>{note.content}</p>
                  <div className="muted">{formatDateTime(note.created_at)}</div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="empty-state">
            <span className="muted">Select an enquiry to view the timeline.</span>
          </div>
        )}
      </aside>
    </>
  );
}

export default function InboxPage() {
  return (
    <ProtectedPage>
      {({ sessionContext }) => <InboxContent sessionContext={sessionContext} />}
    </ProtectedPage>
  );
}
