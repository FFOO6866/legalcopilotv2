export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiError {
  error: string;
}

export type {
  User,
  LoginRequest,
  LoginResponse,
  AuthState,
} from "./auth";

export type {
  Case,
  Document,
  PracticeArea,
  CaseStatus,
  FileType,
} from "./case";

export type {
  Conversation,
  Message,
  Source,
  QualityWarning,
  RAGFeedback,
} from "./chat";

export type {
  KnowledgeEntry,
  CitationEdge,
  Judge,
  LegislationRef,
  SOPTemplate,
  FirmKnowledge,
} from "./knowledge";
