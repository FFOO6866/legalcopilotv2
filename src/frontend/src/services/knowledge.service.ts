import { nexusCall } from "./api";
import type { KnowledgeEntry, CitationEdge, Judge, LegislationRef, SOPTemplate } from "@/types/knowledge";
import type { PaginatedResponse } from "@/types/common";

export async function searchCases(
  query: string,
  jurisdiction?: string,
  court?: string,
  year_from?: number,
  year_to?: number,
  limit?: number,
): Promise<KnowledgeEntry[]> {
  return nexusCall<KnowledgeEntry[]>("search_cases", {
    query,
    jurisdiction,
    court,
    year_from,
    year_to,
    limit,
  });
}

export async function getCitations(
  entry_id: string,
  direction?: string,
  depth?: number,
): Promise<CitationEdge[]> {
  return nexusCall<CitationEdge[]>("get_citations", {
    entry_id,
    direction,
    depth,
  });
}

export async function getJudgeProfile(
  judge_id: string,
): Promise<Judge> {
  return nexusCall<Judge>("get_judge_profile", {
    judge_id,
  });
}

export async function searchLegislation(
  statute_name?: string,
  section?: string,
  query?: string,
): Promise<LegislationRef[]> {
  return nexusCall<LegislationRef[]>("search_legislation", {
    statute_name,
    section,
    query,
  });
}

export async function legalResearch(
  query: string,
  jurisdiction?: string,
  practice_area?: string,
  include_statutes?: boolean,
  include_cases?: boolean,
): Promise<{
  cases: KnowledgeEntry[];
  legislation: LegislationRef[];
  summary: string;
}> {
  return nexusCall<{
    cases: KnowledgeEntry[];
    legislation: LegislationRef[];
    summary: string;
  }>("legal_research", {
    query,
    jurisdiction,
    practice_area,
    include_statutes,
    include_cases,
  });
}

export async function getSOPTemplate(
  case_type: string,
): Promise<SOPTemplate> {
  return nexusCall<SOPTemplate>("get_sop_template", {
    case_type,
  });
}

export async function listSOPTemplates(
  practice_area?: string,
): Promise<PaginatedResponse<SOPTemplate>> {
  return nexusCall<PaginatedResponse<SOPTemplate>>("list_sop_templates", {
    practice_area,
  });
}

export async function getSOPUsageStats(
  case_type: string,
): Promise<{
  total_uses: number;
  avg_quality_score: number;
  avg_iterations: number;
}> {
  return nexusCall<{
    total_uses: number;
    avg_quality_score: number;
    avg_iterations: number;
  }>("get_sop_usage_stats", {
    case_type,
  });
}
