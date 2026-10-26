import { useEffect, useRef, useState, useCallback } from 'react';

export type ConnectionState = 'CONNECTED' | 'CONNECTING' | 'DISCONNECTED';

interface RealtimeHookOptions {
  onMessage?: (message: any) => void;
  reconnectInterval?: number;
}

export function useRealtime(options: RealtimeHookOptions = {}) {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionState>('CONNECTING');
  const [lastMessageTime, setLastMessageTime] = useState<Date>(new Date());
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<any>(null);
  const pingIntervalRef = useRef<any>(null);

  const connect = useCallback(() => {
    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.port === '5173' ? 'localhost:8000' : window.location.host;
      const wsUrl = `${protocol}//${host}/ws/events`;

      setConnectionStatus('CONNECTING');
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        setConnectionStatus('CONNECTED');
        setLastMessageTime(new Date());

        // Heartbeat ping every 15s
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, 15000);
      };

      ws.onmessage = (event) => {
        setLastMessageTime(new Date());
        if (event.data === 'pong') return;

        try {
          const parsed = JSON.parse(event.data);
          options.onMessage?.(parsed);
        } catch {
          // Plain text message
          options.onMessage?.({ type: 'text', data: event.data });
        }
      };

      ws.onclose = () => {
        setConnectionStatus('DISCONNECTED');
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        // Schedule reconnect
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, options.reconnectInterval || 4000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (err) {
      setConnectionStatus('DISCONNECTED');
      reconnectTimeoutRef.current = setTimeout(connect, 5000);
    }
  }, [options]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      socketRef.current?.close();
    };
  }, [connect]);

  const reconnect = () => {
    socketRef.current?.close();
    connect();
  };

  return {
    connectionStatus,
    lastMessageTime,
    reconnect,
  };
}
