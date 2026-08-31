import { useEffect, useState, useRef } from 'react';
import { LiveSyncEvent } from '../types/api';

interface UseLiveEventsOptions {
  onSyncCompleted?: (data: Record<string, any>) => void;
  onFileModified?: (data: Record<string, any>) => void;
  onEvent?: (event: LiveSyncEvent) => void;
}

export function useLiveEvents(options: UseLiveEventsOptions = {}) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<LiveSyncEvent | null>(null);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    let eventSource: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;


    const connect = () => {
      eventSource = new EventSource('http://localhost:8000/api/events/live');

      eventSource.onopen = () => {
        setIsConnected(true);
      };

      const handleEvent = (type: string, rawEvent: MessageEvent) => {
        try {
          const parsed = JSON.parse(rawEvent.data);
          const liveEvent: LiveSyncEvent = {
            id: rawEvent.lastEventId || Date.now().toString(),
            event_type: type as any,
            data: parsed,
            timestamp: new Date().toISOString(),
          };
          setLastEvent(liveEvent);
          optionsRef.current.onEvent?.(liveEvent);

          if (type === 'sync_completed') {
            optionsRef.current.onSyncCompleted?.(parsed);
          } else if (type === 'file_modified') {
            optionsRef.current.onFileModified?.(parsed);
          }
        } catch (err) {
          console.warn('Failed to parse SSE payload:', err);
        }
      };

      // Listen for named event types
      const eventTypes = [
        'connected',
        'heartbeat',
        'sync_started',
        'sync_progress',
        'sync_completed',
        'sync_failed',
        'file_modified',
        'file_created',
      ];

      eventTypes.forEach((type) => {
        eventSource?.addEventListener(type, (e: MessageEvent) => handleEvent(type, e));
      });

      eventSource.onerror = () => {
        setIsConnected(false);
        eventSource?.close();
        // Native EventSource auto-reconnects, but if closed explicitly, retry in 3s
        reconnectTimer = setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (eventSource) eventSource.close();
    };
  }, []);

  return { isConnected, lastEvent };
}
