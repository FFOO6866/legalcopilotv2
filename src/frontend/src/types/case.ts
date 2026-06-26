export type PracticeArea =
  | "general"
  | "contract"
  | "employment"
  | "family"
  | "criminal"
  | "property"
  | "arbitration"
  | "corporate"
  | "insolvency"
  | "ip"
  | "tort"
  | "probate";

export type CaseStatus = "open" | "in_progress" | "pending_review" | "under_review" | "closed" | "archived";

export type CaseStage =
  | "intake"
  | "fact_gathering"
  | "research"
  | "analysis"
  | "drafting"
  | "review"
  | "submission"
  | "complete";

export type FileType =
  | "pleading"
  | "affidavit"
  | "exhibit"
  | "correspondence"
  | "submission"
  | "judgment"
  | "contract"
  | "memo"
  | "draft"
  | "other";

export interface Case {
  id: string;
  firm_id: string;
  title: string;
  practice_area: PracticeArea;
  case_type: string;
  status: CaseStatus;
  stage: CaseStage;
  priority: string;
  client_name?: string;
  client_reference?: string;
  opposing_party?: string;
  court?: string;
  case_number?: string;
  description?: string;
  assigned_user_id?: string;
  created_by_id: string;
  filing_date?: string;
  tags: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Document {
  id: string;
  case_id: string;
  firm_id: string;
  filename: string;
  file_type: FileType;
  storage_url: string;
  file_size_bytes: number;
  ocr_text?: string;
  ocr_status: "pending" | "processing" | "complete" | "failed";
  classification: Record<string, unknown>;
  metadata: Record<string, unknown>;
  uploaded_by_id: string;
  created_at: string;
  updated_at: string;
}

export interface CaseEvent {
  id: string;
  case_id: string;
  firm_id: string;
  source_document_id?: string;
  event_date?: string;
  event_date_text: string;
  description: string;
  significance?: string;
  parties_involved: string[];
  event_type: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}
