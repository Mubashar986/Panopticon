/**
 * TypeScript definitions for the Panopticon Agentic RAG subsystem.
 */

export interface AgentStepTraceItem {
  step: number;
  tool_name: string;
  arguments: Record<string, unknown>;
  output_summary: string;
}

export interface VerifiedCitationItem {
  file_id: string;
  document_name: string;
  web_view_link: string;
  mime_type: string;
  matched_snippet?: string | null;
  confidence_score: number;
  verification_status: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isLoading?: boolean;
  trace?: AgentStepTraceItem[];
  citations?: VerifiedCitationItem[];
  latencyMs?: number;
  model?: string;
  error?: string;
}

export type AgentStreamEventType =
  | 'step_start'
  | 'tool_call'
  | 'tool_result'
  | 'token'
  | 'citations'
  | 'done'
  | 'error';
