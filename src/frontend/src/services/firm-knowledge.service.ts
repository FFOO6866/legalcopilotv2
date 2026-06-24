import { nexusCall } from "./api";
import type { FirmKnowledge } from "@/types/knowledge";
import type { PaginatedResponse } from "@/types/common";

export async function createFirmKnowledge(
  firm_id: string,
  title: string,
  category: FirmKnowledge["category"],
  content?: string,
): Promise<FirmKnowledge> {
  return nexusCall<FirmKnowledge>("create_firm_knowledge", {
    firm_id,
    title,
    category,
    content,
  });
}

export async function listFirmKnowledge(
  firm_id: string,
  category?: FirmKnowledge["category"],
  limit?: number,
  offset?: number,
): Promise<PaginatedResponse<FirmKnowledge>> {
  return nexusCall<PaginatedResponse<FirmKnowledge>>("list_firm_knowledge", {
    firm_id,
    category,
    limit,
    offset,
  });
}

export async function getFirmKnowledge(
  knowledge_id: string,
  firm_id: string,
): Promise<FirmKnowledge> {
  return nexusCall<FirmKnowledge>("get_firm_knowledge", {
    knowledge_id,
    firm_id,
  });
}

export async function deleteFirmKnowledge(
  knowledge_id: string,
  firm_id: string,
): Promise<{ success: boolean }> {
  return nexusCall<{ success: boolean }>("delete_firm_knowledge", {
    knowledge_id,
    firm_id,
  });
}
