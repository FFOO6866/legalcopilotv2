export interface KnowledgeEntry {
  citation: string;
  case_name: string;
  court: string;
  jurisdiction: string;
  year: number;
  summary: string;
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
  skills: string[];
  knowledge_sources: string[];
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
