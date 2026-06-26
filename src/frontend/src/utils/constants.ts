export const APP_NAME = "Legal CoPilot";
export const APP_VERSION = "2.0.0";
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export const ROUTES = {
  LOGIN: "/login",
  DASHBOARD: "/dashboard",
  CASES: "/cases",
  CASE_DETAIL: "/cases/:id",
  KNOWLEDGE: "/knowledge",
} as const;

export const CASE_STAGES = [
  { value: "intake", label: "Intake", color: "bg-gray-500" },
  { value: "fact_gathering", label: "Fact Gathering", color: "bg-blue-500" },
  { value: "research", label: "Research", color: "bg-indigo-500" },
  { value: "analysis", label: "Analysis", color: "bg-purple-500" },
  { value: "drafting", label: "Drafting", color: "bg-amber-500" },
  { value: "review", label: "Review", color: "bg-orange-500" },
  { value: "submission", label: "Submission", color: "bg-emerald-500" },
  { value: "complete", label: "Complete", color: "bg-green-600" },
] as const;

export const PRACTICE_AREAS = [
  { value: "general", label: "General" },
  { value: "contract", label: "Contract Law" },
  { value: "employment", label: "Employment Law" },
  { value: "family", label: "Family Law" },
  { value: "criminal", label: "Criminal Law" },
  { value: "property", label: "Property Law" },
  { value: "arbitration", label: "Arbitration" },
  { value: "corporate", label: "Corporate Law" },
  { value: "insolvency", label: "Insolvency" },
  { value: "ip", label: "Intellectual Property" },
  { value: "tort", label: "Tort Law" },
  { value: "probate", label: "Probate & Succession" },
] as const;

export const CASE_STATUSES = [
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In Progress" },
  { value: "pending_review", label: "Pending Review" },
  { value: "under_review", label: "Under Review" },
  { value: "closed", label: "Closed" },
  { value: "archived", label: "Archived" },
] as const;

export const FILE_TYPES = [
  { value: "pleading", label: "Pleading" },
  { value: "affidavit", label: "Affidavit" },
  { value: "exhibit", label: "Exhibit" },
  { value: "correspondence", label: "Correspondence" },
  { value: "submission", label: "Submission" },
  { value: "judgment", label: "Judgment" },
  { value: "contract", label: "Contract" },
  { value: "memo", label: "Memo" },
  { value: "draft", label: "Draft" },
  { value: "other", label: "Other" },
] as const;

export const CONVERSATION_TYPES = [
  { value: "legal_research", label: "Legal Research" },
  { value: "document_drafting", label: "Document Drafting" },
  { value: "case_analysis", label: "Case Analysis" },
  { value: "general", label: "General" },
] as const;

export const DRAFT_TYPES = [
  { value: "submission", label: "Written Submissions" },
  { value: "affidavit", label: "Affidavit" },
  { value: "application", label: "Application" },
  { value: "notice", label: "Notice" },
  { value: "letter_of_demand", label: "Letter of Demand" },
  { value: "advice_note", label: "Advice Note" },
  { value: "case_memo", label: "Case Memorandum" },
  { value: "contract", label: "Contract" },
  { value: "bail_application", label: "Bail Application", practiceArea: "criminal" },
  { value: "mitigation_plea", label: "Mitigation Plea", practiceArea: "criminal" },
  { value: "representations_to_agc", label: "Representations to AGC", practiceArea: "criminal" },
  { value: "parenting_plan", label: "Parenting Plan", practiceArea: "family" },
  { value: "statement_of_particulars", label: "Statement of Particulars", practiceArea: "family" },
  { value: "cease_and_desist", label: "Cease & Desist", practiceArea: "ip" },
  { value: "appeal_petition", label: "Appeal Petition" },
] as const;

export const MAX_MESSAGE_LENGTH = 50000;

export const JURISDICTIONS = [
  { value: "SG", label: "Singapore" },
  { value: "UK", label: "United Kingdom" },
  { value: "AU", label: "Australia" },
  { value: "MY", label: "Malaysia" },
  { value: "HK", label: "Hong Kong" },
  { value: "IN", label: "India" },
  { value: "US", label: "United States" },
  { value: "CA", label: "Canada" },
  { value: "NZ", label: "New Zealand" },
  { value: "PH", label: "Philippines" },
] as const;
