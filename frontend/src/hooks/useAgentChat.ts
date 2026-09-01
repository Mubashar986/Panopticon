import { useState, useRef, useCallback } from 'react';
import { ChatMessage, AgentStepTraceItem, VerifiedCitationItem } from '../types/agent';
import { getApiUrl } from '../config/api';

export interface UseAgentChatReturn {
  messages: ChatMessage[];
  isStreaming: boolean;
  activeTool: string | null;
  currentStep: number;
  selectedModel: string | null;
  setSelectedModel: (model: string | null) => void;
  sendMessage: (query: string) => Promise<void>;
  cancelStreaming: () => void;
  clearChat: () => void;
}

export function useAgentChat(): UseAgentChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

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

  const clearChat = useCallback(() => {
    cancelStreaming();
    setMessages([]);
    setCurrentStep(0);
    setActiveTool(null);
  }, [cancelStreaming]);

  const sendMessage = useCallback(
    async (query: string) => {
      const trimmed = query.trim();
      if (!trimmed || isStreaming) return;

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
            model: selectedModel || undefined,
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
    [isStreaming, selectedModel]
  );

  return {
    messages,
    isStreaming,
    activeTool,
    currentStep,
    selectedModel,
    setSelectedModel,
    sendMessage,
    cancelStreaming,
    clearChat,
  };
}
