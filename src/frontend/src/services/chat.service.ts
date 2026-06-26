import { nexusCall } from "./api";
import type { Conversation, Message, RAGFeedback, SendMessageResponse, DraftDocumentResponse, CloseConversationResponse } from "@/types/chat";
import type { PaginatedResponse } from "@/types/common";

export async function createConversation(
  firm_id: string,
  user_id: string,
  case_id?: string,
  conversation_type?: string,
  title?: string,
): Promise<Conversation> {
  return nexusCall<Conversation>("create_conversation", {
    firm_id,
    user_id,
    case_id,
    conversation_type,
    title,
  });
}

export async function sendMessage(
  conversation_id: string,
  content: string,
  firm_id: string,
  user_id?: string,
  case_context?: string,
): Promise<SendMessageResponse> {
  return nexusCall<SendMessageResponse>("send_message", {
    conversation_id,
    content,
    firm_id,
    user_id,
    case_context,
  });
}

export async function getConversationHistory(
  conversation_id: string,
  firm_id: string,
  limit?: number,
  offset?: number,
): Promise<PaginatedResponse<Message>> {
  const result = await nexusCall<{ messages: Message[]; total: number; limit: number; offset: number }>("get_conversation_history", {
    conversation_id,
    firm_id,
    limit,
    offset,
  });
  return { items: result.messages, total: result.total, limit: result.limit, offset: result.offset };
}

export async function listConversations(
  firm_id: string,
  case_id?: string,
): Promise<Conversation[]> {
  const result = await nexusCall<{ conversations: Conversation[]; total: number }>("search_conversations", {
    firm_id,
    case_id,
  });
  return result.conversations;
}

export async function searchConversations(
  firm_id: string,
  query?: string,
  status?: string,
  limit?: number,
  offset?: number,
): Promise<PaginatedResponse<Conversation>> {
  const result = await nexusCall<{ conversations: Conversation[]; total: number }>("search_conversations", {
    firm_id,
    query,
    status,
    limit,
    offset,
  });
  return { items: result.conversations, total: result.total, limit: limit ?? 50, offset: offset ?? 0 };
}

export async function submitFeedback(
  message_id: string,
  firm_id: string,
  was_helpful: boolean,
  feedback_text?: string,
): Promise<RAGFeedback> {
  return nexusCall<RAGFeedback>("submit_feedback", {
    message_id,
    firm_id,
    was_helpful,
    feedback_text,
  });
}

export async function closeConversation(
  conversation_id: string,
  firm_id: string,
  resolved?: boolean,
): Promise<CloseConversationResponse> {
  return nexusCall<CloseConversationResponse>("close_conversation", {
    conversation_id,
    firm_id,
    resolved,
  });
}

export async function draftDocument(
  document_type: string,
  instructions: string,
  firm_id: string,
  user_id?: string,
  case_id?: string,
  case_type?: string,
  facts?: string,
  tone?: string,
): Promise<DraftDocumentResponse> {
  return nexusCall<DraftDocumentResponse>(
    "draft_document",
    {
      document_type,
      instructions,
      firm_id,
      user_id,
      case_id,
      case_type,
      facts,
      tone,
    },
  );
}
