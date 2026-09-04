import { useState, useRef, useCallback, useEffect } from 'react';
import {
  ChatMessage,
  AgentStepTraceItem,
  VerifiedCitationItem,
  AgentThread,
  AgentThreadDetail,
} from '../types/agent';
import { getApiUrl } from '../config/api';

export interface UseAgentChatReturn {
  messages: ChatMessage[];
  isStreaming: boolean;
  activeTool: string | null;
  currentStep: number;
  selectedModel: string | null;
  setSelectedModel: (model: string | null) => void;
  // Multi-turn thread state & controls (RFC-0002)
  threads: AgentThread[];
  activeThreadId: string | null;
  isHistoryOpen: boolean;
  setIsHistoryOpen: (open: boolean | ((prev: boolean) => boolean)) => void;
  loadThreads: () => Promise<void>;
  selectThread: (threadId: string) => Promise<void>;
  createNewThread: () => void;
  renameThread: (threadId: string, newTitle: string) => Promise<void>;
  deleteThread: (threadId: string) => Promise<void>;
  sendMessage: (query: string) => Promise<void>;
  cancelStreaming: () => void;
  clearChat: () => void;
}

export function useAgentChat(dossierId?: string | null): UseAgentChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);

  // Multi-turn thread management
  const [threads, setThreads] = useState<AgentThread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);

  const abortControllerRef = useRef<AbortController | null>(null);

  const loadThreads = useCallback(async () => {
    try {
      const response = await fetch(getApiUrl('/api/agent/threads'));
      if (response.ok) {
        const data: AgentThread[] = await response.json();
        setThreads(data);
      }
    } catch (err) {
      console.error('Failed to load conversation threads:', err);
    }
  }, []);

  // Hydrate threads on hook mount
  useEffect(() => {
    loadThreads();
  }, [loadThreads]);

  const cancelStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
    setActiveTool(null);
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.role === 'assistant' && last.isLoading) {
        return [
          ...prev.slice(0, -1),
          { ...last, isLoading: false, content: last.content + ' *(Response cancelled)*' },
        ];
      }
      return prev;
    });
  }, []);

  const createNewThread = useCallback(() => {
    cancelStreaming();
    setActiveThreadId(null);
    setMessages([]);
    setCurrentStep(0);
    setActiveTool(null);
  }, [cancelStreaming]);

  const clearChat = useCallback(() => {
    if (activeThreadId) {
      // If we have an active thread, create a fresh one
      createNewThread();
    } else {
      cancelStreaming();
      setMessages([]);
      setCurrentStep(0);
      setActiveTool(null);
    }
  }, [activeThreadId, cancelStreaming, createNewThread]);

  const selectThread = useCallback(
    async (threadId: string) => {
      cancelStreaming();
      setActiveThreadId(threadId);
      try {
        const response = await fetch(getApiUrl(`/api/agent/threads/${threadId}`));
        if (!response.ok) throw new Error('Failed to load thread details');
        const detail: AgentThreadDetail = await response.json();
        const loadedMessages: ChatMessage[] = detail.messages.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          timestamp: new Date(m.created_at),
          trace: m.trace,
          citations: m.citations,
          model: m.model || undefined,
          latencyMs: m.latency_ms || undefined,
        }));
        setMessages(loadedMessages);
      } catch (err) {
        console.error('Error loading thread:', err);
      }
    },
    [cancelStreaming]
  );

  const deleteThread = useCallback(
    async (threadId: string) => {
      try {
        await fetch(getApiUrl(`/api/agent/threads/${threadId}`), { method: 'DELETE' });
        setThreads((prev) => prev.filter((t) => t.id !== threadId));
        if (activeThreadId === threadId) {
          createNewThread();
        }
      } catch (err) {
        console.error('Error deleting thread:', err);
      }
    },
    [activeThreadId, createNewThread]
  );

  const renameThread = useCallback(async (threadId: string, newTitle: string) => {
    try {
      const response = await fetch(getApiUrl(`/api/agent/threads/${threadId}`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle }),
      });
      if (response.ok) {
        const updated: AgentThread = await response.json();
        setThreads((prev) => prev.map((t) => (t.id === threadId ? updated : t)));
      }
    } catch (err) {
      console.error('Error renaming thread:', err);
    }
  }, []);

  const sendMessage = useCallback(
    async (query: string) => {
      const trimmed = query.trim();
      if (!trimmed || isStreaming) return;

      // Assign or reuse thread ID
      const currentThreadId = activeThreadId || `th_${Math.random().toString(36).substring(2, 10)}`;
      if (!activeThreadId) {
        setActiveThreadId(currentThreadId);
      }

      const userMsgId = `user_${Date.now()}`;
      const assistantMsgId = `assistant_${Date.now()}`;

      const userMessage: ChatMessage = {
        id: userMsgId,
        role: 'user',
        content: trimmed,
        timestamp: new Date(),
      };

      const initialAssistantMessage: ChatMessage = {
        id: assistantMsgId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isLoading: true,
        trace: [],
        citations: [],
      };

      setMessages((prev) => [...prev, userMessage, initialAssistantMessage]);
      setIsStreaming(true);
      setActiveTool(null);
      setCurrentStep(1);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const response = await fetch(getApiUrl('/api/agent/query/stream'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: trimmed,
            thread_id: currentThreadId,
            model: selectedModel || undefined,
            dossier_id: dossierId || undefined,
          }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('ReadableStream not supported by browser.');
        }

        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        let accumulatedContent = '';
        let accumulatedTrace: AgentStepTraceItem[] = [];
        let accumulatedCitations: VerifiedCitationItem[] = [];

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse SSE frames delimited by double newlines
          let boundary = buffer.indexOf('\n\n');
          while (boundary !== -1) {
            const rawFrame = buffer.slice(0, boundary).trim();
            buffer = buffer.slice(boundary + 2);

            if (rawFrame) {
              const lines = rawFrame.split('\n');
              let eventType = 'message';
              let dataStr = '';

              for (const line of lines) {
                if (line.startsWith('event:')) {
                  eventType = line.replace('event:', '').trim();
                } else if (line.startsWith('data:')) {
                  dataStr = line.replace('data:', '').trim();
                }
              }

              if (dataStr) {
                try {
                  const data = JSON.parse(dataStr);

                  if (eventType === 'step_start') {
                    setCurrentStep(data.step || 1);
                  } else if (eventType === 'tool_call') {
                    setActiveTool(data.tool_name);
                    const newTraceItem: AgentStepTraceItem = {
                      step: data.step,
                      tool_name: data.tool_name,
                      arguments: data.arguments || {},
                      output_summary: 'Executing...',
                    };
                    accumulatedTrace = [...accumulatedTrace, newTraceItem];
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === assistantMsgId ? { ...m, trace: accumulatedTrace } : m
                      )
                    );
                  } else if (eventType === 'tool_result') {
                    setActiveTool(null);
                    accumulatedTrace = accumulatedTrace.map((t, idx) =>
                      idx === accumulatedTrace.length - 1
                        ? { ...t, output_summary: data.output_summary }
                        : t
                    );
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === assistantMsgId ? { ...m, trace: accumulatedTrace } : m
                      )
                    );
                  } else if (eventType === 'token') {
                    accumulatedContent += data.delta;
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === assistantMsgId ? { ...m, content: accumulatedContent } : m
                      )
                    );
                  } else if (eventType === 'citations') {
                    accumulatedCitations = data.citations || [];
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === assistantMsgId
                          ? { ...m, citations: accumulatedCitations }
                          : m
                      )
                    );
                  } else if (eventType === 'done') {
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === assistantMsgId
                          ? {
                              ...m,
                              content: data.answer || accumulatedContent,
                              isLoading: false,
                              trace: data.trace || accumulatedTrace,
                              citations: data.citations || accumulatedCitations,
                              latencyMs: data.latency_ms,
                              model: data.model,
                            }
                          : m
                      )
                    );
                    // Refresh threads to capture updated title and timestamp
                    loadThreads();
                  } else if (eventType === 'error') {
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === assistantMsgId
                          ? {
                              ...m,
                              isLoading: false,
                              error: data.error || 'Unknown error occurred.',
                            }
                          : m
                      )
                    );
                  }
                } catch {
                  // Ignore JSON parse errors for incomplete frames
                }
              }
            }

            boundary = buffer.indexOf('\n\n');
          }
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }
        const errorMsg = err instanceof Error ? err.message : 'Network error';
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  isLoading: false,
                  error: `Failed to query agent: ${errorMsg}`,
                }
              : m
          )
        );
      } finally {
        setIsStreaming(false);
        setActiveTool(null);
        abortControllerRef.current = null;
      }
    },
    [activeThreadId, isStreaming, loadThreads, selectedModel]
  );

  return {
    messages,
    isStreaming,
    activeTool,
    currentStep,
    selectedModel,
    setSelectedModel,
    threads,
    activeThreadId,
    isHistoryOpen,
    setIsHistoryOpen,
    loadThreads,
    selectThread,
    createNewThread,
    renameThread,
    deleteThread,
    sendMessage,
    cancelStreaming,
    clearChat,
  };
}
