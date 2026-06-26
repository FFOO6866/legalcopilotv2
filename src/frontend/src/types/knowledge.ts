export interface KnowledgeEntry {
  id?: string;
  citation: string;
  case_name: string;
  court: string;
  jurisdiction: string;
  year: number;
  summary: string;
  score?: number;
  type?: string;
  treatment_warning?: string;
}

export interface CitationEdge {
  citing_id: string;
  cited_id: string;
  treatment: string;
  citing_case?: string;
  cited_case?: string;
}

export interface Judge {
  id: string;
  name: string;
  court: string;
  title: string;
  cases?: Record<string, unknown>[];
  total_cases?: number;
}

export interface LegislationRef {
  statute_name: string;
  section: string;
  subsection: string;
  chapter: string;
}

export interface SOPTemplate {
  name: string;
  practice_area: string;
  case_type: string;
  skills: Record<string, unknown>;
  knowledge_sources: Record<string, unknown>;
  quality_threshold: number;
  max_iterations: number;
}

export interface FirmKnowledge {
  id: string;
  firm_id: string;
  title: string;
  category:
    | "precedent"
    | "playbook"
    | "template"
    | "policy"
    | "training"
    | "other";
  content: string;
  qdrant_point_id: string;
  is_active: boolean;
  created_at: string;
}
