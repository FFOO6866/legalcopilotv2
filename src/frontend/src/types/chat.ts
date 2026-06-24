export interface Conversation {
  id: string;
  firm_id: string;
  user_id: string;
  case_id?: string;
  title?: string;
  conversation_type: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Source {
  citation: string;
  case_name: string;
  court: string;
  score: number;
  type: string;
  treatment_warning?: string;
}

export interface QualityWarning {
  status: string;
  iterations: number;
  confidence: number;
  message: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  firm_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  agent_name?: string;
  confidence?: number;
  rag_context?: {
    sources: Source[];
  };
  tokens_used: number;
  processing_time_ms: number;
  created_at: string;
}

export interface RAGFeedback {
  id: string;
  firm_id: string;
  message_id: string;
  was_helpful: boolean;
  feedback_text?: string;
  created_at: string;
}
