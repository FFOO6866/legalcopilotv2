import { nexusCall } from "./api";
import type { CaseEvent, CaseStage } from "@/types/case";
import type { PaginatedResponse } from "@/types/common";

export interface StageTemplate {
  name: string;
  description: string;
  checklist: string[];
  next_actions: string[];
  ai_focus: string;
}

export interface StageInfo {
  stage: CaseStage;
  template: StageTemplate;
  next_stage: CaseStage | null;
  all_stages: CaseStage[];
}

export interface StageTransitionResult {
  case_id: string;
  previous_stage: CaseStage;
  current_stage: CaseStage;
  template: StageTemplate;
  warning?: string;
}

export async function getStageInfo(
  stage: CaseStage = "intake",
): Promise<StageInfo> {
  return nexusCall<StageInfo>("get_stage_info", { stage });
}

export async function transitionStage(
  case_id: string,
  firm_id: string,
  target_stage: CaseStage,
): Promise<StageTransitionResult> {
  return nexusCall<StageTransitionResult>("transition_stage", {
    case_id,
    firm_id,
    target_stage,
  });
}

export async function addTimelineEvent(
  case_id: string,
  firm_id: string,
  description: string,
  event_date?: string,
  event_date_text?: string,
  significance?: string,
  event_type?: string,
  source_document_id?: string,
  parties_involved?: string[],
): Promise<CaseEvent> {
  return nexusCall<CaseEvent>("add_timeline_event", {
    case_id,
    firm_id,
    description,
    event_date,
    event_date_text,
    significance,
    event_type,
    source_document_id,
    parties_involved,
  });
}

export async function listTimelineEvents(
  case_id: string,
  firm_id: string,
  significance?: string,
  limit?: number,
  offset?: number,
): Promise<PaginatedResponse<CaseEvent>> {
  const result = await nexusCall<{ events: CaseEvent[]; total: number; limit: number; offset: number }>("list_timeline_events", {
    case_id,
    firm_id,
    significance,
    limit,
    offset,
  });
  return { items: result.events, total: result.total, limit: result.limit, offset: result.offset };
}

export async function deleteTimelineEvent(
  event_id: string,
  firm_id: string,
): Promise<{ success: boolean; id: string }> {
  return nexusCall("delete_timeline_event", {
    event_id,
    firm_id,
  });
}

export async function getCaseContext(
  case_id: string,
  firm_id: string,
): Promise<Record<string, unknown>> {
  return nexusCall("get_case_context", {
    case_id,
    firm_id,
  });
}
