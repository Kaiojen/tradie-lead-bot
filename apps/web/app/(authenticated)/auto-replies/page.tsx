"use client";

import { useEffect, useState } from "react";

import { AppSidebar } from "@/components/app-sidebar";
import { ProtectedPage } from "@/components/protected-page";
import { apiFetch, type TemplateSummary } from "@/lib/api";

export default function AutoRepliesPage() {
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [testPhone, setTestPhone] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    void apiFetch<TemplateSummary[]>("/api/templates").then((payload) => {
      setTemplates(payload);
      if (payload[0]) {
        setSelectedId(payload[0].id);
        setContent(payload[0].content);
      }
    });
  }, []);

  async function saveTemplate() {
    if (!selectedId) {
      return;
    }
    const currentTemplate = templates.find((template) => template.id === selectedId);
    const nextIsActive = currentTemplate?.is_active ?? true;
    const updated = await apiFetch<TemplateSummary>(`/api/templates/${selectedId}`, {
      method: "PATCH",
      body: { content, is_active: nextIsActive }
    });
    setTemplates((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    setContent(updated.content);
    setFeedback("Auto-Reply saved.");
  }

  async function toggleTemplateActive(template: TemplateSummary, nextIsActive: boolean) {
    const updated = await apiFetch<TemplateSummary>(`/api/templates/${template.id}`, {
      method: "PATCH",
      body: { content: template.content, is_active: nextIsActive }
    });
    setTemplates((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    if (selectedId === template.id) {
      setContent(updated.content);
    }
    setFeedback(nextIsActive ? "Template turned on." : "Template turned off.");
  }

  async function sendTest() {
    if (!selectedId || !testPhone) {
      return;
    }
    await apiFetch(`/api/templates/${selectedId}/send-test`, {
      method: "POST",
      body: { phone_number: testPhone }
    });
    setFeedback("Test SMS queued.");
  }

  return (
    <ProtectedPage>
      {() => (
        <>
          <AppSidebar />
          <section className="inbox-card">
            <div className="eyebrow">Auto-Replies</div>
            <h1 style={{ marginTop: 0 }}>Your Auto-Replies</h1>
            {feedback ? <p className="notice">{feedback}</p> : null}
            <div className="two-column">
              <div className="stack">
                {templates.map((template) => (
                  <div
                    key={template.id}
                    className={`list-row${selectedId === template.id ? " selected" : ""}`}
                  >
                    <button
                      type="button"
                      className="list-select"
                      onClick={() => {
                        setSelectedId(template.id);
                        setContent(template.content);
                      }}
                    >
                      <div className="list-summary">
                        <div className="list-title-row">
                          <div>
                            <strong>{template.template_type}</strong>
                            <div className="muted">{template.locale}</div>
                          </div>
                        </div>
                      </div>
                    </button>
                    <div className="template-controls">
                      <span className={`tag${template.is_active ? " success" : ""}`}>
                        {template.is_active ? "On" : "Off"}
                      </span>
                      <button
                        className="button-secondary inline-button"
                        type="button"
                        onClick={() => void toggleTemplateActive(template, !template.is_active)}
                      >
                        {template.is_active ? "Turn off" : "Turn on"}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="stack">
                <textarea value={content} onChange={(event) => setContent(event.target.value)} />
                <div className="field">
                  <label htmlFor="test-phone">Send Test SMS</label>
                  <input
                    id="test-phone"
                    value={testPhone}
                    onChange={(event) => setTestPhone(event.target.value)}
                    placeholder="0412 345 678"
                  />
                </div>
                <div className="filter-row">
                  <button className="button" type="button" onClick={() => void saveTemplate()}>
                    Save
                  </button>
                  <button className="button-secondary" type="button" onClick={() => void sendTest()}>
                    Send Test SMS
                  </button>
                </div>
              </div>
            </div>
          </section>

          <aside className="detail-card">
            <div className="eyebrow">Rules</div>
            <p className="muted">
              Use only [Customer Name] and [Business Name]. Keep SMS copy short and direct.
            </p>
          </aside>
        </>
      )}
    </ProtectedPage>
  );
}
