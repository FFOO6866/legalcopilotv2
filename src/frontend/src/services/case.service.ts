import { nexusCall } from "./api";
import type { Case, Document, FileType, PracticeArea, CaseStatus } from "@/types/case";
import type { PaginatedResponse } from "@/types/common";

export async function createCase(
  firm_id: string,
  created_by_id: string,
  title: string,
  practice_area?: PracticeArea,
  case_type?: string,
  client_name?: string,
  description?: string,
): Promise<Case> {
  return nexusCall<Case>("create_case", {
    firm_id,
    created_by_id,
    title,
    practice_area,
    case_type,
    client_name,
    description,
  });
}

export async function getCase(
  case_id: string,
  firm_id: string,
): Promise<Case> {
  return nexusCall<Case>("get_case", {
    case_id,
    firm_id,
  });
}

export async function listCases(
  firm_id: string,
  status?: CaseStatus,
  practice_area?: PracticeArea,
  limit?: number,
  offset?: number,
): Promise<PaginatedResponse<Case>> {
  return nexusCall<PaginatedResponse<Case>>("list_cases", {
    firm_id,
    status,
    practice_area,
    limit,
    offset,
  });
}

export async function updateCase(
  case_id: string,
  firm_id: string,
  fields: Partial<Case>,
): Promise<Case> {
  return nexusCall<Case>("update_case", {
    case_id,
    firm_id,
    ...fields,
  });
}

export async function uploadDocument(
  case_id: string,
  firm_id: string,
  uploaded_by_id: string,
  filename: string,
  file_type?: FileType,
  content_text?: string,
): Promise<Document> {
  return nexusCall<Document>("upload_document", {
    case_id,
    firm_id,
    uploaded_by_id,
    filename,
    file_type,
    content_text,
  });
}

export async function getDocument(
  document_id: string,
  firm_id: string,
): Promise<Document> {
  return nexusCall<Document>("get_document", {
    document_id,
    firm_id,
  });
}

export async function listDocuments(
  case_id: string,
  firm_id: string,
  file_type?: FileType,
  limit?: number,
  offset?: number,
): Promise<PaginatedResponse<Document>> {
  return nexusCall<PaginatedResponse<Document>>("list_documents", {
    case_id,
    firm_id,
    file_type,
    limit,
    offset,
  });
}
