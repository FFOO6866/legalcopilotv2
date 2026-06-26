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
  const result = await nexusCall<{ results: KnowledgeEntry[]; total: number }>("search_cases", {
    query,
    jurisdiction,
    court,
    year_from,
    year_to,
    limit,
  });
  return result.results;
}

export async function getCitations(
  entry_id: string,
  direction?: string,
  depth?: number,
): Promise<{ citing: CitationEdge[]; cited_by: CitationEdge[] }> {
  return nexusCall<{ citing: CitationEdge[]; cited_by: CitationEdge[] }>("get_citations", {
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
  const result = await nexusCall<{ references: LegislationRef[]; total: number }>("search_legislation", {
    statute_name,
    section,
    query,
  });
  return result.references;
}

export async function legalResearch(
  query: string,
  jurisdiction?: string,
  practice_area?: string,
  include_statutes?: boolean,
  include_cases?: boolean,
): Promise<{
  cases: KnowledgeEntry[];
  statutes: LegislationRef[];
  context: string;
}> {
  return nexusCall<{
    cases: KnowledgeEntry[];
    statutes: LegislationRef[];
    context: string;
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
): Promise<SOPTemplate[]> {
  const result = await nexusCall<{ templates: SOPTemplate[]; total: number }>("list_sop_templates", {
    practice_area,
  });
  return result.templates;
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
