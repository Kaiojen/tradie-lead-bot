export type EnquiryStatus = "new" | "follow_up" | "done";
export type AIStatus = "pending" | "completed" | "failed";
export type UrgencyLevel = "low" | "medium" | "high" | "emergency";
export type MessageStatus =
  | "queued"
  | "sent_to_provider"
  | "delivered"
  | "failed"
  | "undelivered";

export interface EnquiryListItem {
  id: string;
  customerName: string;
  suburb: string;
  serviceRequested: string;
  status: EnquiryStatus;
  aiStatus: AIStatus;
  urgencyLevel?: UrgencyLevel;
  qualificationSummary?: string;
  needsReview: boolean;
  hasFailedSms: boolean;
  hasFailedCustomerSms: boolean;
  hasFailedTradieSms: boolean;
  receivedAt: string;
}
